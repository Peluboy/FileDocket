; FileDocket.iss — Inno Setup (run on Windows, or via GitHub Actions).
; Output: Output\FileDocket-Setup.exe

#define MyAppName "FileDocket"
#define MyAppVersion "1.2.2"
#define MyAppExeName "FileDocket.exe"
#define MyAppPublisher "Peluboy"
#define MyAppURL "https://peluboy.github.io/FileDocket/"

[Setup]
AppId={{A3C8D1E4-7B2F-4A91-9E06-2F8C4B1D5E70}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Output
OutputBaseFilename=FileDocket-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=filedocket.ico
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Organize Downloads automatically every 15 minutes"; GroupDescription: "Background sorting:"; Flags: checkedonce
Name: "startup"; Description: "Launch FileDocket when I sign in"; GroupDescription: "Startup:"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "organize.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "filedocket.ico"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Run {#MyAppName} now"; Flags: nowait postinstall skipifsilent
Filename: "{cmd}"; Parameters: "/c schtasks /create /tn ""{#MyAppName}"" /tr ""{app}\organize.cmd"" /sc minute /mo 15 /f"; Flags: runhidden; Tasks: autostart

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c schtasks /delete /tn ""{#MyAppName}"" /f"; Flags: runhidden; RunOnceId: "DelSchedule"
