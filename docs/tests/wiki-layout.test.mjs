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
  assert.match(index, /\bsubMaxLevel\s*:\s*0\b/, 'Docsify subMaxLevel must be zero');
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
});
