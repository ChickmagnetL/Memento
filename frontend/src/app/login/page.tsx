"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  getVideoProcessingSettings,
  updateVideoProcessingSettings,
  type VideoProcessingSettings,
} from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type PlatformStatus = "logged_in" | "not_logged_in";

interface PlatformCardProps {
  displayName: string;
  status: PlatformStatus;
  onLogin: () => void;
  onRelogin: () => void;
}

function PlatformCard({ displayName, status, onLogin, onRelogin }: PlatformCardProps) {
  const { t } = useLanguage();
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
            {isLoggedIn ? t("Logged in") : t("Not logged in")}
          </span>
        </div>
      </div>
      <div className="flex gap-2">
        <Button onClick={onLogin} variant="outline" className="flex-1">
          {isLoggedIn ? t("Login") : t("Login with QR code")}
        </Button>
        {isLoggedIn && (
          <Button onClick={onRelogin} variant="outline" className="flex-1">
            {t("Relogin")}
          </Button>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  const { t } = useLanguage();
  const [settings, setSettings] = useState<VideoProcessingSettings | null>(null);
  const [message, setMessage] = useState("");
  const [isElectronAvailable] = useState(() => typeof window !== "undefined" && !!window.electron);

  useEffect(() => {
    // Load initial settings
    getVideoProcessingSettings()
      .then(setSettings)
      .catch((e) => setMessage(e instanceof Error ? e.message : t("Failed to load settings")));
  }, [t]);

  useEffect(() => {
    if (!window.electron) return;

    const offCookieReady = window.electron.onCookieReady(async (data) => {
      try {
        const updatePayload =
          data.platform === "bilibili"
            ? {
                bilibili_cookie: data.cookies,
                ...(data.refresh_token
                  ? { bilibili_refresh_token: data.refresh_token }
                  : {}),
              }
            : { douyin_cookie: data.cookies };
        const updated = await updateVideoProcessingSettings(updatePayload);
        setSettings(updated);
        setMessage(t("{platform} login successful", {
          platform: data.platform === "bilibili" ? "Bilibili" : "Douyin",
        }));
      } catch (e) {
        setMessage(e instanceof Error ? e.message : t("Failed to save login credentials"));
      }
    });

    const offCookieRefreshed = window.electron.onCookieRefreshed(async (data) => {
      try {
        const updatePayload =
          data.platform === "bilibili"
            ? {
                bilibili_cookie: data.cookies,
                ...(data.refresh_token
                  ? { bilibili_refresh_token: data.refresh_token }
                  : {}),
              }
            : { douyin_cookie: data.cookies };
        const updated = await updateVideoProcessingSettings(updatePayload);
        setSettings(updated);
        setMessage(t("{platform} credentials refreshed", {
          platform: data.platform === "bilibili" ? "Bilibili" : "Douyin",
        }));
      } catch (e) {
        setMessage(e instanceof Error ? e.message : t("Failed to save refreshed credentials"));
      }
    });

    return () => {
      offCookieReady();
      offCookieRefreshed();
    };
  }, [t]);

  const handleLogin = (platform: "bilibili" | "douyin") => {
    if (!window.electron) {
      setMessage(t("This feature is only available in the Electron desktop app."));
      return;
    }
    setMessage("");
    window.electron.openLogin(platform);
  };

  const handleRelogin = async (platform: "bilibili" | "douyin") => {
    if (!window.electron) {
      setMessage(t("This feature is only available in the Electron desktop app."));
      return;
    }
    setMessage(t("Clearing login status..."));

    try {
      // Clear Electron session (await to ensure storage is wiped before reopening)
      await window.electron.clearLoginSession(platform);

      // Clear backend cookie
      const updatePayload =
        platform === "bilibili"
          ? {
              bilibili_cookie: "",
              bilibili_refresh_token: "",
              bilibili_cookie_expires_at: 0,
            }
          : { douyin_cookie: "" };
      const updated = await updateVideoProcessingSettings(updatePayload);
      setSettings(updated);

      // Open login window immediately (session is already cleared)
      window.electron.openLogin(platform);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : t("Failed to clear login status"));
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
          <h1 className="text-xl font-semibold">{t("Login")}</h1>
        </header>
        <p className="text-sm text-muted-foreground">
          {t("This feature is only available in the Electron desktop app.")}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">{t("Login")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("Log in to video platforms with a QR code to access content that requires an account")}
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
        <p className="text-sm text-muted-foreground">{t("Loading...")}</p>
      )}
    </div>
  );
}
