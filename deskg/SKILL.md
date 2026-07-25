---
name: deskg
description: deskG(deskg.kr) 태스크로 작업을 리포팅하는 방법 — 관련 태스크 검색·계획 태스크 생성·진행/코멘트 보고·완료 정리·커밋에 태스크 링크. deskG로 관리되는 작업을 할 때, 사용자가 "deskg에 올려/진행 올려/태스크로 정리해"라고 하거나 deskg.kr 태스크를 다룰 때 사용. 조회는 자유롭게, 태스크·코멘트 게시는 사용자 확인 후.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# deskG 작업 리포팅 스킬

deskG(https://deskg.kr)의 **계정별 API 키**로 태스크를 읽고 써서, 작업을
**사람이 읽기 편한 태스크/코멘트**로 리포팅한다. 각 사용자는 자기 API 키를 쓴다.
deskG 서버 코드는 건드리지 않고 **기존 `/api/v1` REST API만** 쓴다.

이 스킬로 하는 일: ① 시작 시 관련 정보 확인 → ② 계획 태스크 생성 → ③ 진행/코멘트
보고 → ④ 완료 정리 → ⑤ 커밋 메시지에 태스크 링크.

## 준비 (API 키)

헬퍼는 아래 소스를 **병합**해 설정을 만든다(위가 우선, 부족한 값은 아래에서 채움) — 자세한 건 `references/setup.md`:
1. 환경변수 `DESKG_API_KEY` / `DESKG_BASE_URL` / `DESKG_FOLDER_ID`
2. `$DESKG_CONFIG` 가 가리키는 JSON 파일
3. `~/.deskg/config.json` → `{"baseUrl":"https://deskg.kr","apiKey":"dgk_...","defaultFolderId":4}`
4. 스킬 폴더의 `config.local.json`(gitignore됨)

키가 없으면 헬퍼가 발급 방법을 안내한다(deskg.kr 프로필 팝업 → **API 키** → **+ 키 발급**, 원문은 1회만 표시).
**키를 저장소·커밋·메모리에 절대 남기지 말 것.** 항상 위 설정 경로에만 둔다.

## 헬퍼 사용법

모든 호출은 파이썬 헬퍼 하나로 한다(표준 라이브러리만, pip 불필요).

> **경로 규칙 (중요).** 아래 명령의 `scripts/deskg.py`는 **스킬 설치 폴더 기준
> 상대경로**다. 실행 시 cwd는 대개 작업 프로젝트라 그대로 쓰면 파일을 못 찾는다.
> **이 SKILL.md가 있는 폴더가 `<스킬>`** 이다. 둘 중 하나로 실행하라:
> - 절대경로: `python "<스킬>/scripts/deskg.py" me`
> - 또는 한 번의 Bash 호출 안에서: `cd "<스킬>"; python scripts/deskg.py me`
>
> `python`이 없으면 Windows는 `py`, POSIX는 `python3` 로 대체(`py "<스킬>/scripts/deskg.py" me`).

```bash
python "<스킬>/scripts/deskg.py" me                 # 키 확인 → 소유 계정
python "<스킬>/scripts/deskg.py" tasks --q "검색어"  # 태스크 검색(제목+본문 프리뷰)
python "<스킬>/scripts/deskg.py" tasks --folder 4   # 폴더로 필터
python "<스킬>/scripts/deskg.py" task 72            # 태스크 상세(본문 포함)
python "<스킬>/scripts/deskg.py" comments 72        # 코멘트(스레드) 읽기
python "<스킬>/scripts/deskg.py" progresses 72      # 진행(버전) 목록 읽기
python "<스킬>/scripts/deskg.py" folders            # folderId ↔ 폴더 경로 표
python "<스킬>/scripts/deskg.py" new --title "..." --html-file plan.html --folder 4
python "<스킬>/scripts/deskg.py" progress 72 --html-file prog.html   # 진행 추가(새 버전)
python "<스킬>/scripts/deskg.py" comment 72 --body-file note.txt     # 코멘트/메모
python "<스킬>/scripts/deskg.py" patch 72 --status 완료 --done true  # 상태/완료/본문 수정
python "<스킬>/scripts/deskg.py" notifications                       # 내 알림(코멘트/멘션)
python "<스킬>/scripts/deskg.py" photo-upload shot.png               # 사진/영상 올리기 → 넣을 태그 출력
python "<스킬>/scripts/deskg.py" photos 72                           # 태스크의 사진 목록
python "<스킬>/scripts/deskg.py" photos 72 --out-dir ./shots         # 목록 + 전부 내려받기
python "<스킬>/scripts/deskg.py" photo-download 8f1c….png --out a.png # 한 장 내려받기
```
> `patch`·`notifications`·`progress`·`photo-*`·`photos` 는 **최신 배포 서버**에서만 동작한다
> (구버전이면 404 → 헬퍼가 안내). 조회(me/tasks/task/comments/folders)와 new/comment 는 어디서나 동작.

- **본문은 항상 파일로 넘긴다**(`--html-file` / `--body-file`). 한글·HTML을 CLI 인자로
  직접 넘기면 Windows PowerShell에서 따옴표/인코딩이 깨진다. 임시 파일은 스크래치
  디렉터리에 쓰고 UTF-8로 저장.
- `new`는 만든 태스크의 URL(`https://deskg.kr/{id}`)을 출력한다 → 커밋 메시지에 쓴다.

### 쓰기 전 확인 (필수)
`new`(태스크 생성)와 `comment`(코멘트)는 **실제 게시**다. 코멘트는 태스크 작성자·
`@멘션` 대상에게 **알림·웹푸시를 보낸다** — 즉 남을 향한 발행이다. 그래서:
- **첫 태스크 생성 전, 그리고 모든 코멘트 게시 전에 사용자에게 확인을 받는다.**
- 확인용으로 **`--dry-run`을 먼저 실행해 보낼 내용을 보여준 뒤** 동의를 받고 실제로 올린다.
- 조회(`me`/`tasks`/`task`/`folders`/`photos`/`photo-download`)는 확인 없이 자유롭게 해도 된다.
- `photo-upload` 는 서버에 파일만 올릴 뿐 **아무 태스크에도 붙지 않고 알림도 없다** →
  준비 단계로 확인 없이 해도 된다. 다만 **삭제 API가 없어 올린 파일은 사람이 지울 수도 없다**.
  그러니 **사용자가 준 파일 / 내가 만든 산출물만** 올리고, 관계없는 로컬 파일은 올리지 않는다.
  실제 게시는 그 URL을 본문에 넣어 `new`/`progress`/`patch` 할 때 일어나므로, **그 시점의
  확인 규칙을 그대로 따른다**.

## 사진 올리기 / 받기

**올리기** — 3단계다. `photo-upload` 로 올리고 → 출력된 `/uploads/…` URL을 본문 HTML에
`<img>` 로 넣고 → 그 HTML을 `new`/`progress`/`patch` 에 `--html-file` 로 넘긴다.
```bash
python "<스킬>/scripts/deskg.py" photo-upload before.png after.png   # 여러 장 한 번에
```
- ⚠️ **코멘트에는 이미지를 못 넣는다**(코멘트는 평문 — `<img>` 가 글자로 보인다).
  사진이 있는 보고는 `progress`(새 버전)나 `patch --html-file`(본문 수정)로 한다.
- 이미지엔 `alt`(무슨 화면인지)를 붙이고, 여러 장이면 사이에 한 줄 설명을 넣는다.
- 허용: `jpg jpeg png gif webp svg mp4 webm mov m4v ogg`, 최대 300MB. 서버가 파일명을
  GUID로 바꿔 저장한다. 멀티파트가 막힌 환경이면 `--base64`(전송량 +33%).

**받기** — 태스크에 있는 사진을 로컬로 가져온다.
```bash
python "<스킬>/scripts/deskg.py" photos 72                    # 어떤 사진이 어디(본문/진행 N)에 있는지
python "<스킬>/scripts/deskg.py" photos 72 --out-dir ./shots  # 전부 내려받기
python "<스킬>/scripts/deskg.py" photo-download 8f1c….png     # 한 장만 (파일명·URL 아무거나)
```
받은 이미지를 실제로 **보려면 Read 도구로 열어야 한다**(파일만 받아서는 내용을 모른다).
`https://deskg.kr/uploads/…` 를 WebFetch로 직접 열면 로그인 페이지로 튕긴다 — 반드시 헬퍼로 받는다.

## 작업 리포팅 흐름

세부 템플릿과 예시는 **`references/reporting-playbook.md`** 참고. 핵심 규칙:

### 0. 시작 전 — 관련 정보부터 확인 (필수)
계획을 세우기 전에 **먼저 deskG에서 관련 태스크를 검색**한다.
```bash
python "<스킬>/scripts/deskg.py" tasks --q "핵심키워드"
```
- **키워드를 바꿔 2~3번** 검색한다. `q=`는 **제목 + 본문의 짧은 평문 프리뷰(약 140~200자)만**
  매치하고 본문 HTML 깊은 곳은 못 잡는다 — 한 번의 검색으로 없다고 단정하지 말 것.
- 후보가 나오면 바로 판단하지 말고 `task {id}`로 **상세 본문을 열어** 정말 같은 작업인지 확인한다.
- 같은 작업의 태스크가 **이미 있으면** 새로 만들지 말고 그 태스크에 이어서 보고한다.
- 관련(선행/유사) 태스크가 있으면 계획 본문에 링크한다(`https://deskg.kr/{id}`).
- 폴더를 모르면 `folders`로 확인. 태스크는 **하위 폴더가 없는 leaf 폴더에만** 놓을 수 있다(최상위 금지).

### 1. 계획 — 태스크 생성
관련 태스크가 없으면 계획을 담은 태스크를 만든다.
- 제목: `작업 요약 (YYYY-MM-DD)`.
- 본문(HTML, `--html-file`): **목표 / 배경·관련 / 계획(단계) / 완료 기준**. 헤딩·목록으로 읽기 좋게.
- 폴더: 개발 작업은 보통 `defaultFolderId`(설정값). 없으면 `folders`로 leaf 폴더 선택.
- 출력된 태스크 URL을 기억해 둔다(이후 진행/완료 보고와 커밋에 쓴다).

### 2. 진행 보고 — "진행 추가(버전)" vs "코멘트"
진전이 생기면 두 갈래로 판단한다:

- **진행 추가 (`progress`) — 새 버전 스냅샷**: 태스크 **본문이 새 상태로 갱신**될 만한 의미 있는
  진전일 때(계획·문서·산출물이 실제로 진척돼 그 시점을 버전으로 남기고 싶을 때). 갱신된 **본문
  전체**를 넘기면 기존 본문이 이전 버전으로 스냅샷된다. deskG UI '진행' 탭에 번호로 쌓이고 ◁▷로 비교된다.
  ```bash
  python "<스킬>/scripts/deskg.py" progress 72 --html-file prog.html   # --title, --copy-comments 옵션
  ```
  본문은 리치 HTML(`--html-file`) 또는 평문(`--body-file`). 첫 추가면 기존 본문이 진행 1, 새 내용이 진행 2가 된다.
  ⚠️ 진행 추가 API(`POST /tasks/{id}/progress`)가 **배포된 서버**에서만 동작한다. 구버전이면 404 →
  헬퍼가 안내하며, 그 경우 아래 코멘트로 진행 보고한다.
- **코멘트 (`comment`) — 스레드에 보고/논의**: "한 일 / 다음" 같은 **진행 보고**나 질문·메모.
  본문은 그대로 두고 append한다. 의미 있는 진행 보고는 구조화(헤더+한 일+다음)해서, 사소한 메모·질문은 한 줄로.
  ```bash
  python "<스킬>/scripts/deskg.py" comment 72 --body-file note.txt
  ```

판단 기준: **본문 자체가 새 상태로 넘어가면 `progress`**, 그냥 보고·질문·메모면 **`comment`**. 사소한 건
코멘트 한 줄로 충분하다(남발 금지). 코멘트는 **평문**이다(HTML escape, 줄바꿈 유지, `@이름` 멘션 강조) —
읽기 좋게 불릿(`•`)·상태 이모지(▶ ✅ 📌)를 쓴다.

### 3. 완료 — 마무리 코멘트 + 상태
작업이 끝나면 완료 코멘트를 올린다: **한 일 / 결과·검증 / 커밋(있으면)**.
- 배포된 서버면 `patch` 로 **상태·완료도 바꿀 수 있다**(쓰기 전 확인 규칙 적용):
  ```bash
  python "<스킬>/scripts/deskg.py" patch 72 --status 완료 --done true
  ```
- 구버전 서버(`patch` 404)면 완료를 **코멘트 본문에 명확히** 쓰고, 상태 전환은 사람이 UI에서 한다.

## 커밋 메시지 규칙

작업 커밋의 **첫 줄 끝에 태스크 링크**를 붙인다(이 프로젝트의 기존 관행):
```
<작업 요약> https://deskg.kr/{taskId}
```
예: `모바일 웹 개선(...) https://deskg.kr/81`. `https://deskg.kr/{id}`만으로도 라우팅된다.
본문/`Co-Authored-By`는 평소 규칙대로. 커밋 ↔ deskG 태스크를 서로 추적하기 위함이다.

## 원칙·주의

- **키 보안**: 저장소/커밋/메모리에 키를 남기지 않는다. 설정 경로에만.
- **폴더 규칙**: leaf 폴더에만 생성(위반 시 400 + 이유). 최상위·하위폴더 보유 폴더 금지.
- **삭제 없음**: API는 삭제를 제공하지 않는다. 잘못 올렸으면 사용자에게 UI 삭제를 요청.
  **업로드한 사진은 UI로도 못 지운다**(파일 정리 기능 없음) — 올리기 전에 한 번 더 생각할 것.
- **사진 열람 범위**: 파일명이 GUID라 추측은 못 하지만, 파일명을 아는 유효 키/로그인 사용자면
  누구나 볼 수 있다. 민감한 캡처(자격증명·개인정보가 찍힌 화면)는 올리지 않는다.
- **부작용 확인(필수)**: 태스크/코멘트 생성은 실제 게시이며 알림·푸시를 유발한다. 위 **"쓰기 전 확인(필수)"** 규칙을 따른다 — 첫 태스크 생성·모든 코멘트 게시 전 사용자 동의, `--dry-run` 먼저.
- **알림 자동 발생**: 코멘트를 달면 태스크 작성자·`@멘션` 대상에게 알림/푸시가 간다. 불필요한 멘션 주의.

## 참고 문서
- `references/setup.md` — API 키 발급·설정 상세, 사용자별 키 구조.
- `references/reporting-playbook.md` — 계획/진행/코멘트/완료 **템플릿과 예시**.
- `references/api-reference.md` — `/api/v1` 엔드포인트·인증·제약 정리.
