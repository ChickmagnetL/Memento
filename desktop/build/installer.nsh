!include "LogicLib.nsh"
!include "FileFunc.nsh"

!ifndef BUILD_UNINSTALLER
  !macro customInstallMode
    StrCpy $isForceCurrentInstall "1"
  !macroend

  !macro customInit
    ${If} ${isForAllUsers}
      MessageBox MB_OK|MB_ICONSTOP \
        "Memento supports current-user installation only."
      SetErrorLevel 1
      Quit
    ${EndIf}
    ${If} $hasPerMachineInstallation == "1"
      MessageBox MB_OK|MB_ICONSTOP \
        "Memento must be installed for the current user. Uninstall the existing all-users version first."
      SetErrorLevel 1
      Quit
    ${EndIf}
    Call NormalizeMementoInstallLayout
  !macroend

  !macro customPageAfterChangeDir
    Page custom EnsureMementoInstallLayoutPage
  !macroend

  Function EnsureMementoInstallLayoutPage
    Call NormalizeMementoInstallLayout
    Abort
  FunctionEnd

  Function NormalizeMementoInstallLayout
    StrCpy $2 "$INSTDIR" 1 -1
    StrCmp $2 "\" 0 inspectLastComponent
    StrCpy $INSTDIR "$INSTDIR" -1

  inspectLastComponent:
    ${GetFileName} "$INSTDIR" $0
    StrCmp $0 "app" inspectAppParent
    StrCmp $0 "${APP_FILENAME}" appendApp appendContainer

  inspectAppParent:
    ${GetParent} "$INSTDIR" $1
    ${GetFileName} "$1" $2
    StrCmp $2 "${APP_FILENAME}" done appendContainer

  appendApp:
    StrCpy $INSTDIR "$INSTDIR\app"
    Goto done

  appendContainer:
    StrCpy $INSTDIR "$INSTDIR\${APP_FILENAME}\app"

  done:
    Return
  FunctionEnd
!else
  Function un.StopMementoRuntimeProcesses
    Push $0
    Push $1

    DetailPrint "Stopping Memento runtime processes..."
    System::Call 'kernel32::SetEnvironmentVariableW(w "MEMENTO_UNINSTALL_ROOT", w "$R8") i.r0'
    nsExec::ExecToLog `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$$root = [Environment]::GetEnvironmentVariable('MEMENTO_UNINSTALL_ROOT'); if ([string]::IsNullOrWhiteSpace($$root)) { exit 1 }; $$prefix = [IO.Path]::GetFullPath($$root).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar; foreach ($$attempt in 1..3) { $$processes = @(Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue | Where-Object { $$_.ExecutablePath -and $$_.ExecutablePath.StartsWith($$prefix, [StringComparison]::OrdinalIgnoreCase) }); if ($$processes.Count -eq 0) { exit 0 }; $$processes | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }; Start-Sleep -Milliseconds 300 }; exit 2"`
    Pop $0
    System::Call 'kernel32::SetEnvironmentVariableW(w "MEMENTO_UNINSTALL_ROOT", p 0) i.r1'

    ${If} $0 != 0
      DetailPrint "Some Memento runtime processes could not be stopped; locked files will be removed after restart."
    ${EndIf}
    Pop $1
    Pop $0
  FunctionEnd
!endif

!macro customUnInstall
  ${IfNot} ${isUpdated}
    RMDir /r "$APPDATA\${APP_FILENAME}"
    !ifdef APP_PRODUCT_FILENAME
      RMDir /r "$APPDATA\${APP_PRODUCT_FILENAME}"
    !endif
    !ifdef APP_PACKAGE_NAME
      RMDir /r "$APPDATA\${APP_PACKAGE_NAME}"
    !endif
  ${EndIf}
!macroend

!macro customRemoveFiles
  ${If} ${isUpdated}
    CreateDirectory "$PLUGINSDIR\old-install"

    Push ""
    Call un.atomicRMDir
    Pop $0

    ${If} $0 != 0
      DetailPrint "File is busy, aborting: $0"

      Push ""
      Call un.restoreFiles
      Pop $0

      Abort `Can't rename "$INSTDIR" to "$PLUGINSDIR\old-install".`
    ${EndIf}

    SetOutPath $TEMP
    RMDir /r "$INSTDIR"
  ${Else}
    SetOutPath $TEMP
    ${GetFileName} "$INSTDIR" $R7
    ${GetParent} "$INSTDIR" $R8
    ${GetFileName} "$R8" $R6
    ${If} $R7 == "app"
    ${AndIf} $R6 == "${APP_FILENAME}"
      Call un.StopMementoRuntimeProcesses

      ClearErrors
      RMDir /r "$R8\services"
      ${If} ${Errors}
        DetailPrint "Scheduling locked service files for removal after restart."
        RMDir /r /REBOOTOK "$R8\services"
      ${EndIf}

      ClearErrors
      RMDir /r "$R8\cache"
      ${If} ${Errors}
        DetailPrint "Scheduling locked cache files for removal after restart."
        RMDir /r /REBOOTOK "$R8\cache"
      ${EndIf}

      ClearErrors
      RMDir /r "$INSTDIR"
      ${If} ${Errors}
        RMDir /r /REBOOTOK "$INSTDIR"
      ${EndIf}

      ClearErrors
      RMDir /r "$R8\data"
      ${If} ${Errors}
        DetailPrint "Scheduling locked data files for removal after restart."
        RMDir /r /REBOOTOK "$R8\data"
      ${EndIf}

      RMDir /REBOOTOK "$R8"
    ${Else}
      # Preserve electron-builder's normal behavior if an older install does
      # not use the expected Memento\app layout.
      RMDir /r /REBOOTOK "$INSTDIR"
    ${EndIf}
  ${EndIf}
!macroend
