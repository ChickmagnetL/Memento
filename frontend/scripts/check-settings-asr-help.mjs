import { readFileSync } from "node:fs";

const settingsForm = readFileSync("src/app/settings/settings-form.tsx", "utf8");

const endpointHelp = "本地默认使用 http://localhost:8001/v1；云端或局域网 ASR 也填写 OpenAI-compatible base URL。";
const routeHelpPrefix = "当前协议将请求";

const endpointLabel = 'label === "Endpoint"';
const endpointHelpIndex = settingsForm.indexOf(endpointHelp);
if (endpointHelpIndex === -1) {
  console.error("FAIL: ASR endpoint help text was not found.");
  process.exit(1);
}

const endpointLabelIndex = settingsForm.indexOf(endpointLabel);
if (endpointLabelIndex === -1 || endpointHelpIndex < endpointLabelIndex) {
  console.error("FAIL: ASR endpoint help should be rendered with the Endpoint field.");
  process.exit(1);
}

const protocolIndex = settingsForm.indexOf("Protocol");
const routeHelpIndex = settingsForm.indexOf(routeHelpPrefix);
if (protocolIndex === -1 || routeHelpIndex < protocolIndex) {
  console.error("FAIL: ASR protocol route help should be rendered under Protocol.");
  process.exit(1);
}

if (
  !settingsForm.includes('"/audio/transcriptions"') ||
  !settingsForm.includes('"/chat/completions"')
) {
  console.error("FAIL: ASR protocol route help must include both protocol paths.");
  process.exit(1);
}

if (!settingsForm.includes("asrRequestUrl")) {
  console.error("FAIL: ASR protocol route help should use a dynamic request URL.");
  process.exit(1);
}

console.log("ASR settings help text is placed by field and shows dynamic routes.");
