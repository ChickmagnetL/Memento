/**
 * LoginWindowManager - Handles QR code login windows with cookie detection
 *
 * Opens a BrowserView overlaid on the main window, displays platform login pages,
 * polls for login success cookies, and notifies the frontend when complete.
 */

const { BrowserView, ipcMain } = require('electron');

const LOGIN_URLS = {
  bilibili: 'https://passport.bilibili.com/login',
  douyin: 'https://www.douyin.com/passport/web/login/'
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

class LoginWindowManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.loginView = null;
    this.pollInterval = null;
    this.currentPlatform = null;
    this.errorCount = 0;
    this.MAX_ERRORS = 5;
  }

  async open(platform) {
    if (!LOGIN_URLS[platform]) {
      console.error(`[login-manager] Unknown platform: ${platform}`);
      return;
    }

    if (this.loginView) {
      this.close();
    }

    this.currentPlatform = platform;

    const session = require('electron').session.fromPartition(`persist:${platform}`, {
      cache: true
    });

    this.loginView = new BrowserView({
      webPreferences: {
        partition: `persist:${platform}`,
        session,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    });

    this.mainWindow.addBrowserView(this.loginView);

    const bounds = this.mainWindow.getContentBounds();
    const width = 500;
    const height = 600;
    const x = Math.floor((bounds.width - width) / 2);
    const y = Math.floor((bounds.height - height) / 2);

    this.loginView.setBounds({
      x,
      y,
      width,
      height
    });

    this.loginView.setAutoResize({
      width: false,
      height: false
    });

    await this.loginView.webContents.loadURL(LOGIN_URLS[platform]);

    this.startCookiePolling(session, platform);
  }

  startCookiePolling(session, platform) {
    this.pollInterval = setInterval(async () => {
      try {
        const cookies = await session.cookies.get({});
        this.errorCount = 0; // Reset on success

        const checkFunc = COOKIE_CHECKS[platform];
        if (checkFunc && checkFunc(cookies)) {
          console.log(`[login-manager] Login success detected for ${platform}`);
          this.onLoginSuccess(cookies, platform);
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

  onLoginSuccess(cookies, platform) {
    const cookieString = cookies.map(c => `${c.name}=${c.value}`).join('; ');

    this.mainWindow.webContents.send('cookie-ready', {
      platform,
      cookies: cookieString
    });

    this.close();
  }

  close() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }

    if (this.loginView) {
      this.mainWindow.removeBrowserView(this.loginView);
      this.loginView.webContents.close();
      this.loginView = null;
    }

    this.currentPlatform = null;
  }
}

module.exports = { LoginWindowManager };
