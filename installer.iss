#define AppName "SQL Server Simulator"
#define AppVersion "0.6.1"
#define AppExe "SQLServerSimulator.exe"

[Setup]
AppId={{E9EBD782-4D48-4D15-91DD-5B1E5FD58841}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} - Initial Preview v{#AppVersion}
AppPublisher=Ali Sayyadi
AppPublisherURL=mailto:Ali.sayyadi200@gmail.com
AppSupportURL=https://mail.google.com/mail/?view=cm&fs=1&to=Ali.sayyadi200%40gmail.com
DefaultDirName={localappdata}\Programs\SQL Server Simulator
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
WizardImageFile=assets\wizard_side.bmp
WizardSmallImageFile=assets\wizard_small.bmp
SetupIconFile=assets\app.ico
InfoBeforeFile=NOTICE_EN.txt
OutputDir=installer_out
OutputBaseFilename=SQL_Server_Simulator_Setup_v0.6.1
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
VersionInfoDescription=Educational SQL Server Simulator - Ali Sayyadi
VersionInfoCompany=Ali Sayyadi
VersionInfoVersion=0.6.1

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional tasks:"; Flags: unchecked

[Files]
Source: "dist\SQLServerSimulator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "NOTICE_EN.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch SQL Server Simulator"; Flags: nowait postinstall skipifsilent
