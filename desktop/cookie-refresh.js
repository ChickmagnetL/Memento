/**
 * CookieRefreshScheduler - Auto-refresh Bilibili cookies every 12 hours
 *
 * Checks immediately on startup, then every 12 hours. Reads Bilibili session
 * cookies and logs status. Full refresh API implementation deferred (requires
 * extracting refresh_token from BrowserView localStorage).
 */

const { session } = require('electron');

const CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000; // 12 hours

class CookieRefreshScheduler {
  constructor() {
    this.intervalId = null;
  }

  start() {
    console.log('[cookie-refresh] Starting CookieRefreshScheduler');

    // Check immediately on startup
    this.checkAndRefresh();

    // Then check every 12 hours
    this.intervalId = setInterval(() => {
      this.checkAndRefresh();
    }, CHECK_INTERVAL_MS);
  }

  stop() {
    if (this.intervalId) {
      console.log('[cookie-refresh] Stopping CookieRefreshScheduler');
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  async checkAndRefresh() {
    try {
      console.log('[cookie-refresh] Running cookie refresh check');

      const bilibiliSession = session.fromPartition('persist:bilibili', {
        cache: true
      });

      const cookies = await bilibiliSession.cookies.get({});

      const hasSessData = cookies.some(c => c.name === 'SESSDATA');
      const hasBiliJct = cookies.some(c => c.name === 'bili_jct');

      if (hasSessData && hasBiliJct) {
        console.log('[cookie-refresh] Bilibili cookies found (SESSDATA + bili_jct)');
        console.log('[cookie-refresh] Cookie refresh check complete (full refresh API requires refresh_token from localStorage)');
      } else {
        console.log('[cookie-refresh] No Bilibili cookies found, skipping refresh');
      }
    } catch (error) {
      console.error('[cookie-refresh] Error during cookie refresh check:', error);
    }
  }
}

module.exports = { CookieRefreshScheduler };
