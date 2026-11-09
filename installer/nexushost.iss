; Inno Setup script for NEXUS HOST. Build with build_installer.bat (after PyInstaller has produced dist\NexusHost).
#define MyAppName "NEXUS HOST"
#define MyAppVersion "1.0.0"
#define MyAppExe "NexusHost.exe"

[Setup]
AppId={{B5C7E5A2-3F1D-4E0A-9C61-7A2D8E4F1B90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=NEXUS HOST
DefaultDirName={autopf}\NEXUS HOST
DefaultGroupName=NEXUS HOST
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=NexusHost-Setup-{#MyAppVersion}
SetupIconFile=..\assets\nexus.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\NexusHost\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\NEXUS HOST"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\NEXUS HOST"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,NEXUS HOST}"; Flags: nowait postinstall skipifsilent

; Servers and worlds live in %LOCALAPPDATA%\NexusHost and are intentionally NOT removed on uninstall.
