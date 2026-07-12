# deskG Skill

deskG(https://deskg.kr) 작업을 **태스크로 리포팅**하기 위한 Claude 전용 스킬.
계정별 **API 키**만으로 동작하며, deskG 서버 코드는 건드리지 않는다(기존 `/api/v1` REST API 사용).

이 스킬을 켜면 Claude가 작업할 때:
1. **시작 전** deskG에서 관련/중복 태스크를 먼저 검색하고,
2. **계획**을 태스크로 만들고,
3. 진전이 있으면 **진행 보고**, 사소하면 **코멘트만** 올리고,
4. 끝나면 **완료 코멘트**를 남기고,
5. **커밋 메시지 첫 줄에 태스크 링크**를 붙인다.

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
`deskg/` 폴더를 Claude Code 스킬 경로에 둔다:

- 사용자 전역: `~/.claude/skills/deskg/`  (`~/.claude/skills/deskg/SKILL.md` 가 되도록)
- 또는 프로젝트: `<repo>/.claude/skills/deskg/`

예(전역 설치):
```bash
git clone git@github.com:chrysos8201/deskG_Skill.git
cp -r deskG_Skill/deskg ~/.claude/skills/deskg
```
설치 후 `/deskg` 로 호출하거나, deskG 관련 작업 맥락에서 자동으로 쓰인다.

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
- 현재 API는 태스크/코멘트 **생성과 조회**만 지원한다(수정·삭제·상태변경·진행버전
  쓰기 없음). 그래서 "진행 추가"는 구조화된 코멘트로 표현하고, 완료 상태 전환은
  사람이 UI에서 한다.
