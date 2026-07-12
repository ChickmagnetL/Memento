/**
 * LoginWindowManager - Handles QR code login with a dedicated modal shell
 *
 * Opens a modal BrowserWindow with Memento chrome, attaches a BrowserView
 * for the platform auth surface, polls for login success cookies, and
 * notifies the frontend when complete.
 */

const { BrowserView, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { setActiveRefreshToken } = require('./cookie-refresh');

const LOGIN_URLS = {
  bilibili: 'https://passport.bilibili.com/login',
  douyin: 'https://www.douyin.com/jingxuan'
};

const COOKIE_CHECKS = {
  bilibili: (cookies) => {
    const hasSessData = cookies.some(c => c.name === 'SESSDATA');
    const hasBiliJct = cookies.some(c => c.name === 'bili_jct');
    return hasSessData && hasBiliJct;
  },
  douyin: (cookies) => {
    return cookies.some(c => c.name === 'sessionid');
  }
};

// Platform-specific CSS to hide non-login content
// Selectors derived from live DOM analysis
const PLATFORM_CSS = {
  bilibili: `
    /* Hide page chrome */
    .login_mask,
    .bili-header, .bili-footer,
    .international-header, .international-footer,
    .login-nav, .agreement-tip, .link-login,
    .app-download, .side-container, .banner,
    .promotion, .notice-banner,
    .login-protocol {
      display: none !important;
    }
    /* Clean background */
    body {
      background: #f4f4f4 !important;
      overflow: hidden !important;
      padding: 0 !important;
      margin: 0 !important;
    }
    /* Reset parent containers */
    #app, #app-main {
      padding: 0 !important;
      margin: 0 !important;
      height: 100vh !important;
      min-height: 100vh !important;
      overflow: hidden !important;
    }
    /* Center the login wrapper */
    .login_wp {
      position: fixed !important;
      top: 0 !important;
      left: 0 !important;
      right: 0 !important;
      bottom: 0 !important;
      width: 100% !important;
      display: flex !important;
      flex-direction: column !important;
      align-items: center !important;
      justify-content: center !important;
      padding: 0 !important;
      margin: 0 !important;
      min-height: auto !important;
      height: auto !important;
    }
    /* Scale the login card */
    .login__main {
      transform: scale(0.85) !important;
      transform-origin: center center !important;
    }
  `,
  douyin: `
    /* Hide page-level content */
    [role="banner"], [role="tablist"],
    [role="tabpanel"], [role="contentinfo"],
    nav, header, footer {
      display: none !important;
    }
    /* Dark overlay background */
    body {
      background: rgba(0, 0, 0, 0.6) !important;
      overflow: hidden !important;
    }
    /* The overlay parent (.kqi3HrY4) already centers the dialog
       via position:fixed + display:flex. Do NOT override position
       on #douyin-login-new-id — that would fight the parent's
       flex centering. Just handle overflow for the Electron
       BrowserView where the dialog (483px) exceeds viewport (464px). */
    #douyin-login-new-id {
      z-index: 99999 !important;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
      border-radius: 12px !important;
      max-height: 100vh !important;
      overflow: auto !important;
    }
  `
};

// JS to auto-trigger Douyin login dialog
const DOUYIN_AUTO_LOGIN_JS = `
  (() => {
    const candidates = Array.from(document.querySelectorAll("button, div, span, a"));
    const loginTrigger = candidates.find((node) => {
      const text = (node.textContent || "").trim();
      return text === "登录" || text.includes("登录");
    });
    if (loginTrigger instanceof HTMLElement) {
      loginTrigger.click();
      return true;
    }
    return false;
  })();
`;

class LoginWindowManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.loginWindow = null;
    this.authView = null;
    this.pollInterval = null;
    this.currentPlatform = null;
    this.errorCount = 0;
    this.MAX_ERRORS = 5;
    this.loginCompleted = false;
  }

  async open(platform) {
    if (!LOGIN_URLS[platform]) {
      console.error(`[login-manager] Unknown platform: ${platform}`);
      return;
    }

    // Close any existing login window
    if (this.loginWindow && !this.loginWindow.isDestroyed()) {
      this.close();
    }

    this.currentPlatform = platform;
    this.loginCompleted = false;

    // Create a frameless modal window — the custom shell provides all chrome
    // Size per platform to fit the login element tightly
    const windowSize = platform === 'bilibili'
      ? { width: 780, height: 540 }   // 900*0.85=765, need ~780
      : { width: 750, height: 520 };  // douyin dialog is 726, need ~750

    this.loginWindow = new BrowserWindow({
      parent: this.mainWindow,
      modal: false,
      show: false,
      frame: false,
      width: windowSize.width,
      height: windowSize.height,
      resizable: false,
      minimizable: false,
      maximizable: false,
      title: platform === 'bilibili' ? 'Bilibili 登录' : '抖音登录',
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    });

    // Load the Memento shell HTML
    const shellPath = path.join(__dirname, 'login-shell.html');
    await this.loginWindow.loadFile(shellPath, {
      query: { platform }
    });

    // Create the auth BrowserView with platform session
    const session = require('electron').session.fromPartition(`persist:${platform}`, {
      cache: true
    });

    this.authView = new BrowserView({
      webPreferences: {
        partition: `persist:${platform}`,
        session,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    });

    // Attach BrowserView over the auth-surface region
    this.loginWindow.setBrowserView(this.authView);

    // Position the auth view inside the shell
    // Shell layout: header(42px) + auth(flex) + footer(34px)
    const contentBounds = this.loginWindow.getContentBounds();
    const headerHeight = 42;
    const footerHeight = 34;
    const authHeight = contentBounds.height - headerHeight - footerHeight;

    this.authView.setBounds({
      x: 0,
      y: headerHeight,
      width: contentBounds.width,
      height: authHeight
    });

    this.authView.setAutoResize({ width: true, height: true });

    // Register did-finish-load listeners BEFORE loadURL so we catch the
    // initial page load (loadURL resolves after this event fires).
    this.authView.webContents.on('did-finish-load', () => {
      this.injectPlatformCSS(platform);
    });

    // For Douyin: auto-trigger the login dialog
    if (platform === 'douyin') {
      this.authView.webContents.on('did-finish-load', () => {
        setTimeout(() => this.triggerDouyinLogin(), 1500);
      });
    }

    // Load the platform login URL
    await this.authView.webContents.loadURL(LOGIN_URLS[platform]);

    // Now show the window (shell is ready, auth is loading)
    this.loginWindow.show();

    // Handle window close
    this.loginWindow.on('closed', () => {
      this.cleanup();
    });

    // Start cookie polling
    this.startCookiePolling(session, platform);
  }

  injectPlatformCSS(platform) {
    const css = PLATFORM_CSS[platform];
    if (!css || !this.authView) return;

    this.authView.webContents.insertCSS(css).catch(err => {
      console.error(`[login-manager] CSS injection failed for ${platform}:`, err.message);
    });
  }

  async triggerDouyinLogin() {
    if (!this.authView || this.authView.webContents.isDestroyed()) return;

    try {
      const result = await this.authView.webContents.executeJavaScript(DOUYIN_AUTO_LOGIN_JS);
      if (!result) {
        console.log('[login-manager] Douyin login trigger not found, user must click manually');
      }
    } catch (err) {
      console.error('[login-manager] Douyin auto-login trigger failed:', err.message);
    }
  }

  startCookiePolling(session, platform) {
    this.pollInterval = setInterval(async () => {
      try {
        if (this.loginCompleted) return;

        const cookies = await session.cookies.get({});
        this.errorCount = 0;

        const checkFunc = COOKIE_CHECKS[platform];
        if (checkFunc && checkFunc(cookies)) {
          console.log(`[login-manager] Login success detected for ${platform}`);
          this.loginCompleted = true;
          // stop polling before async work
          if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
          }
          await this.onLoginSuccess(cookies, platform);
        }
      } catch (error) {
        console.error(`[login-manager] Cookie polling error:`, error);
        this.errorCount++;
        if (this.errorCount >= this.MAX_ERRORS) {
          console.error(`[login-manager] Too many errors, stopping cookie polling`);
          this.close();
        }
      }
    }, 1000);
  }

  async onLoginSuccess(cookies, platform) {
    // Guard: main window may have been destroyed
    if (this.mainWindow.isDestroyed()) {
      this.close();
      return;
    }

    const cookieString = cookies.map(c => `${c.name}=${c.value}`).join('; ');

    let refreshToken = '';
    if (platform === 'bilibili' && this.authView && !this.authView.webContents.isDestroyed()) {
      try {
        for (let attempt = 0; attempt < 3; attempt++) {
          refreshToken = await this.authView.webContents.executeJavaScript(`
            (() => {
              try { return window.localStorage.getItem('ac_time_value') || ''; }
              catch (e) { return ''; }
            })()
          `);
          if (refreshToken) break;
          if (attempt < 2) {
            await new Promise((r) => setTimeout(r, 200));
          }
        }
        if (!refreshToken) {
          console.warn(
            "[login-manager] Bilibili login succeeded but ac_time_value missing; auto-refresh unavailable"
          );
        }
      } catch (err) {
        console.warn(
          "[login-manager] Failed to read ac_time_value:",
          err && err.message ? err.message : err
        );
      }
    }

    if (refreshToken) {
      setActiveRefreshToken(refreshToken);
    }

    const payload = {
      platform,
      cookies: cookieString
    };
    if (refreshToken) {
      payload.refresh_token = refreshToken;
    }

    this.mainWindow.webContents.send('cookie-ready', payload);

    this.close();
  }

  close() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }

    if (this.loginWindow && !this.loginWindow.isDestroyed()) {
      const win = this.loginWindow;
      this.loginWindow = null;
      this.authView = null;
      win.close();
    }

    this.currentPlatform = null;
    this.loginCompleted = false;
  }

  cleanup() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
    this.loginWindow = null;
    this.authView = null;
    this.currentPlatform = null;
    this.loginCompleted = false;
  }
}

module.exports = { LoginWindowManager };
