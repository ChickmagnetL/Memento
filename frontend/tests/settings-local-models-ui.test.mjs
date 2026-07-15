import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");
const settingsForm = readFileSync(
  join(root, "src/app/settings/settings-form.tsx"),
  "utf8",
);
const localModelModal = readFileSync(
  join(root, "src/app/settings/local-model-modal.tsx"),
  "utf8",
);
const api = readFileSync(join(root, "src/lib/api.ts"), "utf8");
const i18n = readFileSync(join(root, "src/lib/i18n.tsx"), "utf8");

test("Settings opens model selection for both local services before installing", () => {
  assert.match(settingsForm, /activeTab === "asr" \|\| activeTab === "embedding"/);
  assert.match(settingsForm, /localModelsCard\(activeTab, false\)/);
  assert.doesNotMatch(settingsForm, /deployAsr/);
  assert.doesNotMatch(settingsForm, /handleDeployAsr/);
});

test("local model modal installs only the selected service model", () => {
  assert.match(localModelModal, /useLanguage/);
  assert.match(localModelModal, /selectedSlug/);
  assert.match(localModelModal, /installLocalModel\(service, selectedSlug!?\)/);
  assert.match(localModelModal, /t\("First model install also creates the environment\."\)/);
  assert.doesNotMatch(localModelModal, /Install Environment/);
});

test("ASR and Embedding expose symmetric local model APIs", () => {
  assert.match(api, /\/api\/\$\{service\}\/local\/status/);
  assert.match(api, /\/api\/\$\{service\}\/local\/models\/\$\{slug\}\/install/);
  assert.match(api, /\/api\/\$\{service\}\/local\/uninstall-all/);
});

test("installed local models can configure and activate a matching preset", () => {
  assert.match(localModelModal, /t\("Configure & Activate"\)/);
  assert.match(localModelModal, /Local ASR/);
  assert.match(localModelModal, /Local Embedding/);
  assert.match(localModelModal, /switchActivePreset\(service, preset\.id\)/);
  assert.match(localModelModal, /previewEmbeddingPresetConfigSwitch/);
  assert.match(localModelModal, /switchEmbeddingPreset/);
  assert.match(settingsForm, /onConfigured/);
});

test("local model dialogs render cached status before background device probing", () => {
  assert.match(settingsForm, /LOCAL_MODEL_SERVICES\.map/);
  assert.match(settingsForm, /open=\{localModelService === service\}/);
  assert.match(localModelModal, /localStorage/);
  assert.match(localModelModal, /probeRuntimeDevice: false/);
  assert.match(localModelModal, /void refresh\(\)/);
  assert.doesNotMatch(settingsForm, /localModelService \? \(/);
});

test("local model dialogs include Chinese copy without translating runtime payloads", () => {
  assert.match(i18n, /"Local ASR Models": "本地 ASR 模型"/);
  assert.match(i18n, /"Local Embedding Models": "本地嵌入模型"/);
  assert.match(i18n, /"Confirm & Rebuild": "确认并重建"/);
  assert.match(i18n, /"Remove the local \{service\} environment and all its models\?"/);
  assert.match(i18n, /"\{service\} preset configured and activated\."/);
  assert.doesNotMatch(localModelModal, /t\(status\.progress\.(?:stage|detail|error)/);
});
