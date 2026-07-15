/**
 * TypeScript definitions for Electron IPC API.
 *
 * These types match the API exposed via contextBridge in preload.js.
 * Login event listeners return a cleanup function for unsubscription.
 */

export type CookieEventPayload = {
  platform: string;
  cookies: string;
  refresh_token?: string;
};

export interface ElectronAPI {
  openGitHub: () => Promise<void>;
  openLogin: (platform: "bilibili" | "douyin") => void;
  clearLoginSession: (platform: "bilibili" | "douyin") => Promise<void>;
  onCookieReady: (callback: (data: CookieEventPayload) => void) => () => void;
  onCookieRefreshed: (callback: (data: CookieEventPayload) => void) => () => void;
  refreshBilibiliCookie?: () => Promise<{
    ok: boolean;
    refreshed: boolean;
    reason?: string;
  }>;
  openVideoPlayer: (params: {
    platform: string;
    videoId: string;
    timestamp?: number;
  }) => void;
}

declare global {
  interface Window {
    electron?: ElectronAPI;
  }
}
