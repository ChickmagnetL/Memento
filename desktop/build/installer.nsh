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
    RMDir /r "$INSTDIR"
    ${If} $R7 == "app"
    ${AndIf} $R6 == "${APP_FILENAME}"
      RMDir /r "$R8\data"
      RMDir /r "$R8\services"
      RMDir /r "$R8\cache"
      RMDir "$R8"
    ${EndIf}
  ${EndIf}
!macroend
