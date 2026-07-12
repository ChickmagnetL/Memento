/**
 * CookieRefreshScheduler - Official bilibili cookie refresh state machine
 *
 * Checks immediately on startup, then every 12 hours. When refresh is needed,
 * runs the community protocol (cookie/info → correspondPath → refresh → confirm),
 * updates the Electron jar, notifies the renderer, and soft-writes backend config.
 */

const crypto = require('crypto');

function getSession() {
  // Lazy require so pure helpers can load outside Electron (node -e tests).
  return require('electron').session;
}

const CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000; // 12 hours
const BILIBILI_PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLgd2OAkcGVtoE3ThUREbio0Eg
Uc/prcajMKXvkCKFCWhJYJcLkcM2DKKcSeFpD/j6Boy538YXnR6VhcuUJOhH2x71
nzPjfdTcqMz7djHum0qSZA0AyCBDABUqCrfNgCiJ00Ra7GmRj+YCK1NJEuewlb40
JNrRuoEUXpabUzGB8QIDAQAB
-----END PUBLIC KEY-----`;
const COOKIE_INFO_URL = 'https://passport.bilibili.com/x/passport-login/web/cookie/info';
const COOKIE_REFRESH_URL = 'https://passport.bilibili.com/x/passport-login/web/cookie/refresh';
const CONFIRM_REFRESH_URL = 'https://passport.bilibili.com/x/passport-login/web/confirm/refresh';
const CORRESPOND_URL_PREFIX = 'https://www.bilibili.com/correspond/1/';
const BACKEND_VP_URL = 'http://127.0.0.1:8000/api/video-processing';
const PARTITION = 'persist:bilibili';
const AUTH_ERROR_CODES = new Set([-101, -111]);

let activeScheduler = null;

function generateCorrespondPath(timestampMs) {
  const encrypted = crypto.publicEncrypt(
    {
      key: BILIBILI_PUBLIC_KEY,
      padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
      oaepHash: 'sha256',
    },
    Buffer.from(`refresh_${timestampMs}`)
  );
  return encrypted.toString('hex');
}

function extractRefreshCsrf(html) {
  const m = String(html || '').match(/id=["']1-name["'][^>]*>([^<]+)/i);
  return m ? m[1].trim() : '';
}

function parseCookieHeader(cookieString) {
  const out = {};
  if (!cookieString) return out;
  for (const part of String(cookieString).split(';')) {
    const idx = part.indexOf('=');
    if (idx === -1) continue;
    const name = part.slice(0, idx).trim();
    const value = part.slice(idx + 1).trim();
    if (name) out[name] = value;
  }
  return out;
}

function cookiesToHeader(cookies) {
  return cookies.map((c) => `${c.name}=${c.value}`).join('; ');
}

function parseSetCookieLine(setCookieLine) {
  if (!setCookieLine) return null;
  const segments = String(setCookieLine).split(';');
  const first = segments[0];
  const eq = first.indexOf('=');
  if (eq === -1) return null;
  const name = first.slice(0, eq).trim();
  const value = first.slice(eq + 1).trim();
  if (!name) return null;

  const attrs = {
    name,
    value,
    path: '/',
    secure: false,
    httpOnly: false,
    domain: undefined,
  };

  for (let i = 1; i < segments.length; i++) {
    const part = segments[i].trim();
    if (!part) continue;
    const lower = part.toLowerCase();
    if (lower === 'secure') {
      attrs.secure = true;
      continue;
    }
    if (lower === 'httponly') {
      attrs.httpOnly = true;
      continue;
    }
    const aeq = part.indexOf('=');
    if (aeq === -1) continue;
    const key = part.slice(0, aeq).trim().toLowerCase();
    const val = part.slice(aeq + 1).trim();
    if (key === 'domain') attrs.domain = val;
    else if (key === 'path') attrs.path = val || '/';
  }

  return attrs;
}

function getSetCookieLines(response) {
  if (response.headers && typeof response.headers.getSetCookie === 'function') {
    try {
      const lines = response.headers.getSetCookie();
      if (Array.isArray(lines)) return lines;
    } catch (_) {
      // fall through
    }
  }
  const single = response.headers && response.headers.get
    ? response.headers.get('set-cookie')
    : null;
  if (!single) return [];
  // Best-effort fallback when getSetCookie is unavailable
  return [single];
}

function isAuthFailure(code, message) {
  if (AUTH_ERROR_CODES.has(code)) return true;
  const msg = String(message || '').toLowerCase();
  return (
    msg.includes('login') ||
    msg.includes('登录') ||
    msg.includes('not login') ||
    msg.includes('csrf') && code === -111
  );
}

async function applySetCookiesToSession(bilibiliSession, setCookieLines) {
  for (const line of setCookieLines) {
    const parsed = parseSetCookieLine(line);
    if (!parsed) continue;
    const cookieDetails = {
      url: 'https://www.bilibili.com',
      name: parsed.name,
      value: parsed.value,
      path: parsed.path || '/',
      secure: parsed.secure || parsed.name === 'SESSDATA',
      httpOnly: parsed.httpOnly || parsed.name === 'SESSDATA',
    };
    if (parsed.domain) {
      cookieDetails.domain = parsed.domain.startsWith('.')
        ? parsed.domain
        : parsed.domain;
    } else {
      cookieDetails.domain = '.bilibili.com';
    }
    try {
      await bilibiliSession.cookies.set(cookieDetails);
    } catch (err) {
      console.warn(
        '[cookie-refresh] Failed to set cookie',
        parsed.name,
        err && err.message ? err.message : err
      );
    }
  }
}

class CookieRefreshScheduler {
  constructor({ getMainWindow } = {}) {
    this.getMainWindow = getMainWindow || (() => null);
    this.intervalId = null;
    this.refreshToken = '';
    this.refreshing = false;
    activeScheduler = this;
  }

  setRefreshToken(token) {
    this.refreshToken = token || '';
  }

  async _tryReloadTokenFromBackend() {
    try {
      const res = await fetch(BACKEND_VP_URL);
      if (!res.ok) return;
      const data = await res.json();
      if (data.bilibili_refresh_token) {
        this.refreshToken = data.bilibili_refresh_token;
        console.log('[cookie-refresh] reloaded refresh_token from backend');
      }
    } catch (e) {
      // ignore — next interval will retry
    }
  }

  start() {
    console.log('[cookie-refresh] Starting CookieRefreshScheduler');
    this.checkAndRefresh();
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
    if (!this.refreshToken) {
      await this._tryReloadTokenFromBackend();
    }
    try {
      const result = await this.refreshIfNeeded();
      console.log(
        '[cookie-refresh] check result:',
        result.ok,
        result.refreshed,
        result.reason || ''
      );
    } catch (error) {
      console.error(
        '[cookie-refresh] Error during cookie refresh check:',
        error && error.message ? error.message : error
      );
    }
  }

  async refreshIfNeeded() {
    if (this.refreshing) {
      return { ok: true, refreshed: false, reason: 'busy' };
    }
    this.refreshing = true;
    try {
      return await this._doRefreshIfNeeded();
    } finally {
      this.refreshing = false;
    }
  }

  async _doRefreshIfNeeded() {
    const bilibiliSession = getSession().fromPartition(PARTITION, { cache: true });
    const cookies = await bilibiliSession.cookies.get({});
    const sessdata = cookies.find((c) => c.name === 'SESSDATA');
    const biliJct = cookies.find((c) => c.name === 'bili_jct');

    if (!sessdata || !biliJct) {
      return { ok: false, refreshed: false, reason: 'not_logged_in' };
    }
    if (!this.refreshToken) {
      return { ok: true, refreshed: false, reason: 'no_refresh_token' };
    }

    const oldRefreshToken = this.refreshToken;
    let cookieHeader = cookiesToHeader(cookies);

    // 1) cookie/info
    let infoJson;
    try {
      const infoUrl = `${COOKIE_INFO_URL}?csrf=${encodeURIComponent(biliJct.value)}`;
      const infoRes = await fetch(infoUrl, {
        method: 'GET',
        headers: {
          Cookie: cookieHeader,
          Referer: 'https://www.bilibili.com/',
        },
      });
      infoJson = await infoRes.json();
    } catch (err) {
      console.warn(
        '[cookie-refresh] cookie/info request failed:',
        err && err.message ? err.message : err
      );
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }

    if (infoJson && isAuthFailure(infoJson.code, infoJson.message)) {
      return { ok: false, refreshed: false, reason: 'auth_expired' };
    }
    if (!infoJson || infoJson.code !== 0 || !infoJson.data) {
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }
    if (!infoJson.data.refresh) {
      return { ok: true, refreshed: false };
    }

    const timestampMs = infoJson.data.timestamp;
    if (timestampMs == null) {
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }

    // 2) correspondPath + fetch refresh_csrf
    let refreshCsrf = '';
    try {
      const correspondPath = generateCorrespondPath(timestampMs);
      const correspondRes = await fetch(
        `${CORRESPOND_URL_PREFIX}${correspondPath}`,
        {
          method: 'GET',
          headers: {
            Cookie: cookieHeader,
            Referer: 'https://www.bilibili.com/',
          },
        }
      );
      const html = await correspondRes.text();
      refreshCsrf = extractRefreshCsrf(html);
    } catch (err) {
      console.warn(
        '[cookie-refresh] correspond request failed:',
        err && err.message ? err.message : err
      );
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }
    if (!refreshCsrf) {
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }

    // 3) POST cookie/refresh
    let refreshJson;
    let setCookieLines = [];
    try {
      const body = new URLSearchParams({
        csrf: biliJct.value,
        refresh_csrf: refreshCsrf,
        source: 'main_web',
        refresh_token: oldRefreshToken,
      });
      const refreshRes = await fetch(COOKIE_REFRESH_URL, {
        method: 'POST',
        headers: {
          Cookie: cookieHeader,
          'Content-Type': 'application/x-www-form-urlencoded',
          Referer: 'https://www.bilibili.com/',
        },
        body: body.toString(),
      });
      setCookieLines = getSetCookieLines(refreshRes);
      refreshJson = await refreshRes.json();
    } catch (err) {
      console.warn(
        '[cookie-refresh] cookie/refresh request failed:',
        err && err.message ? err.message : err
      );
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }

    if (refreshJson && isAuthFailure(refreshJson.code, refreshJson.message)) {
      return { ok: false, refreshed: false, reason: 'auth_expired' };
    }
    if (!refreshJson || refreshJson.code !== 0 || !refreshJson.data) {
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }

    const newRefreshToken = refreshJson.data.refresh_token;
    if (!newRefreshToken) {
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }

    // 4) Apply Set-Cookie to Electron jar
    if (setCookieLines.length > 0) {
      await applySetCookiesToSession(bilibiliSession, setCookieLines);
    }

    // Re-read jar and require usable SESSDATA + bili_jct before rotating token
    const updatedCookies = await bilibiliSession.cookies.get({});
    const newSessdata = updatedCookies.find((c) => c.name === 'SESSDATA');
    const newBiliJct = updatedCookies.find((c) => c.name === 'bili_jct');
    if (!newSessdata || !newSessdata.value || !newBiliJct || !newBiliJct.value) {
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }
    // Empty Set-Cookie + unchanged SESSDATA means refresh did not deliver new cookies
    if (
      setCookieLines.length === 0 &&
      newSessdata.value === sessdata.value
    ) {
      return { ok: false, refreshed: false, reason: 'upstream_error' };
    }
    cookieHeader = cookiesToHeader(updatedCookies);

    // 5) POST confirm/refresh with NEW bili_jct + OLD refresh_token
    try {
      const confirmBody = new URLSearchParams({
        csrf: newBiliJct.value,
        refresh_token: oldRefreshToken,
      });
      const confirmRes = await fetch(CONFIRM_REFRESH_URL, {
        method: 'POST',
        headers: {
          Cookie: cookieHeader,
          'Content-Type': 'application/x-www-form-urlencoded',
          Referer: 'https://www.bilibili.com/',
        },
        body: confirmBody.toString(),
      });
      const confirmJson = await confirmRes.json().catch(() => null);
      if (confirmJson && isAuthFailure(confirmJson.code, confirmJson.message)) {
        return { ok: false, refreshed: false, reason: 'auth_expired' };
      }
      if (confirmJson && confirmJson.code !== 0) {
        console.warn(
          '[cookie-refresh] confirm/refresh non-zero code:',
          confirmJson.code
        );
        // Soft-continue: cookies already rotated; confirm is best-effort for invalidating old token
      }
    } catch (err) {
      console.warn(
        '[cookie-refresh] confirm/refresh request failed:',
        err && err.message ? err.message : err
      );
      // Soft-continue: jar already updated
    }

    // 6) Final cookie string from jar
    const finalCookies = await bilibiliSession.cookies.get({});
    const cookieString = cookiesToHeader(finalCookies);

    this.setRefreshToken(newRefreshToken);

    // 7) Emit to renderer
    try {
      const win = this.getMainWindow && this.getMainWindow();
      if (win && !win.isDestroyed()) {
        win.webContents.send('cookie-refreshed', {
          platform: 'bilibili',
          cookies: cookieString,
          refresh_token: newRefreshToken,
        });
      }
    } catch (err) {
      console.warn(
        '[cookie-refresh] Failed to emit cookie-refreshed:',
        err && err.message ? err.message : err
      );
    }

    // 8) Backend write-back (soft-fail)
    try {
      const putRes = await fetch(BACKEND_VP_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bilibili_cookie: cookieString,
          bilibili_refresh_token: newRefreshToken,
        }),
      });
      if (!putRes.ok) {
        console.warn(
          '[cookie-refresh] Backend write-back HTTP',
          putRes.status
        );
      }
    } catch (e) {
      console.warn(
        '[cookie-refresh] Backend write-back failed:',
        e && e.message ? e.message : e
      );
    }

    return { ok: true, refreshed: true };
  }
}

function setActiveRefreshToken(token) {
  if (activeScheduler) activeScheduler.setRefreshToken(token);
}

module.exports = {
  CookieRefreshScheduler,
  generateCorrespondPath,
  extractRefreshCsrf,
  parseCookieHeader,
  setActiveRefreshToken,
};
