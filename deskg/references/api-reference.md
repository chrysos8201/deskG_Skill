# deskG `/api/v1` 참고

계정별 API 키로 인증하는 REST API. 도메인 서비스(Task/Folder/Comment)를 그대로
재사용하므로 **UI와 동일한 규칙·알림**이 적용된다. 이 스킬은 이 API만 쓴다.

## 인증
헤더 중 하나:
```
X-Api-Key: dgk_xxxxxxxx...
Authorization: Bearer dgk_xxxxxxxx...
```
쿼리 폴백 `?api_key=`도 있으나 URL에 키가 남으므로 쓰지 않는다.
무효/폐기 키 → `401 {"error": ...}`. 키는 SHA-256 해시만 서버에 저장되고 원문은
발급 시 1회만 표시된다.

## 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET  | `/api/v1/me` | 키 소유 계정: `{userId, name, isAdmin}` |
| GET  | `/api/v1/tasks?q=&folderId=` | 목록(요약). `q`=제목+본문 평문 프리뷰 검색(본문 HTML 전체 아님), `folderId`=폴더 필터 |
| GET  | `/api/v1/tasks/{id}` | 상세(본문 HTML `content` 포함) |
| POST | `/api/v1/tasks` | 생성 `{title*, body?, html?, folderId?, parentId?}` |
| GET  | `/api/v1/tasks/{id}/comments` | 코멘트 목록(기본 스레드) |
| POST | `/api/v1/tasks/{id}/comments` | 코멘트 작성 `{body*}` |
| GET  | `/api/v1/tasks/{id}/progresses` | 진행(버전) 목록 `{id, number, content, author, createdAt}` |
| POST | `/api/v1/tasks/{id}/progress` | 진행 추가 `{html?\|body?, title?, copyComments?, bump?}` — 배포된 서버에서만(구버전 404) |

### 응답 필드
- 요약: `id, title, author, crumb, status, priority, done, commentCount, createdAt`
- 상세: 위 + `parentId, folderId, body, content(HTML), assigneeName, milestone`
- 생성 결과: `{id, title, crumb, url}` (url은 `/{id}`)
- 코멘트 작성 결과: `{id, body, commentCount}`

## 규칙·제약 (스킬 설계에 중요)

- **생성 시 설정 가능한 것은 `title/body/html/folderId/parentId`뿐.**
  상태(status)·우선순위·담당자·완료(done)·마일스톤은 **API로 설정/변경 불가**.
- **본문 수정(PATCH) 없음, 삭제 없음.** 태스크 본문을 직접 고치는 PATCH는 없다. 진전은
  **진행 추가(`POST …/progress`, 새 버전 스냅샷)** 또는 **코멘트**로 남긴다.
  진행 추가는 최신 배포 서버에서만 동작(구버전이면 404 → 코멘트로 대체). 상태/완료(status/done)
  변경도 아직 없어 완료 전환은 UI에서 한다.
- **폴더 배치 규칙**(UI와 동일): 태스크는 **leaf 폴더**에만. 최상위 금지, 하위폴더를
  가진 폴더 금지. 위반 시 `400`과 사유 문구.
- **폴더 목록 엔드포인트가 없다.** folderId를 알아내려면 `folders` 헬퍼를 쓴다
  (태스크들의 `crumb`를 모아 대표 태스크 상세로 `folderId`를 역추적).
- `html`은 서버에서 **정화(Sanitize)** 된다: 허용 태그만 남고 `script/style/on*/class`
  제거, 링크는 `http/https`만. **허용 태그(ContentSanitizer 기준 — 단일 출처):**
  `p, br, hr, h1~h6, strong, b, em, i, u, s, strike, del, ul, ol, li, blockquote,
  pre, code, span, a, img, video`.
- **코멘트는 평문**으로 저장/표시(HTML escape, 줄바꿈 유지). 코멘트 작성 시
  본문의 `@표시이름` 멘션과 태스크 작성자에게 **알림·웹푸시가 자동 발생**.
- POST에는 계정 단위 레이트리밋이 적용될 수 있다(과도한 연속 생성 주의).

## curl 예시(참고 — 실제로는 헬퍼 사용 권장)
```bash
curl -H "X-Api-Key: dgk_..." https://deskg.kr/api/v1/me
curl -H "X-Api-Key: dgk_..." -H "Content-Type: application/json" \
  -d '{"title":"제목","html":"<p>내용</p>","folderId":4}' \
  https://deskg.kr/api/v1/tasks
```
헬퍼(`scripts/deskg.py`)는 UTF-8·파일 입력·URL 출력·에러 메시지를 처리하므로,
특히 한글/HTML 본문이 있으면 curl보다 헬퍼를 쓴다.
