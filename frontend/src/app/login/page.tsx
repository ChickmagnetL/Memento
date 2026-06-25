"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  getVideoProcessingSettings,
  updateVideoProcessingSettings,
  type VideoProcessingSettings,
} from "@/lib/api";

type PlatformStatus = "logged_in" | "not_logged_in";

interface PlatformCardProps {
  displayName: string;
  status: PlatformStatus;
  onLogin: () => void;
  onRelogin: () => void;
}

function PlatformCard({ displayName, status, onLogin, onRelogin }: PlatformCardProps) {
  const isLoggedIn = status === "logged_in";

  return (
    <div className="rounded-md border border-input p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{displayName}</h2>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              isLoggedIn ? "bg-green-500" : "bg-gray-400"
            }`}
          />
          <span className="text-sm text-muted-foreground">
            {isLoggedIn ? "已登录" : "未登录"}
          </span>
        </div>
      </div>
      <div className="flex gap-2">
        <Button onClick={onLogin} variant="outline" className="flex-1">
          {isLoggedIn ? "登录" : "使用二维码登录"}
        </Button>
        {isLoggedIn && (
          <Button onClick={onRelogin} variant="outline" className="flex-1">
            重新登录
          </Button>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  const [settings, setSettings] = useState<VideoProcessingSettings | null>(null);
  const [message, setMessage] = useState("");
  const [isElectronAvailable] = useState(() => typeof window !== "undefined" && !!window.electron);

  useEffect(() => {
    // Load initial settings
    getVideoProcessingSettings()
      .then(setSettings)
      .catch(() => setMessage("加载设置失败"));
  }, []);

  useEffect(() => {
    if (!window.electron) return;

    const offCookieReady = window.electron.onCookieReady(async (data) => {
      try {
        const updatePayload =
          data.platform === "bilibili"
            ? { bilibili_cookie: data.cookies }
            : { douyin_cookie: data.cookies };
        const updated = await updateVideoProcessingSettings(updatePayload);
        setSettings(updated);
        setMessage(`${data.platform === "bilibili" ? "Bilibili" : "Douyin"} 登录成功`);
      } catch {
        setMessage("保存登录凭证失败");
      }
    });

    const offCookieRefreshed = window.electron.onCookieRefreshed(async (data) => {
      try {
        const updatePayload =
          data.platform === "bilibili"
            ? { bilibili_cookie: data.cookies }
            : { douyin_cookie: data.cookies };
        const updated = await updateVideoProcessingSettings(updatePayload);
        setSettings(updated);
        setMessage(`${data.platform === "bilibili" ? "Bilibili" : "Douyin"} 凭证已刷新`);
      } catch {
        setMessage("保存刷新凭证失败");
      }
    });

    return () => {
      offCookieReady();
      offCookieRefreshed();
    };
  }, []);

  const handleLogin = (platform: "bilibili" | "douyin") => {
    if (!window.electron) {
      setMessage("此功能仅在 Electron 应用中可用");
      return;
    }
    setMessage("");
    window.electron.openLogin(platform);
  };

  const handleRelogin = async (platform: "bilibili" | "douyin") => {
    if (!window.electron) {
      setMessage("此功能仅在 Electron 应用中可用");
      return;
    }
    setMessage("正在清除登录状态...");

    try {
      // Clear Electron session (await to ensure storage is wiped before reopening)
      await window.electron.clearLoginSession(platform);

      // Clear backend cookie
      const updatePayload =
        platform === "bilibili"
          ? { bilibili_cookie: "" }
          : { douyin_cookie: "" };
      const updated = await updateVideoProcessingSettings(updatePayload);
      setSettings(updated);

      // Open login window immediately (session is already cleared)
      window.electron.openLogin(platform);
    } catch {
      setMessage("清除登录状态失败");
    }
  };

  const getBilibiliStatus = (): PlatformStatus => {
    return settings?.bilibili_cookie ? "logged_in" : "not_logged_in";
  };

  const getDouyinStatus = (): PlatformStatus => {
    return settings?.douyin_cookie ? "logged_in" : "not_logged_in";
  };

  if (!isElectronAvailable) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
        <header className="space-y-1">
          <h1 className="text-xl font-semibold">登录</h1>
        </header>
        <p className="text-sm text-muted-foreground">
          此功能仅在 Electron 桌面应用中可用。
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">登录</h1>
        <p className="text-sm text-muted-foreground">
          使用二维码登录视频平台以访问需要登录的内容
        </p>
      </header>

      {message && (
        <p className="text-sm text-muted-foreground">{message}</p>
      )}

      {settings ? (
        <div className="grid gap-4 md:grid-cols-2">
          <PlatformCard
            displayName="Bilibili"
            status={getBilibiliStatus()}
            onLogin={() => handleLogin("bilibili")}
            onRelogin={() => handleRelogin("bilibili")}
          />
          <PlatformCard
            displayName="Douyin"
            status={getDouyinStatus()}
            onLogin={() => handleLogin("douyin")}
            onRelogin={() => handleRelogin("douyin")}
          />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">加载中…</p>
      )}
    </div>
  );
}
