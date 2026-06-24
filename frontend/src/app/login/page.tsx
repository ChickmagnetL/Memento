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
  platform: "bilibili" | "douyin";
  displayName: string;
  status: PlatformStatus;
  onLogin: () => void;
  onRelogin: () => void;
}

function PlatformCard({ platform, displayName, status, onLogin, onRelogin }: PlatformCardProps) {
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
  const [isElectronAvailable, setIsElectronAvailable] = useState(false);

  useEffect(() => {
    // Check if running in Electron
    setIsElectronAvailable(typeof window !== "undefined" && !!window.electron);

    // Load initial settings
    getVideoProcessingSettings()
      .then(setSettings)
      .catch(() => setMessage("加载设置失败"));
  }, []);

  useEffect(() => {
    if (!window.electron) return;

    // Listen for cookie-ready event
    const handleCookieReady = async (data: { platform: string; cookies: string }) => {
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
    };

    // Listen for cookie-refreshed event
    const handleCookieRefreshed = async (data: { platform: string; cookies: string }) => {
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
    };

    window.electron.onCookieReady(handleCookieReady);
    window.electron.onCookieRefreshed(handleCookieRefreshed);
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

    // Clear Electron session
    window.electron.clearLoginSession(platform);

    // Clear backend cookie
    const updatePayload =
      platform === "bilibili"
        ? { bilibili_cookie: "" }
        : { douyin_cookie: "" };

    try {
      const updated = await updateVideoProcessingSettings(updatePayload);
      setSettings(updated);
      setMessage("登录状态已清除，请重新登录");

      // Open login window after a brief delay
      setTimeout(() => {
        window.electron!.openLogin(platform);
      }, 500);
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
            platform="bilibili"
            displayName="Bilibili"
            status={getBilibiliStatus()}
            onLogin={() => handleLogin("bilibili")}
            onRelogin={() => handleRelogin("bilibili")}
          />
          <PlatformCard
            platform="douyin"
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
