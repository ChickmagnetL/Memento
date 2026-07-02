"""
pytest configuration for Memento backend tests.

WHY THIS EXISTS (DATA LOSS INCIDENT):

The test suite originally had NO isolation. Tests using TestClient(app) at module
level (test_health.py, test_asr_deploy_api.py, test_asr_model_api.py) triggered the
app lifespan which connected to the REAL data/metadata.db. Test runs would silently
read from, write to, and potentially replace the real database.

On 2026-07-02, this caused the real database to be replaced with a fresh one,
resulting in data loss.

SOLUTION:

pytest_configure runs BEFORE any test modules are imported. By setting
MEMENTO_PROJECT_ROOT to a temp directory, resolve_project_root() in
backend/config/settings.py returns the temp dir, which makes data_dir resolve
relative to that temp dir. All TestClient(app) instances then use an isolated
database, never touching the real data/metadata.db.
"""

import os
import shutil
import tempfile


def pytest_configure(config):
    """Create an isolated temp project root so tests never touch real data/."""
    tmpdir = tempfile.mkdtemp(prefix="memento_test_")
    os.environ["MEMENTO_PROJECT_ROOT"] = tmpdir
    os.environ["TESTING"] = "1"

    # Stash on the config object for cleanup in pytest_unconfigure
    config._memento_test_tmpdir = tmpdir


def pytest_unconfigure(config):
    """Clean up the isolated temp directory and env vars."""
    os.environ.pop("MEMENTO_PROJECT_ROOT", None)
    os.environ.pop("TESTING", None)

    tmpdir = getattr(config, "_memento_test_tmpdir", None)
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)