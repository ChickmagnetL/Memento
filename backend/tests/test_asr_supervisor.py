"""Tests for the lazy ASR service supervisor."""

import os
import signal
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.video.asr_client import AsrError
from core.video import asr_supervisor
from core.video.asr_supervisor import ensure_asr_running, shutdown


@pytest.fixture(autouse=True)
def reset_spawned_proc():
    asr_supervisor._spawned_proc = None
    yield
    asr_supervisor._spawned_proc = None


@pytest.fixture
def existing_venv(tmp_path) -> Path:
    """A real file path standing in for the installed ASR venv binary."""
    venv = tmp_path / "uvicorn"
    venv.touch()
    return venv


def _fake_proc(pid: int = 999999) -> Mock:
    """A fake subprocess.Popen whose pid does not resolve to a real process.

    ``poll()`` returns None to indicate the process is still alive.
    """
    proc = Mock()
    proc.pid = pid
    proc.poll = Mock(return_value=None)
    return proc


def _exited_proc(stderr: bytes = b"missing dependency") -> Mock:
    proc = Mock()
    proc.pid = 999998
    proc.poll = Mock(return_value=1)
    proc.communicate = Mock(return_value=(b"", stderr))
    return proc


def test_healthy_service_does_not_spawn():
    spawn = Mock()

    ensure_asr_running(
        "http://localhost:8001",
        is_healthy=lambda endpoint: True,
        venv_path=lambda: Path("/does/not/exist"),
        spawn=spawn,
        sleep=lambda _: None,
    )

    spawn.assert_not_called()


def test_unhealthy_with_venv_spawns_and_waits_until_healthy(existing_venv):
    spawn = Mock(return_value=_fake_proc())
    # unhealthy until after spawn is called, then becomes healthy
    health_state = {"up": False}

    def is_healthy(endpoint):
        return health_state["up"]

    def spawn_wrapper(venv, port):
        result = spawn(venv, port)
        health_state["up"] = True
        return result

    ensure_asr_running(
        "http://localhost:8001",
        is_healthy=is_healthy,
        venv_path=lambda: existing_venv,
        spawn=spawn_wrapper,
        sleep=lambda _: None,
    )

    spawn.assert_called_once()
    venv, port = spawn.call_args.args
    assert venv == existing_venv
    assert port == 8001


def test_missing_venv_skips_spawn_and_does_not_raise():
    spawn = Mock()

    ensure_asr_running(
        "http://localhost:8001",
        is_healthy=lambda endpoint: False,
        venv_path=lambda: Path("/does/not/exist"),
        spawn=spawn,
        sleep=lambda _: None,
    )

    spawn.assert_not_called()


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://192.168.1.10:8001/v1",
        "https://api.siliconflow.cn/v1",
    ],
)
def test_remote_endpoint_returns_without_spawn_or_health_check(endpoint):
    spawn = Mock()

    def fail_health_check(_endpoint):
        raise AssertionError("remote endpoint should not be checked")

    def fail_venv_path():
        raise AssertionError("remote endpoint should not inspect local venv")

    ensure_asr_running(
        endpoint,
        is_healthy=fail_health_check,
        venv_path=fail_venv_path,
        spawn=spawn,
        sleep=lambda _: None,
    )

    spawn.assert_not_called()


def test_service_never_becomes_healthy_raises_asr_error(existing_venv):
    spawn = Mock(return_value=_fake_proc())

    with pytest.raises(AsrError, match="did not become healthy"):
        ensure_asr_running(
            "http://localhost:8001",
            timeout=0.0,
            is_healthy=lambda endpoint: False,
            venv_path=lambda: existing_venv,
            spawn=spawn,
            sleep=lambda _: None,
        )


def test_spawn_exit_surfaces_startup_error(existing_venv):
    spawn = Mock(return_value=_exited_proc(b"python-multipart missing"))

    with pytest.raises(AsrError, match="python-multipart missing"):
        ensure_asr_running(
            "http://localhost:8001",
            timeout=10.0,
            is_healthy=lambda endpoint: False,
            venv_path=lambda: existing_venv,
            spawn=spawn,
            sleep=lambda _: None,
        )


def test_does_not_respawn_when_already_spawned(existing_venv):
    spawn = Mock(return_value=_fake_proc())

    for _ in range(2):
        try:
            ensure_asr_running(
                "http://localhost:8001",
                timeout=0.0,
                is_healthy=lambda endpoint: False,
                venv_path=lambda: existing_venv,
                spawn=spawn,
                sleep=lambda _: None,
            )
        except AsrError:
            pass

    spawn.assert_called_once()


def test_port_parsed_from_endpoint(existing_venv):
    captured = {}

    def spawn(venv, port):
        captured["port"] = port
        return _fake_proc()

    health_state = {"up": False}

    def is_healthy(endpoint):
        return health_state["up"]

    def spawn_wrapper(venv, port):
        result = spawn(venv, port)
        health_state["up"] = True
        return result

    ensure_asr_running(
        "http://127.0.0.1:9001",
        is_healthy=is_healthy,
        venv_path=lambda: existing_venv,
        spawn=spawn_wrapper,
        sleep=lambda _: None,
    )

    assert captured["port"] == 9001


def test_respawns_when_spawned_process_died_mid_session(existing_venv):
    proc1 = _fake_proc()
    proc1.poll = Mock(return_value=1)  # first process has exited
    proc2 = _fake_proc()  # replacement is alive
    spawn = Mock(side_effect=[proc1, proc2])
    health_state = {"up": False}

    def is_healthy(endpoint):
        return health_state["up"]

    def spawn_wrapper(venv, port):
        result = spawn(venv, port)
        health_state["up"] = True  # each spawn brings the service up
        return result

    # First call spawns proc1 and waits until healthy.
    ensure_asr_running(
        "http://localhost:8001",
        timeout=2.0,
        is_healthy=is_healthy,
        venv_path=lambda: existing_venv,
        spawn=spawn_wrapper,
        sleep=lambda _: None,
    )

    # Service dies mid-session.
    health_state["up"] = False

    # Second call should detect the dead proc1 and respawn proc2.
    ensure_asr_running(
        "http://localhost:8001",
        timeout=2.0,
        is_healthy=is_healthy,
        venv_path=lambda: existing_venv,
        spawn=spawn_wrapper,
        sleep=lambda _: None,
    )

    assert spawn.call_count == 2


def test_shutdown_terminates_spawned_process_group(monkeypatch):
    proc = _fake_proc()
    proc.pid = 4242
    asr_supervisor._spawned_proc = proc
    killed = []
    monkeypatch.setattr(os, "getpgid", lambda pid: 5555)
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: killed.append((pgid, sig)))

    shutdown()

    assert killed == [(5555, signal.SIGTERM)]
    assert asr_supervisor._spawned_proc is None


def test_shutdown_noop_when_nothing_spawned():
    asr_supervisor._spawned_proc = None
    shutdown()  # must not raise
    assert asr_supervisor._spawned_proc is None


def test_default_venv_path_uses_windows_scripts_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(asr_supervisor, "resolve_project_root", lambda: tmp_path)

    assert asr_supervisor._default_venv_path() == (
        tmp_path / "services" / "asr" / ".venv" / "Scripts" / "uvicorn.exe"
    )


def test_windows_shutdown_terminates_process_directly(monkeypatch):
    proc = _fake_proc()
    asr_supervisor._spawned_proc = proc
    monkeypatch.setattr(sys, "platform", "win32")

    shutdown()

    proc.terminate.assert_called_once_with()
    assert asr_supervisor._spawned_proc is None
