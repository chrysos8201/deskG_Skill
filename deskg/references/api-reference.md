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
| PATCH | `/api/v1/tasks/{id}` | 태스크 수정 `{title?, html?, status?, priority?, milestone?, folderId?, clearFolder?, done?, assigneeId?, clearAssignee?, startDate?, endDate?}` — 준 값만 반영(`""`=해제). 배포된 서버에서만 |
| GET  | `/api/v1/folders` | 폴더 평면 목록 `{id, name, parentId, sortOrder}` — 배포된 서버에서만 |
| GET  | `/api/v1/notifications` | 내 알림(코멘트·@멘션, 최신 100) — 배포된 서버에서만 |
| POST | `/api/v1/photos` | **사진/영상 업로드**(아래 참고) — 배포된 서버에서만 |
| GET  | `/api/v1/photos/{fileName}` | **원본 바이트 내려받기**(Range 지원) — 배포된 서버에서만 |
| GET  | `/api/v1/tasks/{id}/photos` | **태스크의 사진/영상 목록**(본문 + 진행에서 추출) — 배포된 서버에서만 |

### 응답 필드
- 요약: `id, title, author, crumb, status, priority, done, commentCount, createdAt`
- 상세: 위 + `parentId, folderId, body, content(HTML), assigneeName, milestone`
- 생성 결과: `{id, title, crumb, url}` (url은 `/{id}`)
- 코멘트 작성 결과: `{id, body, commentCount}`

## 사진/영상 (photos)

### 업로드 `POST /api/v1/photos` → `201`
두 가지 형식을 다 받는다.
- **multipart/form-data**: `file` 파트 하나. (헬퍼 `photo-upload` 의 기본)
- **application/json**: `{fileName*, contentBase64*, contentType?}` — 표준 라이브러리만으로
  멀티파트를 만들기 어려울 때. `contentBase64` 는 `data:image/png;base64,…` 접두사가 있어도 된다.
  전송량이 33% 늘어난다. (헬퍼 `photo-upload --base64`)

응답:
```json
{ "fileName":"8f1c….png", "url":"/uploads/8f1c….png",
  "downloadUrl":"/api/v1/photos/8f1c….png",
  "contentType":"image/png", "size":20480, "kind":"image" }
```
- `url` → **본문 HTML 에 넣는 경로**. `<img src="/uploads/8f1c….png">` 로 쓰면 UI에 그대로 뜬다.
- `downloadUrl` → **API 키로 받는 경로**. `/uploads/…` 는 로그인 쿠키 전용이라 API 클라이언트가
  직접 열면 로그인 페이지로 리다이렉트된다(302).
- 서버가 파일명을 GUID로 바꿔 저장한다(원본 파일명은 보관하지 않음).

거부(400): 허용 확장자 밖(`jpg jpeg png gif webp svg mp4 webm mov m4v ogg`),
`contentType` 이 image/video 가 아님, 빈 파일, 300MB 초과, 잘못된 base64, `file` 파트 없음.

### 내려받기 `GET /api/v1/photos/{fileName}`
원본 바이트 그대로(`Content-Type` 은 확장자 기준, Range 요청 지원). 없으면 404.
파일명이 GUID라 추측은 불가하지만 **파일명을 아는 유효 키면 누구나 받을 수 있다**
(로그인 사용자 전원이 볼 수 있는 UI와 같은 열람 범위). 민감한 이미지는 올리지 않는다.

### 태스크 사진 목록 `GET /api/v1/tasks/{id}/photos`
본문(`content`)과 **모든 진행 버전**에서 `<img src>` · `<video src|poster>` 를 등장 순서대로
뽑아 준다(같은 URL은 첫 등장만).
```json
[{ "url":"/uploads/8f1c….png", "fileName":"8f1c….png",
   "downloadUrl":"/api/v1/photos/8f1c….png",
   "kind":"image", "source":"content", "progressNumber":null }]
```
- `source` = `content` | `progress`, `progressNumber` 는 진행 번호(본문이면 null).
- 외부 이미지(`https://…`)도 목록에 나오지만 `fileName`/`downloadUrl` 이 `null` → 내려받기 불가.

## 규칙·제약 (스킬 설계에 중요)

- **생성 시에도 메타를 같이 줄 수 있다**: `title/body/html/folderId/parentId` +
  `status/priority/milestone/assigneeId/startDate/endDate/isPrivate`.
- **본문·상태 수정은 `PATCH /tasks/{id}`**(준 값만 반영, `""`=해제). 진전을 버전으로 남기려면
  **진행 추가(`POST …/progress`)**, 보고·논의는 **코멘트**. `PATCH`·`progress`·`folders`·
  `notifications`·`photos` 는 최신 배포 서버에서만 동작(구버전이면 404 → 헬퍼가 안내).
  인가: 공개 태스크 또는 **내** 비공개 태스크만 수정 가능(아니면 403).
- **삭제는 없다.** 태스크·코멘트·업로드 파일 모두 API로 지울 수 없다 → 잘못 올렸으면 UI에서 사람이 지운다.
- **폴더 배치 규칙**(UI와 동일): 태스크는 **leaf 폴더**에만. 최상위 금지, 하위폴더를
  가진 폴더 금지. 위반 시 `400`과 사유 문구.
- **폴더 목록은 `GET /folders`**. 구버전 서버라 404면 `folders` 헬퍼가 태스크들의 `crumb`를
  모아 대표 태스크 상세로 `folderId`를 역추적한다.
- `html`은 서버에서 **정화(Sanitize)** 된다: 허용 태그만 남고 `script/style/on*/class`
  제거, 링크는 `http/https`만. **허용 태그(ContentSanitizer 기준 — 단일 출처):**
  `p, br, hr, h1~h6, strong, b, em, i, u, s, strike, del, ul, ol, li, blockquote,
  pre, code, span, a, img, video`. **허용 속성:** `src, width, height, alt, controls,
  preload, poster, href, rel`. → 사진은 `<img src="/uploads/…" alt="설명" width="600">`,
  영상은 `<video src="/uploads/….mp4" controls poster="/uploads/….png"></video>` 형태로 쓴다.
  `<source>` 태그는 허용 목록에 없어 제거되므로 `<video src=…>` 를 직접 쓸 것.
  `data:` URL 은 스킴 검사에서 잘리므로 이미지는 **반드시 업로드해서 `/uploads/…` 경로로** 넣는다.
- **코멘트에는 이미지를 넣을 수 없다** — 코멘트는 평문이라 `<img>` 가 그대로 글자로 보인다.
  사진을 곁들인 보고는 **진행 추가(`progress`)** 나 **본문 수정(`patch --html-file`)** 으로 한다.
- **코멘트는 평문**으로 저장/표시(HTML escape, 줄바꿈 유지). 코멘트 작성 시
  본문의 `@표시이름` 멘션과 태스크 작성자에게 **알림·웹푸시가 자동 발생**.
- POST에는 계정 단위 레이트리밋이 적용될 수 있다(과도한 연속 생성 주의).

## curl 예시(참고 — 실제로는 헬퍼 사용 권장)
```bash
curl -H "X-Api-Key: dgk_..." https://deskg.kr/api/v1/me
curl -H "X-Api-Key: dgk_..." -H "Content-Type: application/json" \
  -d '{"title":"제목","html":"<p>내용</p>","folderId":4}' \
  https://deskg.kr/api/v1/tasks
curl -H "X-Api-Key: dgk_..." -F "file=@shot.png" https://deskg.kr/api/v1/photos
curl -H "X-Api-Key: dgk_..." -o shot.png https://deskg.kr/api/v1/photos/8f1c….png
```
헬퍼(`scripts/deskg.py`)는 UTF-8·파일 입력·URL 출력·에러 메시지를 처리하므로,
특히 한글/HTML 본문이 있으면 curl보다 헬퍼를 쓴다.
