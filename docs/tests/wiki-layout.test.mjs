import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const docsDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const readDoc = (name) => readFileSync(resolve(docsDir, name), 'utf8');

test('Docsify config and header expose the approved global shell', () => {
  const index = readDoc('index.html');
  const header = index.match(/<header\b[^>]*>[\s\S]*?<\/header>/i)?.[0];
  const searchSlot = header?.match(/<[^>]*\bid\s*=\s*(['"])wiki-search\1[^>]*>/i)?.[0];
  const scripts = [...index.matchAll(/<script\b[^>]*>[\s\S]*?<\/script>/gi)].map((match) => match[0]);
  const searchPluginIndex = scripts.findIndex((script) =>
    /\bsrc\s*=\s*(['"])[^'"]*\/plugins\/search\.min\.js\1/i.test(script),
  );
  const mountScriptIndex = scripts.findIndex((script) =>
    /document\.getElementById\(\s*(['"])wiki-search\1\s*\)/i.test(script),
  );
  const themeScriptIndex = scripts.findIndex((script) =>
    /localStorage\.getItem\(\s*(['"])memento-theme\1\s*\)/i.test(script),
  );
  const mountScript = scripts[mountScriptIndex] ?? '';

  assert.ok(header, 'global shell must include a header element');
  assert.match(
    header,
    /<a\b[^>]*\bhref\s*=\s*(['"])#\/\1[^>]*>/i,
    'global header must include a home link to "#/"',
  );
  assert.ok(searchSlot, 'global header must include the wiki-search slot');
  assert.match(searchSlot, /\brole\s*=\s*(['"])search\1/i, 'wiki-search slot must expose the search landmark');
  assert.match(index, /\bname\s*:\s*(['"])\1/, 'Docsify name must be empty');
  assert.match(index, /\bsubMaxLevel\s*:\s*3\b/, 'Docsify must show article headings through level three');
  assert.match(
    index,
    /\bplaceholder\s*:\s*(['"])搜索文档…\1/,
    'Docsify search must expose the approved placeholder',
  );
  assert.match(
    index,
    /\bnoData\s*:\s*(['"])没有找到相关内容\1/,
    'Docsify search must expose the approved empty-state message',
  );
  assert.match(
    index,
    /<script\b[^>]*>(?:(?!<\/script>)[\s\S])*?\b(?:const|let|var)\s+target\s*=\s*document\.getElementById\(\s*(['"])wiki-search\1\s*\)\s*;?(?:(?!<\/script>)[\s\S])*?\bfunction\s+mountSearch\s*\(\s*\)\s*\{[^}]*?\b(?:const|let|var)\s+search\s*=\s*document\.querySelector\(\s*(['"])\.sidebar \.search\2\s*\)\s*;?[^}]*?\btarget\.appendChild\(\s*search\s*\)\s*;?[^}]*?\}(?:(?!<\/script>)[\s\S])*?\b(?:const|let|var)\s+observer\s*=\s*new\s+MutationObserver\(\s*(?:function\s*\([^)]*\)|\([^)]*\)\s*=>)\s*\{\s*if\s*\(\s*mountSearch\(\s*\)\s*\)\s*(?:\{\s*observer\.disconnect\(\s*\)\s*;?\s*\}|observer\.disconnect\(\s*\)\s*;?)\s*\}\s*\)\s*;?(?:(?!<\/script>)[\s\S])*?\bobserver\.observe\(\s*document\.body\s*,\s*\{\s*\bchildList\b\s*:\s*true\s*,\s*\bsubtree\b\s*:\s*true\s*,?\s*\}\s*\)\s*;?(?:(?!<\/script>)[\s\S])*?<\/script>/i,
    'one script must mount Docsify search into wiki-search and stop observing after success',
  );
  assert.match(
    mountScript,
    /\b(?:const|let|var)\s+input\s*=\s*search\.querySelector\(\s*(['"])input\1\s*\)\s*;?[\s\S]*?\bif\s*\(\s*input\s*\)\s*input\.setAttribute\(\s*(['"])aria-label\2\s*,\s*(['"])文档搜索\3\s*\)\s*;?[\s\S]*?target\.appendChild\(\s*search\s*\)/i,
    'mountSearch must label the real search input before moving its container',
  );
  assert.ok(
    searchPluginIndex >= 0 && searchPluginIndex < mountScriptIndex && mountScriptIndex < themeScriptIndex,
    'search plugin, mount script, and theme script must remain in lifecycle order',
  );
  assert.match(
    mountScript,
    /\bobserver\.observe\([\s\S]*?\bwindow\.addEventListener\(\s*(['"])load\1\s*,\s*function\s*\(\s*\)\s*\{\s*mountSearch\(\s*\)\s*;?\s*observer\.disconnect\(\s*\)\s*;?\s*\}\s*,\s*\{\s*once\s*:\s*true\s*,?\s*\}\s*\)\s*;?/i,
    'observer must make one final load-time mount attempt and then disconnect',
  );
  assert.match(
    index,
    /\blocalStorage\.getItem\(\s*(['"])memento-theme\1\s*\)/,
    'theme initialization must read memento-theme from localStorage',
  );
  assert.match(
    index,
    /\blocalStorage\.setItem\(\s*(['"])memento-theme\1\s*,/,
    'theme changes must write memento-theme to localStorage',
  );
  assert.match(
    index,
    /function\s+syncSidebarActive\(\s*\)\s*\{[\s\S]*?location\.hash[\s\S]*?\.split\(\s*(['"])\?\1\s*\)\s*\[\s*0\s*\][\s\S]*?document\.querySelectorAll\(\s*(['"])\.sidebar-nav a\2\s*\)[\s\S]*?classList\.toggle\(\s*(['"])active\3\s*,\s*linkRoute\s*===\s*route\s*\)[\s\S]*?new\s+MutationObserver\(\s*syncSidebarActive\s*\)[\s\S]*?observer\.observe\(\s*document\.body\s*,\s*\{[\s\S]*?attributes\s*:\s*true[\s\S]*?attributeFilter\s*:\s*\[\s*(['"])class\4\s*\][\s\S]*?childList\s*:\s*true[\s\S]*?subtree\s*:\s*true[\s\S]*?\}\s*\)/i,
    'Docsify must keep the current route highlighted when the sidebar is rendered',
  );
  assert.match(
    index,
    /link\.closest\(\s*(['"])\.app-sub-sidebar\1\s*\)[\s\S]*?classList\.toggle\(\s*(['"])active\2\s*,\s*link\.getAttribute\(\s*(['"])href\3\s*\)\s*===\s*current\s*\)/,
    'only the article heading matching the current anchor may be highlighted',
  );
});

test('Sidebar keeps existing pages and uses semantic group labels', () => {
  const sidebar = readDoc('_sidebar.md');

  for (const group of ['系统', '数据', '对话']) {
    assert.match(
      sidebar,
      new RegExp(`^\\s*-\\s+\\*\\*${group}\\*\\*\\s*$`, 'm'),
      `sidebar must include the semantic ${group} group label`,
    );
  }

  for (const page of ['系统总览', '独立服务与配置', '视频摄入流水线', '存储与检索', '记忆系统架构']) {
    assert.match(sidebar, new RegExp(page), `sidebar must keep the existing ${page} page`);
  }

  assert.doesNotMatch(sidebar, /快速开始/, 'sidebar must not introduce a 快速开始 page');
  assert.doesNotMatch(sidebar, /使用指南/, 'sidebar must not introduce a 使用指南 page');
});

test('CSS defines the centered Structured Blue desktop shell', () => {
  const css = readDoc('custom.css');

  for (const [name, value] of [
    ['--wiki-shell-width', '1180px'],
    ['--wiki-shell-half', '590px'],
    ['--wiki-sidebar-width', '272px'],
    ['--wiki-nav-height', '56px'],
    ['--active-bg', '#e6f0ff'],
  ]) {
    assert.match(
      css,
      new RegExp(`${name}\\s*:\\s*${value.replace('#', '\\#')}\\s*;`, 'i'),
      `CSS must define ${name}: ${value}`,
    );
  }

  assert.match(
    css,
    /\.sidebar\s*\{(?=[^}]*\bleft\s*:\s*var\(\s*--wiki-shell-edge\s*\)(?:\s*!important)?\s*;)[^}]*\}/i,
    'desktop sidebar must align to --wiki-shell-edge',
  );
  assert.match(
    css,
    /\.wiki-nav-inner\s*\{(?=[^}]*\bgrid-template-columns\s*:\s*var\(\s*--wiki-sidebar-width\s*\)\s+minmax\(\s*0\s*,\s*1fr\s*\)\s+36px\s*;)[^}]*\}/i,
    'desktop header must use the sidebar, fluid content, and action grid columns',
  );
  assert.match(css, /\.sidebar-nav\s+li\s*>\s*strong\s*\{/i, 'sidebar groups must target semantic strong labels');
  assert.match(css, /\.sidebar-nav\s+\.app-sub-sidebar\s*\{/i, 'article headings must have a dedicated sidebar style');
  assert.match(
    css,
    /\.sidebar-nav\s+a\s*\{(?=[^}]*\bmin-height\s*:\s*40px(?:\s*!important)?\s*;)[^}]*\}/i,
    'desktop sidebar links must have a 40px minimum height',
  );
  assert.match(
    css,
    /\.sidebar-nav\s*\{(?=[^}]*\boverflow-y\s*:\s*auto(?:\s*!important)?\s*;)[^}]*\}/i,
    'sidebar navigation must scroll independently',
  );
  assert.match(
    css,
    /\.markdown-section\s*\{(?=[^}]*\bmax-width\s*:\s*908px(?:\s*!important)?\s*;)[^}]*\}/i,
    'desktop article content must be capped at 908px',
  );
  assert.match(
    css,
    /\.wiki-nav-search\s+\.search(?:\s*,[^{}]*)?\s*\{/i,
    'Docsify search styles must be scoped beneath wiki-nav-search',
  );
  assert.match(
    css,
    /\.markdown-section\s+table\s*\{(?=[^}]*\bdisplay\s*:\s*block(?:\s*!important)?\s*;)(?=[^}]*\boverflow-x\s*:\s*auto(?:\s*!important)?\s*;)[^}]*\}/i,
    'markdown tables must be block scroll containers so they cannot widen the page',
  );
});

test('CSS switches to an overlay drawer below 1024px', () => {
  const css = readDoc('custom.css');
  const mediaMatch = /@media\s*\(\s*max-width\s*:\s*1023px\s*\)\s*\{/i.exec(css);

  assert.ok(mediaMatch, 'CSS must define the responsive region at max-width: 1023px');

  const openingBrace = css.indexOf('{', mediaMatch.index);
  let depth = 0;
  let closingBrace = -1;

  for (let index = openingBrace; index < css.length; index += 1) {
    if (css[index] === '{') depth += 1;
    if (css[index] === '}' && --depth === 0) {
      closingBrace = index;
      break;
    }
  }

  assert.notEqual(closingBrace, -1, 'responsive region must have a closing brace');
  const responsiveCss = css.slice(openingBrace + 1, closingBrace);

  assert.match(
    responsiveCss,
    /\.sidebar\s*\{(?=[^}]*\bwidth\s*:\s*min\(\s*320px\s*,\s*86vw\s*\)(?:\s*!important)?\s*;)(?=[^}]*\btransform\s*:\s*translateX\(\s*-100%\s*\)(?:\s*!important)?\s*;)[^}]*\}/i,
    'responsive sidebar must be a hidden min(320px, 86vw) overlay drawer',
  );
  assert.match(
    responsiveCss,
    /body:not\(\.close\)\s+\.sidebar\s*\{(?=[^}]*\btransform\s*:\s*translateX\(\s*0\s*\)(?:\s*!important)?\s*;)[^}]*\}/i,
    'open responsive drawer must translate the sidebar into view',
  );
  assert.match(
    responsiveCss,
    /\.sidebar-toggle\s*\{(?=[^}]*\btop\s*:\s*10px(?:\s*!important)?\s*;)[^}]*\}/i,
    'responsive sidebar toggle must sit 10px from the top',
  );
  assert.match(
    responsiveCss,
    /\.sidebar-nav\s+a\s*\{(?=[^}]*\bmin-height\s*:\s*44px(?:\s*!important)?\s*;)[^}]*\}/i,
    'responsive sidebar links must expose a 44px touch target',
  );
});
