/**
 * TypeScript definitions for Electron IPC API.
 *
 * These types match the API exposed via contextBridge in preload.js.
 */

export interface ElectronAPI {
  openLogin: (platform: 'bilibili' | 'douyin') => void;
  onCookieReady: (callback: (data: { platform: string; cookies: string }) => void) => void;
  onCookieRefreshed: (callback: (data: { platform: string; cookies: string }) => void) => void;
  openVideoPlayer: (params: { platform: string; videoId: string; timestamp: number }) => void;
}

declare global {
  interface Window {
    electron?: ElectronAPI;
  }
}
