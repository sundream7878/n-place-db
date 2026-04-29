; Inno Setup Script for N-Place-DB Pro
; 이 스크립트는 N-Place-DB Pro 설치 프로그램을 생성합니다.

[Setup]
AppId={{D83B5E0C-5F1A-4C2E-A111-B2C1A2D3E4F5}
AppName=N-Place-DB Pro
AppVersion=1.0
AppPublisher=N-Place-DB Team
DefaultDirName={autopf}\N-Place-DB Pro
DefaultGroupName=N-Place-DB Pro
OutputDir=.
OutputBaseFilename=N-Place-DB_Pro_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; 관리자 권한 필수 (의존성 설치를 위해)
PrivilegesRequired=admin

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 빌드된 전체 폴더 포함 (dist 폴더 위치가 다를 경우 아래 경로 수정)
Source: "d:\N-Place-DB\dist\N-Place-DB-Pro-Final\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 의존성 설치 파일 포함
Source: "d:\N-Place-DB\dependencies\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\N-Place-DB Pro"; Filename: "{app}\N-Place-DB-Pro-Final.exe"
Name: "{autodesktop}\N-Place-DB Pro"; Filename: "{app}\N-Place-DB-Pro-Final.exe"; Tasks: desktopicon

[Run]
; 프로그램 마지막 단계에서 VC++ Redistributable 설치 실행
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/quiet /norestart"; StatusMsg: "필수 시스템 구성 요소(Visual C++)를 설치하는 중입니다..."; Check: NeedsVC14; Flags: waituntilterminated
; 프로그램 바로 실행 옵션
Filename: "{app}\N-Place-DB-Pro-Final.exe"; Description: "{cm:LaunchProgram,N-Place-DB Pro}"; Flags: nowait postinstall skipifsilent

[Code]
// VC++ Redistributable 2015-2022 가 설치되어 있는지 확인하는 함수
function NeedsVC14: Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
  begin
    if Installed = 1 then
      Result := False;
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
