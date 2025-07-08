; installer.iss - Inno Setup script for AutoVerse

[Setup]
AppName=AutoVerse
AppVersion=1.0.2 
; ^ Remember to update this version number for new releases.

; --- [THE FIX]: Change PrivilegesRequired and DefaultDirName ---
PrivilegesRequired=lowest
DefaultDirName={localappdata}\AutoVerse
; --- [END OF FIX] ---

OutputBaseFilename=AutoVerse-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; ... rest of the file is unchanged ...

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\AutoVerse_App\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AutoVerse"; Filename: "{app}\AutoVerse.exe"
Name: "{group}\{cm:UninstallProgram,AutoVerse}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AutoVerse"; Filename: "{app}\AutoVerse.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AutoVerse.exe"; Description: "{cm:LaunchProgram,AutoVerse}"; Flags: nowait postinstall skipifsilent