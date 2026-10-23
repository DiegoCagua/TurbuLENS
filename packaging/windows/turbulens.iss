; Instalador de TurbuLENS para Windows (Inno Setup 6).
; Lo compila GitHub Actions:  iscc /DMyVersion=1.2.0 /DSourceDir=..\..\dist\TurbuLENS packaging\windows\turbulens.iss
; Crea accesos directos en el menú Inicio y (opcional) en el escritorio, y un desinstalador.

#ifndef MyVersion
  #define MyVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\TurbuLENS"
#endif
#ifndef OutputName
  #define OutputName "TurbuLENS-Instalador"
#endif

[Setup]
AppId={{6F3C2B1E-7A8D-4C55-9E21-5B0D3A9C7E41}
AppName=TurbuLENS
AppVersion={#MyVersion}
AppVerName=TurbuLENS {#MyVersion}
AppPublisher=Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina
AppPublisherURL=https://github.com/DiegoCagua/TurbuLENS
AppSupportURL=https://github.com/DiegoCagua/TurbuLENS/issues
AppUpdatesURL=https://github.com/DiegoCagua/TurbuLENS/releases
AppCopyright=Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina
VersionInfoVersion={#MyVersion}
VersionInfoProductName=TurbuLENS
VersionInfoDescription=TurbuLENS · Observatorio Astronómico Nacional · Universidad Nacional de Colombia
DefaultDirName={autopf}\TurbuLENS
DefaultGroupName=TurbuLENS
DisableProgramGroupPage=yes
; Sin permisos de administrador por defecto (se instala para el usuario); se puede elegir «para todos».
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\..\LICENSE
SetupIconFile=..\..\turbulens\assets\turbulens.ico
UninstallDisplayIcon={app}\TurbuLENS.exe
UninstallDisplayName=TurbuLENS {#MyVersion}
OutputDir=..\..\instalador
OutputBaseFilename={#OutputName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LEEME.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\TurbuLENS"; Filename: "{app}\TurbuLENS.exe"; Comment: "Seeing con un DIMM y estadística con una estrella"
Name: "{autodesktop}\TurbuLENS"; Filename: "{app}\TurbuLENS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TurbuLENS.exe"; Description: "{cm:LaunchProgram,TurbuLENS}"; Flags: nowait postinstall skipifsilent
