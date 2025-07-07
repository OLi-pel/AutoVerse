; installer.iss

[Setup]
AppName=AutoVerse
AppVersion=1.0.2
; --- [THE FIX]: Specify the output directory ---
OutputDir=dist
OutputBaseFilename=AutoVerse-Setup
DefaultDirName={autopf}\AutoVerse
DefaultGroupName=AutoVerse
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; This command tells Inno Setup to grab everything PyInstaller created
; and package it into the installer.
Source: "dist\AutoVerse_App\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Icon for the Start Menu
Name: "{group}\AutoVerse"; Filename: "{app}\AutoVerse.exe"
; Icon for the "Add or remove programs" uninstaller
Name: "{group}\{cm:UninstallProgram,AutoVerse}"; Filename: "{uninstallexe}"
; Optional Desktop Icon (based on the task)
Name: "{autodesktop}\AutoVerse"; Filename: "{app}\AutoVerse.exe"; Tasks: desktopicon

[Run]
; Launch the application after installation is finished.
Filename: "{app}\AutoVerse.exe"; Description: "{cm:LaunchProgram,AutoVerse}"; Flags: nowait postinstall skipifsilent