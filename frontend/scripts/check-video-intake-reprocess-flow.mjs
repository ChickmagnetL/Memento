import { readFileSync } from "node:fs";

const videoIntake = readFileSync("src/app/video-intake.tsx", "utf8");

const handleProcessStart = videoIntake.indexOf("async function handleProcess");
if (handleProcessStart === -1) {
  console.error("FAIL: handleProcess() was not found in video-intake.tsx");
  process.exit(1);
}

const handleProcessBody = videoIntake.slice(handleProcessStart);

// Douyin completed may bypass pre-check because it has no subtitle path.
const douyinCompletedBypass =
  /if\s*\(\s*video\.status\s*===\s*"completed"\s*&&\s*video\.platform\s*===\s*"douyin"\s*\)\s*\{\s*await\s+runProcess\(video\.id\);\s*return;\s*\}/s;

if (!douyinCompletedBypass.test(handleProcessBody)) {
  console.error(
    "FAIL: completed Douyin videos should bypass subtitle pre-check"
  );
  process.exit(1);
}

// Bilibili and YouTube completed videos must NOT unconditionally bypass.
const unconditionalCompletedBypass =
  /if\s*\(\s*video\.status\s*===\s*"completed"\s*\)\s*\{\s*await\s+runProcess\(video\.id\);\s*return;\s*\}/s;

if (unconditionalCompletedBypass.test(handleProcessBody)) {
  console.error(
    "FAIL: Bilibili and YouTube completed videos must run subtitle pre-check"
  );
  process.exit(1);
}

// First-time, Bilibili, and YouTube processing should keep the subtitle pre-check flow.
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
  "Douyin completed re-process bypasses pre-check; Bilibili and YouTube always precheck; soft failures map to dialog."
);
