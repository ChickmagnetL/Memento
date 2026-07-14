const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');

const {
  DOUYIN_AUTO_LOGIN_JS,
  LoginWindowManager,
  configureAuthNavigationGuards,
  sanitizeUserAgent,
} = require('../login-manager');

test('auth navigation blocks custom protocols without blocking HTTPS', () => {
  const handlers = {};
  let windowOpenHandler = null;
  const webContents = {
    on: (event, handler) => { handlers[event] = handler; },
    setWindowOpenHandler: (handler) => { windowOpenHandler = handler; },
  };
  configureAuthNavigationGuards(webContents, '/tmp/icon.png');

  let prevented = false;
  handlers['will-frame-navigate']({
    url: 'bytedance://dispatch_message/',
    preventDefault: () => { prevented = true; },
  });
  assert.equal(prevented, true);

  prevented = false;
  handlers['will-frame-navigate']({
    url: 'https://www.douyin.com/passport/login',
    preventDefault: () => { prevented = true; },
  });
  assert.equal(prevented, false);

  handlers['will-navigate'](
    { preventDefault: () => { prevented = true; } },
    'bitbrowser://cc/',
  );
  assert.equal(prevented, true);
  assert.deepEqual(windowOpenHandler({ url: 'bitbrowser://cc/' }), { action: 'deny' });

  prevented = false;
  handlers['will-redirect'](
    { preventDefault: () => { prevented = true; } },
    'https://www.douyin.com/passport/login',
  );
  assert.equal(prevented, false);
  assert.deepEqual(
    windowOpenHandler({ url: 'https://www.douyin.com/passport/login' }),
    {
      action: 'allow',
      overrideBrowserWindowOptions: { icon: '/tmp/icon.png' },
    },
  );
});

test('Douyin login script clicks the current pointer div login control', () => {
  class FakeHTMLElement {}
  const loginControl = new FakeHTMLElement();
  loginControl.textContent = ' 登录 ';
  loginControl.getBoundingClientRect = () => ({ width: 64, height: 32 });
  let clicked = false;
  loginControl.click = () => { clicked = true; };
  const context = {
    HTMLElement: FakeHTMLElement,
    document: {
      querySelector: () => null,
      querySelectorAll: (selector) => selector.includes('div') ? [loginControl] : [],
    },
    window: {
      getComputedStyle: () => ({
        cursor: 'pointer',
        display: 'flex',
        visibility: 'visible',
      }),
    },
  };

  const result = vm.runInNewContext(DOUYIN_AUTO_LOGIN_JS, context);

  assert.equal(result, 'clicked');
  assert.equal(clicked, true);
});

test('Douyin login retries until the dialog is visible before injecting CSS', async () => {
  const manager = new LoginWindowManager({});
  const results = ['missing', 'clicked', 'ready'];
  const injected = [];
  let calls = 0;
  manager.authView = {
    webContents: {
      isDestroyed: () => false,
      executeJavaScript: async () => {
        calls += 1;
        return results.shift();
      },
    },
  };
  manager.injectPlatformCSS = (platform) => injected.push(platform);

  const ready = await manager.triggerDouyinLogin({
    maxAttempts: 3,
    retryDelayMs: 0,
  });

  assert.equal(ready, true);
  assert.equal(calls, 3);
  assert.deepEqual(injected, ['douyin']);
});

test('Douyin login leaves the homepage visible when no trigger is found', async () => {
  const manager = new LoginWindowManager({});
  const injected = [];
  manager.authView = {
    webContents: {
      isDestroyed: () => false,
      executeJavaScript: async () => 'missing',
    },
  };
  manager.injectPlatformCSS = (platform) => injected.push(platform);

  const ready = await manager.triggerDouyinLogin({
    maxAttempts: 2,
    retryDelayMs: 0,
  });

  assert.equal(ready, false);
  assert.deepEqual(injected, []);
});

test('Douyin auth view removes Electron from its browser user agent', () => {
  const userAgent = sanitizeUserAgent(
    'Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36 Electron/33.4.11',
  );

  assert.equal(userAgent, 'Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36');
});
