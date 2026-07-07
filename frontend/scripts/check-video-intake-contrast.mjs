import { readFileSync } from "node:fs";

const layout = readFileSync("src/app/layout.tsx", "utf8");
const videoIntake = readFileSync("src/app/video-intake.tsx", "utf8");
const globals = readFileSync("src/app/globals.css", "utf8");

const checks = [
  {
    name: "body sets app background and foreground colors",
    passed:
      layout.includes("bg-background") && layout.includes("text-foreground"),
  },
  {
    name: "URL input sets readable text and placeholder colors",
    passed:
      videoIntake.includes("text-foreground") &&
      videoIntake.includes("placeholder:text-muted-foreground"),
  },
  {
    name: "status badge variants set readable foreground and background colors",
    passed:
      videoIntake.includes("video-badge") &&
      globals.includes(".video-badge.completed") &&
      globals.includes(".video-badge.pending") &&
      globals.includes(".video-badge.failed") &&
      globals.includes("color: #86efac;") &&
      globals.includes("color: #fde68a;") &&
      globals.includes("color: #fca5a5;"),
  },
];

const failures = checks.filter((check) => !check.passed);

if (failures.length > 0) {
  for (const failure of failures) {
    console.error(`FAIL: ${failure.name}`);
  }
  process.exit(1);
}

console.log("Video intake contrast classes are present.");
