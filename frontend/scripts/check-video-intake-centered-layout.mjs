import { readFileSync } from "node:fs";

const css = readFileSync("src/app/globals.css", "utf8");
const videoIntake = readFileSync("src/app/video-intake.tsx", "utf8");

const checks = [
  {
    name: "page shell exposes expanded state for layout transition",
    passed: videoIntake.includes('page-shell${isExpanded ? " is-expanded" : ""}'),
  },
  {
    name: "hero and URL group has a dedicated layout wrapper",
    passed: videoIntake.includes('className="page-hero-url"'),
  },
  {
    name: "hero and URL group height is measured for exact centering",
    passed:
      videoIntake.includes("heroUrlRef") &&
      videoIntake.includes("--hero-url-half-height"),
  },
  {
    name: "collapsed state positions the measured hero and URL group slightly above center",
    passed:
      css.includes(".page-shell:not(.is-expanded)") &&
      css.includes("padding-top: max(2.5rem, calc(27vh - var(--hero-url-half-height)));"),
  },
  {
    name: "collapsed carousel focuses cards above the stage center",
    passed:
      css.includes("--focused-card-y: 38%;") &&
      css.includes("top: var(--focused-card-y);"),
  },
  {
    name: "expanded state returns to normal top padding",
    passed: css.includes(".page-shell.is-expanded") && css.includes("padding-top: 2.5rem;"),
  },
];

const failures = checks.filter((check) => !check.passed);

if (failures.length > 0) {
  for (const failure of failures) {
    console.error(`FAIL: ${failure.name}`);
  }
  process.exit(1);
}

console.log("Video intake centered/collapsed layout rules are present.");
