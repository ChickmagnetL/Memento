import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const presetCardSource = readFileSync(
  join(__dirname, "../src/app/settings/preset-card.tsx"),
  "utf8"
);
const modelPanelSource = readFileSync(
  join(__dirname, "../src/app/settings/model-panel.tsx"),
  "utf8"
);
const settingsFormSource = readFileSync(
  join(__dirname, "../src/app/settings/settings-form.tsx"),
  "utf8"
);
const apiSource = readFileSync(join(__dirname, "../src/lib/api.ts"), "utf8");

test("model list control uses dropdown options with an external get button", () => {
  assert.match(presetCardSource, /Get Model List/);
  assert.match(presetCardSource, /Getting Models\.\.\./);
  assert.doesNotMatch(presetCardSource, /<select|<\/select>|<datalist|list=\{|modelOptionsId/);
  assert.match(presetCardSource, /ChevronDown/);
  assert.match(presetCardSource, /aria-haspopup="listbox"/);
  assert.match(presetCardSource, /role="listbox"[\s\S]*selectOptions\.map/);
  assert.match(presetCardSource, /role="option"/);
  assert.doesNotMatch(presetCardSource, /:\s*"Fetch"|>\s*Fetch\s*</);
});

test("model options keep an editable input with a separate arrow trigger", () => {
  assert.match(
    presetCardSource,
    /\{hasModelOptions \? \([\s\S]*?<input[\s\S]*?aria-label=\{label\}[\s\S]*?value=\{fieldValue\}[\s\S]*?onFieldChange\(key, event\.target\.value\)[\s\S]*?<button\s+type="button"[\s\S]*?aria-label=\{t\("Show model options"\)\}[\s\S]*?aria-haspopup="listbox"[\s\S]*?aria-expanded=\{isModelDropdownOpen\}[\s\S]*?<ChevronDown/
  );

  const optionsBranch =
    presetCardSource.match(
      /\{hasModelOptions \? \(([\s\S]*?)\) : \([\s\S]*?\)\}/
    )?.[1] ?? "";

  assert.doesNotMatch(
    optionsBranch,
    /<button\s+type="button"\s+aria-label=\{label\}[\s\S]*?<span[\s\S]*?\{fieldValue \|\| "Select a model"\}/
  );
});

test("model list API fallback copy does not use Fetch", () => {
  assert.match(apiSource, /assertOk\(res, "Get Model List"\)/);
  assert.doesNotMatch(apiSource, /assertOk\(res, "Fetch/i);
  assert.doesNotMatch(apiSource, /assertOk\(res, "Fetch model/i);
});

test("model panel clears model options when request inputs change", () => {
  assert.match(
    modelPanelSource,
    /if \(key === "endpoint" \|\| key === "api_key" \|\| key === "protocol"\) \{\s*clearModelOptions\(\);\s*\}/
  );
});

test("successful preset runtime changes refresh parent-owned service status", () => {
  const refreshStatusBlock =
    settingsFormSource.match(
      /const refreshStatus = useCallback\(async \(\) => \{[\s\S]*?\}, \[t\]\);/
    )?.[0] ?? "";
  const activateRegularPresetBlock =
    modelPanelSource.match(
      /async function activateRegularPreset\([\s\S]*?\n  \}/
    )?.[0] ?? "";
  const handleSaveBlock =
    modelPanelSource.match(
      /async function handleSave\(\) \{[\s\S]*?\n  \}\n\n  const previewPreset/
    )?.[0] ?? "";

  assert.match(refreshStatusBlock, /setStatus\(await getServiceStatus\(\)\)/);
  assert.match(
    settingsFormSource,
    /<ModelPanel[\s\S]*?onStatusRefresh=\{refreshStatus\}/
  );
  assert.match(
    modelPanelSource,
    /onStatusRefresh: \(\) => Promise<void>;/
  );
  assert.match(
    activateRegularPresetBlock,
    /await switchActivePreset\([\s\S]*?markPresetActiveFromList\([\s\S]*?await onStatusRefresh\(\);[\s\S]*?setInlineMessage\(""\);/
  );
  assert.match(
    handleSaveBlock,
    /if \(modelName === "embedding"\) \{[\s\S]*?await saveSelectedPresetConfig\([\s\S]*?await onStatusRefresh\(\);\s*setInlineMessage\(t\("Saved\."\)\);\s*return;[\s\S]*?\}\s*await saveSelectedPresetConfig\([\s\S]*?await onStatusRefresh\(\);\s*setInlineMessage\(t\("Saved\."\)\);/
  );
});

test("model panel fills model options from list-models result", () => {
  assert.match(
    modelPanelSource,
    /const result = await fetchAvailableModels\([\s\S]*?\);\s*if \(modelListRequestSeqRef\.current !== requestSeq\) \{[\s\S]*?\}\s*setModelOptions\(result\.models\);/
  );
});

test("preset card model dropdown option only reports field changes", () => {
  assert.match(
    presetCardSource,
    /selectOptions\.map\(\(option\) =>[\s\S]*?onClick=\{\(event\) => \{[\s\S]*?event\.stopPropagation\(\);[\s\S]*?onFieldChange\(key, option\);[\s\S]*?setModelDropdownOpen\(false\);[\s\S]*?\}\}/
  );
  const optionClickBlock =
    presetCardSource.match(
      /selectOptions\.map\(\(option\) =>[\s\S]*?setModelDropdownOpen\(false\);[\s\S]*?\}\}/
    )?.[0] ?? "";
  assert.doesNotMatch(optionClickBlock, /onAction|handleSave|handleActivate|onFetchModels/);
});

test("model field remains editable before model options load", () => {
  assert.match(
    presetCardSource,
    /\{hasModelOptions \? \([\s\S]*?<input[\s\S]*?onFieldChange\(key, event\.target\.value\)[\s\S]*?\) : \(\s*<input[\s\S]*?onFieldChange\(key, event\.target\.value\)/
  );
});

test("manual model input has an accessible name before model options load", () => {
  assert.match(
    presetCardSource,
    /\{hasModelOptions \? \([\s\S]*?\) : \(\s*<input[\s\S]*?aria-label=\{label\}[\s\S]*?onFieldChange\(key, event\.target\.value\)/
  );
});

test("model dropdown arrow trigger supports keyboard close", () => {
  const triggerBlock =
    presetCardSource.match(
      /<button\s+type="button"\s+aria-label=\{t\("Show model options"\)\}[\s\S]*?aria-haspopup="listbox"[\s\S]*?<\/button>/
    )?.[0] ?? "";

  assert.match(triggerBlock, /onKeyDown=\{\(event\) => \{/);
  assert.match(triggerBlock, /event\.key === "Escape"[\s\S]*?setModelDropdownOpen\(false\)/);
  assert.match(triggerBlock, /setModelDropdownOpen\(\(open\) => !open\)/);
});

test("model dropdown options support Escape without changing click selection", () => {
  const optionBlock =
    presetCardSource.match(
      /role="option"[\s\S]*?onClick=\{\(event\) => \{[\s\S]*?setModelDropdownOpen\(false\);[\s\S]*?\}\}[\s\S]*?<\/button>/
    )?.[0] ?? "";

  assert.match(optionBlock, /onKeyDown=\{\(event\) => \{/);
  assert.match(optionBlock, /event\.key === "Escape"[\s\S]*?setModelDropdownOpen\(false\)/);
  assert.match(optionBlock, /onFieldChange\(key, option\);[\s\S]*?setModelDropdownOpen\(false\);/);
  assert.doesNotMatch(optionBlock, /onAction|handleSave|handleActivate|onFetchModels/);
});
