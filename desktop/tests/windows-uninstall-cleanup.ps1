param(
  [Parameter(Mandatory = $true)]
  [string]$InstallerPath,

  [string]$ProductName = "Memento"
)

$ErrorActionPreference = "Stop"

$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$testRoot = Join-Path ([IO.Path]::GetTempPath()) (
  "memento-uninstall-{0}" -f [guid]::NewGuid().ToString("N")
)
$installRoot = Join-Path $testRoot $ProductName
$appDir = Join-Path $installRoot "app"
$worker = $null
$uninstaller = $null

if ($appDir.Contains(" ")) {
  throw "The NSIS /D smoke-test path must not contain spaces: $appDir"
}

try {
  $install = Start-Process `
    -FilePath $installer `
    -ArgumentList @("/S", "/D=$appDir") `
    -PassThru `
    -Wait
  if ($install.ExitCode -ne 0) {
    throw "Installer exited with code $($install.ExitCode)."
  }
  if (-not (Test-Path -LiteralPath $appDir -PathType Container)) {
    throw "Expected app directory was not installed: $appDir"
  }

  $servicesDir = Join-Path $installRoot "services\asr\.venv\Scripts"
  $cacheDir = Join-Path $installRoot "cache\temp"
  New-Item -ItemType Directory -Force -Path $servicesDir, $cacheDir | Out-Null
  Set-Content -LiteralPath (Join-Path $cacheDir "held-cache.bin") -Value "cache"

  # A process whose executable lives in services reproduces the real lock held
  # by a local ASR/Embedding venv without downloading a multi-GB model.
  $workerExe = Join-Path $servicesDir "memento-uninstall-test-worker.exe"
  $windowsPowerShell = Join-Path $env:SystemRoot (
    "System32\WindowsPowerShell\v1.0\powershell.exe"
  )
  Copy-Item -LiteralPath $windowsPowerShell -Destination $workerExe
  $worker = Start-Process `
    -FilePath $workerExe `
    -ArgumentList @("-NoLogo", "-NoProfile", "-Command", "Start-Sleep -Seconds 300") `
    -PassThru
  Start-Sleep -Milliseconds 800
  $worker.Refresh()
  if ($worker.HasExited) {
    throw "Runtime worker exited before uninstall (code $($worker.ExitCode))."
  }

  $uninstaller = Get-ChildItem `
    -LiteralPath $appDir `
    -Filter "Uninstall*.exe" |
    Select-Object -First 1
  if (-not $uninstaller) {
    throw "Uninstaller was not found under $appDir."
  }

  $uninstall = Start-Process `
    -FilePath $uninstaller.FullName `
    -ArgumentList "/S" `
    -PassThru `
    -Wait
  if ($uninstall.ExitCode -ne 0) {
    throw "Uninstaller exited with code $($uninstall.ExitCode)."
  }

  Start-Sleep -Milliseconds 800
  $worker.Refresh()
  if (-not $worker.HasExited) {
    throw "The uninstaller did not stop the runtime worker."
  }
  if (Test-Path -LiteralPath (Join-Path $installRoot "services")) {
    throw "The services directory remained after uninstall."
  }
  if (Test-Path -LiteralPath (Join-Path $installRoot "cache")) {
    throw "The cache directory remained after uninstall."
  }
  if (Test-Path -LiteralPath $installRoot) {
    throw "The install container remained after uninstall."
  }

  Write-Output (
    "Windows uninstall cleanup passed: runtime process stopped and managed directories removed."
  )
} finally {
  if ($worker) {
    $worker.Refresh()
    if (-not $worker.HasExited) {
      Stop-Process -Id $worker.Id -Force -ErrorAction SilentlyContinue
    }
  }

  if (-not $uninstaller -and (Test-Path -LiteralPath $appDir)) {
    $uninstaller = Get-ChildItem `
      -LiteralPath $appDir `
      -Filter "Uninstall*.exe" `
      -ErrorAction SilentlyContinue |
      Select-Object -First 1
  }
  if ($uninstaller -and (Test-Path -LiteralPath $uninstaller.FullName)) {
    Start-Process `
      -FilePath $uninstaller.FullName `
      -ArgumentList "/S" `
      -Wait `
      -ErrorAction SilentlyContinue
  }

  if (Test-Path -LiteralPath $testRoot) {
    $resolvedTestRoot = (Resolve-Path -LiteralPath $testRoot).Path
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd("\") + "\"
    if (-not $resolvedTestRoot.StartsWith(
      $tempRoot,
      [StringComparison]::OrdinalIgnoreCase
    )) {
      throw "Refusing to remove unsafe test directory: $resolvedTestRoot"
    }
    Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
  }
}
