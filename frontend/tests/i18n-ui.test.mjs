import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const i18nSource = readFileSync(join(__dirname, "../src/lib/i18n.tsx"), "utf8");
const layoutSource = readFileSync(join(__dirname, "../src/app/layout.tsx"), "utf8");
const settingsSource = readFileSync(
  join(__dirname, "../src/app/settings/settings-form.tsx"),
  "utf8",
);
const sidebarSource = readFileSync(
  join(__dirname, "../src/components/layout/sidebar.tsx"),
  "utf8",
);

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filePath = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(filePath);
    return /\.(ts|tsx)$/.test(entry.name) ? [filePath] : [];
  });
}

test("language preference uses saved choice before the system locale", () => {
  assert.match(i18nSource, /localStorage\.getItem\(STORAGE_KEY\)/);
  assert.match(i18nSource, /navigator\.language\.toLowerCase\(\)\.startsWith\("zh"\)/);
  assert.match(
    i18nSource,
    /stored === "en" \|\| stored === "zh-CN" \? stored : detected/,
  );
});

test("language changes persist and update the document locale", () => {
  assert.match(i18nSource, /localStorage\.setItem\(STORAGE_KEY, next\)/);
  assert.match(i18nSource, /document\.documentElement\.lang = language/);
  assert.match(layoutSource, /<LanguageProvider>[\s\S]*?<Sidebar/);
});

test("settings exposes both languages and shared UI uses translations", () => {
  assert.match(settingsSource, /\{ name: "general", label: "General" \}/);
  assert.match(settingsSource, /activeTab === "general" \? \(/);
  assert.match(settingsSource, /<option value="zh-CN">简体中文<\/option>/);
  assert.match(settingsSource, /<option value="en">English<\/option>/);
  assert.match(settingsSource, /onChange=\{\(event\) => setLanguage/);
  assert.match(sidebarSource, /\{t\(label\)\}/);
  assert.match(i18nSource, /"General": "通用"/);
  assert.match(i18nSource, /"Settings": "设置"/);
});

test("translation interpolation preserves dynamic values", () => {
  assert.match(i18nSource, /text\.replace\(\/\\\{\(\\w\+\)\\\}\/g/);
  assert.match(i18nSource, /"Calling tool: \{tool\}…": "正在调用工具：\{tool\}…"/);
});

test("every literal translation key has a Chinese catalog entry", () => {
  const catalogBlock = i18nSource.match(
    /const zhCN[^=]*= \{([\s\S]*?)\n\};/,
  )?.[1] ?? "";
  const catalog = new Set(
    [...catalogBlock.matchAll(/^\s*("(?:\\.|[^"\\])*"):/gm)].map((match) =>
      JSON.parse(match[1]),
    ),
  );
  const missing = new Set();

  for (const filePath of sourceFiles(join(__dirname, "../src"))) {
    const source = readFileSync(filePath, "utf8");
    for (const match of source.matchAll(/\bt\(\s*("(?:\\.|[^"\\])*")/g)) {
      const key = JSON.parse(match[1]);
      if (!catalog.has(key)) missing.add(key);
    }
  }

  assert.deepEqual([...missing], []);
});
