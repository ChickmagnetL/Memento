import { readFileSync } from "node:fs";

const videoIntake = readFileSync("src/app/video-intake.tsx", "utf8");

const handleProcessStart = videoIntake.indexOf("async function handleProcess");
if (handleProcessStart === -1) {
  console.error("FAIL: handleProcess() was not found in video-intake.tsx");
  process.exit(1);
}

const handleProcessBody = videoIntake.slice(handleProcessStart);

const completedBranch = /if\s*\(\s*video\.status\s*===\s*"completed"\s*\)\s*\{\s*await\s+runProcess\(video\.id\);\s*return;\s*\}/s;

if (!completedBranch.test(handleProcessBody)) {
  console.error(
    "FAIL: completed videos should bypass subtitle pre-check and re-process immediately"
  );
  process.exit(1);
}

const hasSubtitleCheck = handleProcessBody.includes(
  'const result = await checkSubtitles(video.id);'
);

if (!hasSubtitleCheck) {
  console.error(
    "FAIL: first-time processing should still keep the subtitle pre-check flow"
  );
  process.exit(1);
}

console.log("Completed re-process bypasses subtitle pre-check.");
