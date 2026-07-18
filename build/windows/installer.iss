; scrcpy-farm Installer — Inno Setup Script for Windows
; Requires: Inno Setup (https://jrsoftware.org/isdl.php)
; 1. Build scrcpy-farm.exe with build\windows\build.bat
; 2. Open this file in Inno Setup Compiler
; 3. Build → Compile

#define MyAppName "scrcpy Farm"
#define MyAppVersion "3.0"
#define MyAppPublisher "scrcpy-farm"
#define MyAppURL "https://github.com/beytgoal/scrcpy-farm"
#define MyAppExeName "scrcpy-farm.exe"

[Setup]
AppId={{SCRCPY-FARM-2024-A1B2-C3D4-E5F6-G7H8I9J0K1L2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\scrcpy-farm
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist
OutputBaseFilename=scrcpy-farm-setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.iso"
Name: "indonesian"; MessagesFile: "compiler:Languages\Indonesian.iso"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\..\dist\scrcpy-farm.exe"; DestDir: "{app}"; Flags: ignoreversion

; Include scrcpy + adb if available
Source: "C:\scrcpy\scrcpy.exe"; DestDir: "{app}\bin"; Flags: ignoreversion skipifsourcedoesntexist
Source: "C:\scrcpy\adb.exe"; DestDir: "{app}\bin"; Flags: ignoreversion skipifsourcedoesntexist
Source: "C:\scrcpy\AdbWinApi.dll"; DestDir: "{app}\bin"; Flags: ignoreversion skipifsourcedoesntexist
Source: "C:\scrcpy\AdbWinUsbApi.dll"; DestDir: "{app}\bin"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: postinstall nowait skipifsilent
