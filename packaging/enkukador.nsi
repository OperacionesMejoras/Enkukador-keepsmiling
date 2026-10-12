; Instalador del Enkukador. Lo arma packaging/build_win.sh:
;   makensis -DVERSION=0.1.0 -DCARGA=<carpeta armada> -DSALIDA=<setup.exe> enkukador.nsi
Unicode true
SetCompressor /SOLID lzma
!include "MUI2.nsh"

!define NOMBRE "Enkukador"
!define CLAVE_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\Enkukador"
!define ICONO "${CARGA}\app\enkukador\ui\estatico\icono.ico"
!define MUI_ICON "${ICONO}"
!define MUI_UNICON "${ICONO}"

Name "${NOMBRE} ${VERSION}"
OutFile "${SALIDA}"
; por usuario, sin pedir permisos de administrador
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\Programs\Enkukador"

!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Abrir ${NOMBRE} ahora"
!define MUI_FINISHPAGE_RUN_FUNCTION Lanzar
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Crear un acceso directo en el escritorio"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION AccesoEscritorio

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"

Function Lanzar
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\runtime\Enkukador.exe" "$INSTDIR\app\lanzador.py"'
FunctionEnd

Function AccesoEscritorio
  SetOutPath "$INSTDIR"
  CreateShortCut "$DESKTOP\${NOMBRE}.lnk" "$INSTDIR\runtime\Enkukador.exe" '"$INSTDIR\app\lanzador.py"' "$INSTDIR\app\enkukador\ui\estatico\icono.ico" 0
FunctionEnd

Section "Programa"
  ; si está abierto no se pueden reemplazar los archivos
  nsExec::Exec 'taskkill /F /IM Enkukador.exe'
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\runtime"
  SetOutPath "$INSTDIR"
  File /r "${CARGA}\*.*"

  CreateDirectory "$SMPROGRAMS\${NOMBRE}"
  CreateShortCut "$SMPROGRAMS\${NOMBRE}\${NOMBRE}.lnk" "$INSTDIR\runtime\Enkukador.exe" '"$INSTDIR\app\lanzador.py"' "$INSTDIR\app\enkukador\ui\estatico\icono.ico" 0
  CreateShortCut "$SMPROGRAMS\${NOMBRE}\Desinstalar.lnk" "$INSTDIR\Desinstalar.exe"

  WriteRegStr HKCU "${CLAVE_REG}" "DisplayName" "${NOMBRE}"
  WriteRegStr HKCU "${CLAVE_REG}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${CLAVE_REG}" "Publisher" "KeepSmiling - Operaciones Mejoras"
  WriteRegStr HKCU "${CLAVE_REG}" "DisplayIcon" "$INSTDIR\app\enkukador\ui\estatico\icono.ico"
  WriteRegStr HKCU "${CLAVE_REG}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${CLAVE_REG}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegDWORD HKCU "${CLAVE_REG}" "NoModify" 1
  WriteRegDWORD HKCU "${CLAVE_REG}" "NoRepair" 1
  WriteUninstaller "$INSTDIR\Desinstalar.exe"
SectionEnd

Section "Uninstall"
  nsExec::Exec 'taskkill /F /IM Enkukador.exe'
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\app.anterior"
  RMDir /r "$INSTDIR\app.nueva"
  Delete "$INSTDIR\app-release.json"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\${NOMBRE}.lnk"
  RMDir /r "$SMPROGRAMS\${NOMBRE}"
  DeleteRegKey HKCU "${CLAVE_REG}"
  ; el registro en %LOCALAPPDATA%\Enkukador no se toca
SectionEnd
