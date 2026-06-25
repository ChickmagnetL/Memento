/**
 * TypeScript definitions for Electron IPC API.
 *
 * These types match the API exposed via contextBridge in preload.js.
 * Login event listeners return a cleanup function for unsubscription.
 */

export interface ElectronAPI {
  openLogin: (platform: 'bilibili' | 'douyin') => void;
  clearLoginSession: (platform: 'bilibili' | 'douyin') => Promise<void>;
  onCookieReady: (callback: (data: { platform: string; cookies: string }) => void) => () => void;
  onCookieRefreshed: (callback: (data: { platform: string; cookies: string }) => void) => () => void;
  openVideoPlayer: (params: { platform: string; videoId: string; timestamp: number }) => void;
}

declare global {
  interface Window {
    electron?: ElectronAPI;
  }
}
