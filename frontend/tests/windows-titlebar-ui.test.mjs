import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const globalsSource = readFileSync(
  join(__dirname, "../src/app/globals.css"),
  "utf8"
);
const chatPanelSource = readFileSync(
  join(__dirname, "../src/app/chat/chat-panel.tsx"),
  "utf8"
);
const sidebarSource = readFileSync(
  join(__dirname, "../src/components/layout/sidebar.tsx"),
  "utf8"
);

test("desktop drag strip is available on macOS and Windows without covering header controls", () => {
  const dragRule = globalsSource.match(
    /html\[data-platform="darwin"\] \.desktop-drag-region,\s*html\[data-platform="win32"\] \.desktop-drag-region \{[\s\S]*?\}/
  )?.[0] ?? "";

  assert.notEqual(dragRule, "");
  assert.match(dragRule, /height:\s*8px/);
  assert.match(dragRule, /margin-bottom:\s*-8px/);
  assert.doesNotMatch(dragRule, /height:\s*48px/);
});

test("chat header itself provides a reliable desktop drag surface", () => {
  const titlebarRule = globalsSource.match(
    /\.desktop-titlebar \{[\s\S]*?\}/
  )?.[0] ?? "";

  assert.match(chatPanelSource, /<header className="desktop-titlebar /);
  assert.match(titlebarRule, /-webkit-app-region:\s*drag/);
});

test("interactive chat header controls are excluded from the drag surface", () => {
  const noDragRule = globalsSource.match(
    /\.desktop-titlebar :is\([\s\S]*?\) \{[\s\S]*?\}/
  )?.[0] ?? "";

  assert.match(noDragRule, /button/);
  assert.match(noDragRule, /input/);
  assert.match(noDragRule, /\[role="dialog"\]/);
  assert.match(noDragRule, /-webkit-app-region:\s*no-drag/);
});

test("expanded and collapsed sidebar headers provide drag surfaces", () => {
  const sidebarTitlebarRule = globalsSource.match(
    /\.desktop-sidebar-titlebar \{[\s\S]*?\}/
  )?.[0] ?? "";
  const sidebarHeaders = sidebarSource.match(
    /className="desktop-sidebar-titlebar /g
  ) ?? [];

  assert.equal(sidebarHeaders.length, 2);
  assert.match(sidebarTitlebarRule, /-webkit-app-region:\s*drag/);
  assert.match(
    globalsSource,
    /\.desktop-sidebar-titlebar :is\(button, a\) \{[\s\S]*?-webkit-app-region:\s*no-drag/
  );
});

test("chat memory control sits directly after the new-chat control", () => {
  const newChatControl = chatPanelSource.indexOf('title={t("New Chat")}');
  const memoryControl = chatPanelSource.indexOf("<MemoryPopover", newChatControl);
  const centeredControlsEnd = chatPanelSource.indexOf("</div>", memoryControl);

  assert.notEqual(newChatControl, -1);
  assert.notEqual(memoryControl, -1);
  assert.ok(memoryControl < centeredControlsEnd);
  assert.doesNotMatch(chatPanelSource, /desktop-window-controls-safe/);
});
