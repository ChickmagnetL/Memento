const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const desktopDir = path.join(__dirname, "..");
const packageJson = require(path.join(desktopDir, "package.json"));
const installerSource = fs.readFileSync(
  path.join(desktopDir, "build", "installer.nsh"),
  "utf8",
);

test("Windows installer is assisted and restricted to current-user paths", () => {
  assert.equal(packageJson.build.nsis.oneClick, false);
  assert.equal(packageJson.build.nsis.perMachine, false);
  assert.equal(packageJson.build.nsis.allowElevation, false);
  assert.equal(packageJson.build.nsis.allowToChangeInstallationDirectory, true);
  assert.equal(packageJson.build.nsis.include, "build/installer.nsh");
  assert.match(installerSource, /StrCpy \$isForceCurrentInstall "1"/);
  assert.match(installerSource, /\$\{If\} \$\{isForAllUsers\}/);
  assert.match(installerSource, /\$hasPerMachineInstallation == "1"/);
});

test("Windows installer uses a Memento container with an app subdirectory", () => {
  assert.match(installerSource, /StrCpy \$INSTDIR "\$INSTDIR\\app"/);
  assert.match(
    installerSource,
    /StrCpy \$INSTDIR "\$INSTDIR\\\$\{APP_FILENAME\}\\app"/,
  );
});

test("upgrades preserve managed siblings while explicit uninstall removes them", () => {
  assert.match(installerSource, /\$\{If\} \$\{isUpdated\}[\s\S]*?Call un\.atomicRMDir/);
  assert.match(installerSource, /\$\{GetFileName\} "\$INSTDIR" \$R7/);
  assert.match(installerSource, /\$\{AndIf\} \$R6 == "\$\{APP_FILENAME\}"/);
  assert.match(installerSource, /RMDir \/r "\$R8\\data"/);
  assert.match(installerSource, /RMDir \/r "\$R8\\services"/);
  assert.match(installerSource, /RMDir \/r "\$R8\\cache"/);
  assert.match(installerSource, /RMDir \/r "\$APPDATA\\\$\{APP_PACKAGE_NAME\}"/);
});

test("explicit uninstall stops runtime processes outside the app subdirectory", () => {
  assert.match(
    installerSource,
    /Function un\.StopMementoRuntimeProcesses[\s\S]*?FunctionEnd/,
  );
  assert.match(
    installerSource,
    /SetEnvironmentVariableW\(w "MEMENTO_UNINSTALL_ROOT", w "\$R8"\)/,
  );
  assert.match(
    installerSource,
    /ExecutablePath\.StartsWith\(\$\$prefix, \[StringComparison\]::OrdinalIgnoreCase\)/,
  );
  assert.match(installerSource, /Stop-Process -Id \$\$_\.ProcessId -Force/);
  assert.match(
    installerSource,
    /\$\{AndIf\} \$R6 == "\$\{APP_FILENAME\}"[\s\S]*?Call un\.StopMementoRuntimeProcesses/,
  );
});

test("locked runtime directories are scheduled for deletion on restart", () => {
  assert.match(installerSource, /RMDir \/r \/REBOOTOK "\$R8\\services"/);
  assert.match(installerSource, /RMDir \/r \/REBOOTOK "\$R8\\cache"/);
  assert.match(installerSource, /RMDir \/r \/REBOOTOK "\$R8\\data"/);
  assert.match(installerSource, /RMDir \/r \/REBOOTOK "\$INSTDIR"/);
  assert.match(installerSource, /RMDir \/REBOOTOK "\$R8"/);
});
