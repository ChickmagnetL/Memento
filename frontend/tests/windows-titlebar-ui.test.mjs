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

test("Windows drag strip does not cover the chat header controls", () => {
  const dragRule = globalsSource.match(
    /html\[data-platform="win32"\] \.desktop-drag-region \{[\s\S]*?\}/
  )?.[0] ?? "";

  assert.match(dragRule, /height:\s*8px/);
  assert.match(dragRule, /margin-bottom:\s*-8px/);
  assert.doesNotMatch(dragRule, /height:\s*48px/);
});

test("Windows chat memory control stays clear of native window buttons", () => {
  assert.match(
    globalsSource,
    /html\[data-platform="win32"\] \.desktop-window-controls-safe \{[\s\S]*?margin-right:\s*var\(--window-controls-width\)/
  );
  assert.match(
    chatPanelSource,
    /className="desktop-window-controls-safe flex justify-end"/
  );
});
