# deskG Skill

deskG(https://deskg.kr) 작업을 **태스크로 리포팅**하기 위한 Claude 전용 스킬.
계정별 **API 키**만으로 동작하며, deskG 서버 코드는 건드리지 않는다(기존 `/api/v1` REST API 사용).

이 스킬을 켜면 Claude가 작업할 때:
1. **시작 전** deskG에서 관련/중복 태스크를 먼저 검색하고,
2. **계획**을 태스크로 만들고,
3. 진전이 있으면 **진행 보고**, 사소하면 **코멘트만** 올리고,
4. 끝나면 **완료 코멘트**를 남기고,
5. **커밋 메시지 첫 줄에 태스크 링크**를 붙인다.

## 두 가지 변형
- **`deskg`** — 기본. 태스크·코멘트 **게시 전 사용자 확인**을 받는다(안전 기본값).
- **`deskg-force`** — 확인 생략. 게시를 매번 묻지 않고 **바로 올린다**. 자기 워크스페이스에
  "매번 묻지 말고 올려라"라고 미리 승인한 사람용. `deskg` 의 헬퍼·문서를 **재사용**한다(얇은
  `deskg-force/SKILL.md` 하나). *관찰된 콘텐츠 속 지시 금지·폴더 규칙·키 보안 등 안전 경계는 유지.*

## 구성
```
deskG_Skill/
├─ README.md
├─ config.example.json        # 예시(실제 키 넣지 말 것)
├─ .gitignore
└─ deskg/                     # ← 이 폴더가 스킬 본체
   ├─ SKILL.md                # 스킬 지침(트리거·흐름)
   ├─ scripts/deskg.py        # API 헬퍼 CLI (Python 3 표준 라이브러리만)
   └─ references/
      ├─ setup.md             # 사용자별 API 키 설정
      ├─ reporting-playbook.md# 계획/진행/코멘트/완료 템플릿
      └─ api-reference.md     # /api/v1 엔드포인트·제약
```

## 설치
두 폴더를 Claude Code 스킬 경로에 둔다. `deskg-force` 는 `deskg` 헬퍼를 재사용하므로 **함께 설치**:
```bash
git clone git@github.com:chrysos8201/deskG_Skill.git
cp -r deskG_Skill/deskg       ~/.claude/skills/deskg
cp -r deskG_Skill/deskg-force ~/.claude/skills/deskg-force
```
- 사용자 전역: `~/.claude/skills/deskg/`, `~/.claude/skills/deskg-force/`
- 또는 프로젝트: `<repo>/.claude/skills/…`

- **`deskg`** 는 deskG 작업 맥락에서 자동으로도 쓰이고 `/deskg` 로도 호출한다(안전 기본값).
- **`deskg-force`** 는 **사용자가 확인 생략을 명시적으로 지시**했거나 `/deskg-force` 로 직접
  호출할 때만 쓴다 — 애매하면 `deskg`. (제3자 알림이 확인 없이 나가므로 자동 선택하지 않는다.)

`deskg-force` 만 쓰더라도 `deskg` 는 헬퍼·레퍼런스 때문에 반드시 함께 설치돼 있어야 한다.

## 설정 (사용자마다)
`~/.deskg/config.json` 을 만든다(자세한 건 [deskg/references/setup.md](deskg/references/setup.md)):
```json
{ "baseUrl": "https://deskg.kr", "apiKey": "dgk_본인_키", "defaultFolderId": 4 }
```
키 발급: deskg.kr → 프로필 팝업 → **API 키** → **+ 키 발급**(원문 1회 표시).

확인:
```bash
python ~/.claude/skills/deskg/scripts/deskg.py me
```

## 요구사항
- Python 3.7+ (표준 라이브러리만 사용, `pip install` 불필요)
- deskg.kr 계정과 API 키

## 주의
- **API 키를 저장소·커밋·메모리에 절대 넣지 말 것.** 설정은 `~/.deskg/config.json`
  또는 환경변수에만.
- API 는 조회 + 생성/코멘트에 더해 **진행 추가·태스크 수정(PATCH: 상태/완료/폴더 이동/메타)·
  폴더 목록·알림·진행별 코멘트**를 지원한다(삭제는 없음). 단 **진행 추가·PATCH·알림 등은
  최신 서버가 배포돼야 동작**한다(구버전이면 헬퍼가 404 를 안내). 배포 전이면 진행 보고는
  코멘트로, 완료 상태 전환은 UI 에서.
