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

test("desktop drag strip is available on macOS and Windows without covering header controls", () => {
  const dragRule = globalsSource.match(
    /html\[data-platform="darwin"\] \.desktop-drag-region,\s*html\[data-platform="win32"\] \.desktop-drag-region \{[\s\S]*?\}/
  )?.[0] ?? "";

  assert.notEqual(dragRule, "");
  assert.match(dragRule, /height:\s*8px/);
  assert.match(dragRule, /margin-bottom:\s*-8px/);
  assert.doesNotMatch(dragRule, /height:\s*48px/);
});

test("chat memory control sits directly after the new-chat control", () => {
  const newChatControl = chatPanelSource.indexOf('title="New Chat"');
  const memoryControl = chatPanelSource.indexOf("<MemoryPopover", newChatControl);
  const centeredControlsEnd = chatPanelSource.indexOf("</div>", memoryControl);

  assert.notEqual(newChatControl, -1);
  assert.notEqual(memoryControl, -1);
  assert.ok(memoryControl < centeredControlsEnd);
  assert.doesNotMatch(chatPanelSource, /desktop-window-controls-safe/);
});
