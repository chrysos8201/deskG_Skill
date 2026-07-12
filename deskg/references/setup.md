# 설정 — 사용자별 API 키

이 스킬은 **사용자마다 자기 API 키**로 동작한다. 키는 저장소에 넣지 않고, 각자
로컬 설정에만 둔다.

## 1. 키 발급 (사용자가 직접)
deskg.kr 로그인 → 프로필 팝업 → **API 키** 섹션 → **+ 키 발급**.
`dgk_...` 원문은 **그 때 1회만** 표시되므로 복사해 둔다. (목록엔 앞부분만 보인다.
분실하면 폐기 후 재발급.)

## 2. 설정 위치 (병합 — 위가 우선, 부족한 값은 아래에서 채움)
헬퍼는 아래 소스를 병합한다. 위 소스가 값을 이기고, 위에 없는 값은 아래 소스가 채운다
(그래서 `baseUrl`만 있는 파일이 아래 파일의 `apiKey`를 가리지 않는다):

1. **환경변수**
   - `DESKG_API_KEY` (필수), `DESKG_BASE_URL`(기본 `https://deskg.kr`), `DESKG_FOLDER_ID`
2. **`$DESKG_CONFIG`** 가 가리키는 JSON 파일
3. **`~/.deskg/config.json`** ← 권장
4. 스킬 폴더의 **`config.local.json`** (gitignore됨)

### `~/.deskg/config.json` 예시 (권장)
```json
{
  "baseUrl": "https://deskg.kr",
  "apiKey": "dgk_여기에_본인_키",
  "defaultFolderId": 4
}
```
- Windows에서 `~` 는 `C:\Users\<이름>` 이다. 파일 경로: `C:\Users\<이름>\.deskg\config.json`.
- `defaultFolderId` 는 개발 작업 태스크를 놓을 **기본 leaf 폴더**. 아래 3번으로 알아낸다.

## 3. 내 folderId 찾기
API에 폴더 목록 엔드포인트가 없어서, 기존 태스크에서 역추적한다
(`<스킬>` = 설치된 스킬 폴더 절대경로, 예: `~/.claude/skills/deskg`):
```bash
python "<스킬>/scripts/deskg.py" folders
```
`folderId  count  crumb` 표가 나온다. 개발 개선 작업을 모으는 **leaf 폴더**(하위폴더 없는)
하나를 골라 `defaultFolderId`로 설정한다.
> ⚠️ 태스크가 하나도 없는 폴더는 이 표에 안 나온다(태스크에서 역추적하므로).
> 빈 폴더에 넣고 싶으면 그 folderId를 아는 사람에게 물어보거나, deskg.kr에서 확인한다.

## 4. 확인
```bash
python "<스킬>/scripts/deskg.py" me
```
`{"userId":..., "name":"...", "isAdmin":...}` 가 나오면 성공. `401`이면 키가 틀렸거나 폐기됨.

## 보안 원칙
- **키를 저장소·커밋·채팅 로그·에이전트 메모리에 남기지 않는다.** 위 설정 경로에만.
- `~/.deskg/config.json` 은 리포 밖이라 커밋될 일이 없다. 스킬 폴더 안에 두려면 반드시
  `config.local.json`(gitignore됨)만 쓴다. `config.example.json` 에는 실제 키를 넣지 않는다.
- 키가 노출됐다고 판단되면 deskg.kr에서 즉시 **폐기** 후 재발급(폐기 즉시 401).
- 이 키는 **소유 계정 전체 권한**으로 태스크를 읽고 쓴다. 남과 공유하지 않는다.
