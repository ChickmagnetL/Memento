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

test("Settings opens model selection for both local services before installing", () => {
  assert.match(settingsForm, /activeTab === "asr" \|\| activeTab === "embedding"/);
  assert.match(settingsForm, /localModelsCard\(activeTab, false\)/);
  assert.doesNotMatch(settingsForm, /deployAsr/);
  assert.doesNotMatch(settingsForm, /handleDeployAsr/);
});

test("local model modal installs only the selected service model", () => {
  assert.match(localModelModal, /selectedSlug/);
  assert.match(localModelModal, /installLocalModel\(service, selectedSlug!?\)/);
  assert.match(localModelModal, /first model install also creates the environment/i);
  assert.doesNotMatch(localModelModal, /Install Environment/);
});

test("ASR and Embedding expose symmetric local model APIs", () => {
  assert.match(api, /\/api\/\$\{service\}\/local\/status/);
  assert.match(api, /\/api\/\$\{service\}\/local\/models\/\$\{slug\}\/install/);
  assert.match(api, /\/api\/\$\{service\}\/local\/uninstall-all/);
});

test("installed local models can configure and activate a matching preset", () => {
  assert.match(localModelModal, /Configure & Activate/);
  assert.match(localModelModal, /Local ASR/);
  assert.match(localModelModal, /Local Embedding/);
  assert.match(localModelModal, /switchActivePreset\(service, preset\.id\)/);
  assert.match(localModelModal, /previewEmbeddingPresetConfigSwitch/);
  assert.match(localModelModal, /switchEmbeddingPreset/);
  assert.match(settingsForm, /onConfigured/);
});
