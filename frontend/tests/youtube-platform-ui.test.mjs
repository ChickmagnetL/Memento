import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const apiSource = readFileSync(join(__dirname, "../src/lib/api.ts"), "utf8");
const intakeSource = readFileSync(
  join(__dirname, "../src/app/video-intake.tsx"),
  "utf8"
);
const timestampLinkSource = readFileSync(
  join(__dirname, "../src/components/VideoTimestampLink.tsx"),
  "utf8"
);
const subtitleDialogSource = readFileSync(
  join(__dirname, "../src/components/ui/subtitle-decision-dialog.tsx"),
  "utf8"
);

test("YouTube is a visible supported video platform", () => {
  assert.match(apiSource, /VideoPlatform = "bilibili" \| "douyin" \| "youtube"/);
  assert.match(intakeSource, /Bilibili, Douyin, or YouTube URL/);
  assert.match(intakeSource, /video\.platform === "youtube"[\s\S]*?"YouTube"/);
});

test("YouTube uses subtitle precheck and timestamp player links", () => {
  assert.match(
    intakeSource,
    /video\.status === "completed" && video\.platform === "douyin"/
  );
  assert.match(timestampLinkSource, /platform !== "youtube"/);
});

test("subtitle choices display human-readable language names", () => {
  assert.match(subtitleDialogSource, /Intl\.DisplayNames/);
  assert.match(subtitleDialogSource, /t\("Available: \{languages\}\."/);
});
