import { readFileSync } from "node:fs";

const videoIntake = readFileSync("src/app/video-intake.tsx", "utf8");

const handleProcessStart = videoIntake.indexOf("async function handleProcess");
if (handleProcessStart === -1) {
  console.error("FAIL: handleProcess() was not found in video-intake.tsx");
  process.exit(1);
}

const handleProcessBody = videoIntake.slice(handleProcessStart);

// Non-bilibili completed may still bypass pre-check
const nonBiliCompletedBypass =
  /if\s*\(\s*video\.status\s*===\s*"completed"\s*&&\s*video\.platform\s*!==\s*"bilibili"\s*\)\s*\{\s*await\s+runProcess\(video\.id\);\s*return;\s*\}/s;

if (!nonBiliCompletedBypass.test(handleProcessBody)) {
  console.error(
    "FAIL: non-bilibili completed videos should still bypass subtitle pre-check"
  );
  process.exit(1);
}

// Bilibili completed must NOT unconditionally bypass (old behavior)
const unconditionalCompletedBypass =
  /if\s*\(\s*video\.status\s*===\s*"completed"\s*\)\s*\{\s*await\s+runProcess\(video\.id\);\s*return;\s*\}/s;

if (unconditionalCompletedBypass.test(handleProcessBody)) {
  console.error(
    "FAIL: bilibili completed videos must run subtitle pre-check (no unconditional completed bypass)"
  );
  process.exit(1);
}

// First-time / bilibili processing should keep the subtitle pre-check flow
const hasSubtitleCheck =
  handleProcessBody.includes("const result = await checkSubtitles(video.id);") ||
  handleProcessBody.includes("let result = await checkSubtitles(video.id);");

if (!hasSubtitleCheck) {
  console.error(
    "FAIL: first-time processing should still keep the subtitle pre-check flow"
  );
  process.exit(1);
}

// Soft process failures should map to SubtitleDecisionDialog
if (!videoIntake.includes("function mapSoftSubtitleError")) {
  console.error(
    "FAIL: mapSoftSubtitleError helper is required for soft process failures"
  );
  process.exit(1);
}

if (!videoIntake.includes("setPendingSubtitleDecision")) {
  console.error(
    "FAIL: soft failures should open SubtitleDecisionDialog via setPendingSubtitleDecision"
  );
  process.exit(1);
}

console.log(
  "Non-bilibili completed re-process bypasses pre-check; bilibili always prechecks; soft failures map to dialog."
);
