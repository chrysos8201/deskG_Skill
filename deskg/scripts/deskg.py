#!/usr/bin/env python3
"""
deskg.py — deskG(/api/v1) CLI helper for the deskG Claude skill.

Uses ONLY the Python 3 standard library (no pip install needed).
Talks to the per-account API-key REST API of deskG (https://deskg.kr).

Config sources are MERGED (env wins, lower sources fill the gaps), so every
user brings their own key. Precedence, high -> low:
  1. Environment:  DESKG_API_KEY, DESKG_BASE_URL, DESKG_FOLDER_ID
  2. $DESKG_CONFIG          (path to a JSON file)
  3. ~/.deskg/config.json
  4. <this-skill>/config.local.json   (gitignored fallback)

Config JSON shape:
  { "baseUrl": "https://deskg.kr", "apiKey": "dgk_...", "defaultFolderId": 4 }

Subcommands:
  me                       Verify the key, print the owning account.
  tasks [--q T] [--folder ID]     List / search tasks (summary).
  task ID                  Show one task (detail, incl. body).
  comments ID / progresses ID     Read a task's comment thread / versions.
  folders                  Derive folderId<->folder map from existing tasks.
  notifications            My notifications (comments / @mentions).
  new  --title T (--html-file F | --body-file F | --body T)
       [--folder ID] [--parent ID] [--dry-run]     Create a task (the "plan").
  comment ID (--body-file F | --body T) [--dry-run] Add a comment / progress note.
  progress ID (--html-file F | --body-file F)      Add a progress version.
  patch ID [--status S] [--done true|false] …      Update a task.
  photo-upload FILE [FILE …] [--base64] [--dry-run]  Upload photos/videos.
  photo-download REF [--out F]      Download one photo by fileName / URL.
  photos ID [--out-dir D]           List (and optionally fetch) a task's photos.

Bodies are read from files by default to avoid shell-quoting problems with
Korean text / HTML on Windows PowerShell. Always writes/reads UTF-8.
"""
import argparse
import json
import mimetypes
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

# Korean / emoji output must not die on a cp949 console.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_BASE = "https://deskg.kr"


def _skill_local_config():
    # <skill>/config.local.json  (scripts/ is one level under the skill root)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "config.local.json")


def load_config():
    """Return (base_url, api_key, default_folder_id). Env overrides files.

    File sources are *merged* (a partial file — e.g. baseUrl but no apiKey —
    does not shadow a key present in a lower-precedence file). Precedence,
    high -> low:  env > $DESKG_CONFIG > ~/.deskg/config.json > <skill>/config.local.json
    """
    cfg = {}
    # Apply lowest precedence first so higher sources overwrite; skip empty
    # values so a partial file never wipes a value set by a lower source.
    for path in (
        _skill_local_config(),
        os.path.expanduser("~/.deskg/config.json"),
        os.environ.get("DESKG_CONFIG"),
    ):
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                die(f"config file {path} is not valid JSON: {e}")
            cfg.update({k: v for k, v in data.items() if v not in (None, "")})

    base = os.environ.get("DESKG_BASE_URL") or cfg.get("baseUrl") or DEFAULT_BASE
    key = os.environ.get("DESKG_API_KEY") or cfg.get("apiKey")

    folder_env = os.environ.get("DESKG_FOLDER_ID")
    if folder_env and folder_env.strip():
        try:
            folder = int(folder_env.strip())
        except ValueError:
            die("DESKG_FOLDER_ID must be an integer")
    else:
        folder = cfg.get("defaultFolderId")

    if not key:
        die(
            "No API key found. Set one of:\n"
            "  - env DESKG_API_KEY=dgk_...\n"
            "  - ~/.deskg/config.json  ->  {\"apiKey\": \"dgk_...\", \"defaultFolderId\": 4}\n"
            "Get a key at deskg.kr: profile popup -> API 키 -> + 키 발급 (shown once)."
        )
    return base.rstrip("/"), key, folder


def die(msg, code=1):
    print(f"deskg: {msg}", file=sys.stderr)
    sys.exit(code)


def send(method, path, base, key, data=None, content_type=None,
         accept="application/json", timeout=30, soft=False, soft_codes=None):
    """Do one API call and return (status, raw_bytes, content_type). Binary-safe.

    On failure it prints a clean error and exits — unless soft=True, in which
    case it returns (status_or_None, None, None) so callers (e.g. `folders`) can
    keep going after a single failed request instead of aborting the whole
    command. soft_codes=(404,) swallows only those status codes, so the server's
    own error text still surfaces for everything else (e.g. a 400 "too large").

    Note the content_type: a server without the endpoint deployed answers the
    Blazor fallback route and *redirects to the login page* — HTTP 200 with
    HTML. Callers must check the type, or they'd save a login page as a .png.
    """
    url = base + path
    headers = {
        "X-Api-Key": key,
        "Accept": accept,
        "User-Agent": "deskg-skill/1.0",
    }
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), (resp.headers.get_content_type() or "")
    except urllib.error.HTTPError as e:
        if soft or (soft_codes and e.code in soft_codes):
            return e.code, None, None
        raw = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(raw).get("error", raw)
        except Exception:
            detail = raw[:500]
        die(f"HTTP {e.code} on {method} {path}: {detail}", code=2)
    except OSError as e:
        # URLError, socket/read timeout (TimeoutError), connection reset — all OSError.
        if soft:
            return None, None, None
        reason = getattr(e, "reason", None) or e
        die(f"network error reaching {url}: {reason}", code=3)


def request(method, path, base, key, payload=None, soft=False, soft_codes=None):
    """JSON call. Returns (status, parsed_json_or_None). See send() for errors."""
    data = ctype = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ctype = "application/json"
    status, raw, got = send(method, path, base, key, data, ctype, soft=soft, soft_codes=soft_codes)
    if raw is None:
        return status, None
    text = raw.decode("utf-8", "replace")
    if not text.strip():
        return status, None
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        if soft or (soft_codes and got == "text/html"):
            # 엔드포인트 미배포 → Blazor 폴백이 로그인 페이지(HTML 200)를 준다.
            return status, None
        die(f"non-JSON response (HTTP {status}) from {method} {path}: {text[:300]}", code=2)


def read_text_arg(inline, file_path, what):
    if file_path:
        if not os.path.isfile(file_path):
            die(f"{what} file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    if inline is not None:
        return inline
    return None


# ── commands ─────────────────────────────────────────────────────────────

def cmd_me(args, base, key, folder):
    _, me = request("GET", "/api/v1/me", base, key)
    print(json.dumps(me, ensure_ascii=False, indent=2))


def cmd_tasks(args, base, key, folder):
    qs = {}
    if args.q:
        qs["q"] = args.q
    if args.folder is not None:
        qs["folderId"] = args.folder
    path = "/api/v1/tasks"
    if qs:
        path += "?" + urllib.parse.urlencode(qs)
    _, tasks = request("GET", path, base, key)
    if args.json:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
        return
    if not tasks:
        print("(no tasks)")
        return
    for t in tasks:
        status = t.get("status") or "-"
        done = "✓" if t.get("done") else " "
        print(f"[{done}] #{t['id']:<4} {t['title']}")
        print(f"        {t['crumb']}  ·  status={status}  ·  comments={t['commentCount']}  ·  {base}/{t['id']}")


def cmd_task(args, base, key, folder):
    _, t = request("GET", f"/api/v1/tasks/{args.id}", base, key)
    if args.json:
        print(json.dumps(t, ensure_ascii=False, indent=2))
        return
    print(f"#{t['id']}  {t['title']}")
    print(f"url:      {base}/{t['id']}")
    print(f"crumb:    {t['crumb']}   (folderId={t.get('folderId')})")
    print(f"author:   {t['author']}   status={t.get('status')}   priority={t.get('priority')}   done={t.get('done')}")
    if t.get("assigneeName"):
        print(f"assignee: {t['assigneeName']}")
    if t.get("milestone"):
        print(f"milestone:{t['milestone']}")
    print(f"comments: {t['commentCount']}")
    print("--- content (html) ---")
    print(t.get("content") or "(empty)")


def cmd_comments(args, base, key, folder):
    _, rows = request("GET", f"/api/v1/tasks/{args.id}/comments", base, key)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("(no comments)")
        return
    for c in rows:
        print(f"— {c['author']}  ·  {c['createdAt']}  (#{c['id']})")
        print(c["body"])
        print()


def cmd_progresses(args, base, key, folder):
    _, rows = request("GET", f"/api/v1/tasks/{args.id}/progresses", base, key)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("(no progresses — 아직 진행 버전이 없는 태스크. 코멘트만 있을 수 있음)")
        return
    for p in rows:
        print(f"— 진행 {p['number']}  ·  {p['author']}  ·  {p['createdAt']}  (#{p['id']})")
        print(p["content"])
        print()


def cmd_progress(args, base, key, folder):
    html = read_text_arg(None, args.html_file, "html")
    body = read_text_arg(args.body, args.body_file, "body")
    if (not html or not html.strip()) and (not body or not body.strip()):
        die("진행 내용을 --html-file / --body-file / --body 중 하나로 제공하세요")
    payload = {}
    if html is not None:
        payload["html"] = html
    if body is not None:
        payload["body"] = body
    if args.title:
        payload["title"] = args.title
    if args.copy_comments:
        payload["copyComments"] = True
    if args.no_bump:
        payload["bump"] = False

    if args.dry_run:
        print(f"[dry-run] POST /api/v1/tasks/{args.id}/progress")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    status, res = request("POST", f"/api/v1/tasks/{args.id}/progress", base, key, payload, soft=True)
    if res is None:
        die("진행 추가 실패. 서버에 진행 추가 API(POST /tasks/{id}/progress)가 배포됐는지 확인하세요"
            " (구버전 서버면 404 — 그럴 땐 comment 로 진행 보고).")
    print(f"진행 {res['number']} 추가됨 (#{res['id']})")
    print(f"url: {base}/{args.id}")


def cmd_notifications(args, base, key, folder):
    _, rows = request("GET", "/api/v1/notifications", base, key, soft=True)
    if rows is None:
        die("알림 조회 실패. 서버에 GET /notifications 가 배포됐는지 확인하세요 (구버전 404).")
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("(no notifications)")
        return
    for n in rows:
        print(f"— [{n['kind']}] {n['actorName']}  ·  {n['taskTitle']} (#{n['taskId']})  ·  {n['createdAt']}")
        print(f"  {n['preview']}")


def cmd_patch(args, base, key, folder):
    payload = {}
    if args.title is not None:
        payload["title"] = args.title
    html = read_text_arg(None, args.html_file, "html")
    if html is not None:
        payload["html"] = html
    if args.status is not None:
        payload["status"] = args.status
    if args.priority is not None:
        payload["priority"] = args.priority
    if args.milestone is not None:
        payload["milestone"] = args.milestone
    if args.done is not None:
        payload["done"] = args.done == "true"
    if args.folder is not None:
        payload["folderId"] = args.folder
    if args.clear_folder:
        payload["clearFolder"] = True
    if args.assignee is not None:
        payload["assigneeId"] = args.assignee
    if not payload:
        die("변경할 필드를 하나 이상 지정하세요 (--status/--done/--title/--html-file/--folder/…)")

    if args.dry_run:
        print(f"[dry-run] PATCH /api/v1/tasks/{args.id}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    _, res = request("PATCH", f"/api/v1/tasks/{args.id}", base, key, payload, soft=True)
    if res is None:
        die("태스크 수정 실패. 서버에 PATCH /tasks/{id} 가 배포됐는지 확인하세요 (구버전 404).")
    print(f"태스크 #{args.id} 수정됨 — status={res.get('status')} priority={res.get('priority')} done={res.get('done')}")
    print(f"url: {base}/{args.id}")


def cmd_folders(args, base, key, folder):
    """Derive crumb<->folderId from tasks (works even on servers without GET /folders)."""
    _, tasks = request("GET", "/api/v1/tasks", base, key)
    by_crumb = {}
    for t in tasks or []:
        by_crumb.setdefault(t["crumb"], []).append(t["id"])
    rows = []
    for crumb, ids in by_crumb.items():
        # one detail call per crumb to read its folderId; soft so one failed
        # lookup (rate limit / just-deleted task) doesn't abort the whole map.
        _, d = request("GET", f"/api/v1/tasks/{max(ids)}", base, key, soft=True)
        rows.append((d.get("folderId") if d else "?", crumb, len(ids)))
    # ints first (by value), then "?" for lookups that failed
    rows.sort(key=lambda r: (0, r[0]) if isinstance(r[0], int) else (1, 0))
    print("folderId  count  crumb")
    for fid, crumb, n in rows:
        print(f"{str(fid):>7}  {n:>5}  {crumb}")
    print("\nNote: new tasks can only be placed in a LEAF folder (no subfolders),")
    print("never at top level. Pick a leaf folderId above for --folder / defaultFolderId.")
    print("A folder with no tasks yet won't appear here — ask the user for its folderId.")


def cmd_new(args, base, key, folder):
    if not args.title or not args.title.strip():
        die("--title is required")
    html = read_text_arg(None, args.html_file, "html")
    body = read_text_arg(args.body, args.body_file, "body")
    fid = args.folder if args.folder is not None else folder
    payload = {"title": args.title}
    if html is not None:
        payload["html"] = html
    if body is not None:
        payload["body"] = body
    if fid is not None:
        payload["folderId"] = fid
    if args.parent is not None:
        payload["parentId"] = args.parent

    if args.dry_run:
        print("[dry-run] POST /api/v1/tasks")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    _, res = request("POST", "/api/v1/tasks", base, key, payload)
    print(f"created task #{res['id']}")
    print(f"url:   {base}/{res['id']}")
    print(f"crumb: {res.get('crumb') or '(unfiled)'}")


def cmd_comment(args, base, key, folder):
    body = read_text_arg(args.body, args.body_file, "body")
    if body is None or not body.strip():
        die("provide comment text via --body or --body-file")
    payload = {"body": body}
    if args.dry_run:
        print(f"[dry-run] POST /api/v1/tasks/{args.id}/comments")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    _, res = request("POST", f"/api/v1/tasks/{args.id}/comments", base, key, payload)
    print(f"commented on #{args.id}  (now {res.get('commentCount')} comments)")
    print(f"url: {base}/{args.id}")


# ── photos ───────────────────────────────────────────────────────────────

# 서버가 받아주는 확장자(MediaService 와 동일). 서버가 최종 판정하지만,
# 올리기 전에 걸러주면 왕복 한 번을 아낀다.
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
              ".mp4", ".webm", ".mov", ".m4v", ".ogg"}


def ascii_filename(path):
    """멀티파트 헤더에 넣을 안전한 파일명. 서버는 GUID 로 다시 저장하므로 확장자만 중요."""
    name = os.path.basename(path)
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        name = "upload" + os.path.splitext(name)[1].lower()
    return name.replace('"', "").replace("\r", "").replace("\n", "")


def build_multipart(path):
    """(body_bytes, content_type) — file 파트 하나짜리 multipart/form-data."""
    with open(path, "rb") as f:
        blob = f.read()
    name = ascii_filename(path)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    boundary = "----deskg" + os.urandom(12).hex()
    head = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n").encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + blob + tail, "multipart/form-data; boundary=" + boundary


def photo_ref_to_name(ref):
    """fileName / /uploads/x.png / /api/v1/photos/x.png / https://deskg.kr/uploads/x.png → 파일명."""
    ref = ref.strip()
    if "://" in ref:
        ref = urllib.parse.urlparse(ref).path
    ref = ref.split("?")[0].split("#")[0]
    name = ref.rsplit("/", 1)[-1]
    if not name:
        die(f"사진 파일명을 알 수 없습니다: {ref}")
    return name


def cmd_photo_upload(args, base, key, folder):
    import base64 as _b64
    out = []
    for path in args.files:
        if not os.path.isfile(path):
            die(f"파일을 찾을 수 없습니다: {path}")
        ext = os.path.splitext(path)[1].lower()
        if ext not in PHOTO_EXTS:
            die(f"허용되지 않는 형식입니다: {ext or '(확장자 없음)'} — 허용: {' '.join(sorted(PHOTO_EXTS))}")
        size = os.path.getsize(path)
        if args.dry_run:
            print(f"[dry-run] POST /api/v1/photos  ← {path} ({size:,} bytes)")
            continue

        if args.base64:
            # 멀티파트를 못 쓰는 환경용 폴백(전송량 +33%).
            with open(path, "rb") as f:
                payload = {"fileName": ascii_filename(path),
                           "contentType": mimetypes.guess_type(path)[0],
                           "contentBase64": _b64.b64encode(f.read()).decode("ascii")}
            _, res = request("POST", "/api/v1/photos", base, key, payload, soft_codes=(404,))
        else:
            body, ctype = build_multipart(path)
            _, raw, got = send("POST", "/api/v1/photos", base, key, body, ctype,
                               timeout=300, soft_codes=(404,))
            try:
                res = json.loads(raw.decode("utf-8", "replace")) if raw else None
            except json.JSONDecodeError:
                res = None      # 미배포 서버가 로그인 HTML 을 200 으로 돌려준 경우
        if res is None:
            die("업로드 실패. 서버에 사진 API(POST /api/v1/photos)가 배포됐는지 확인하세요"
                " — 미배포면 404 이거나 로그인 페이지(HTML)가 돌아옵니다.")
        out.append(res)
        print(f"업로드됨: {os.path.basename(path)} → {res['fileName']}  ({res['size']:,} bytes, {res['kind']})")
        print(f"  본문에 넣을 태그: <img src=\"{res['url']}\">" if res["kind"] == "image"
              else f"  본문에 넣을 태그: <video src=\"{res['url']}\" controls></video>")
        print(f"  다시 받기: photo-download {res['fileName']}")
    if args.json and out:
        print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_photo_download(args, base, key, folder):
    name = photo_ref_to_name(args.ref)
    dest = args.out or name
    status, raw, got = send("GET", "/api/v1/photos/" + urllib.parse.quote(name), base, key,
                            accept="*/*", timeout=300, soft_codes=(404,))
    if raw is None or got == "text/html":
        # HTML 이면 미배포 서버의 로그인 페이지 — 그걸 .png 로 저장해선 안 된다.
        die(f"내려받기 실패(HTTP {status}). 파일명이 맞는지, 서버에 사진 API 가 배포됐는지 확인하세요.")
    d = os.path.dirname(os.path.abspath(dest))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(raw)
    print(f"저장됨: {dest}  ({len(raw):,} bytes)")


def cmd_photos(args, base, key, folder):
    _, rows = request("GET", f"/api/v1/tasks/{args.id}/photos", base, key, soft_codes=(404,))
    if rows is None:
        die(f"사진 목록 조회 실패(404). 태스크 #{args.id} 가 없거나, 서버에"
            " GET /tasks/{id}/photos 가 아직 배포되지 않았습니다.")
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("(no photos — 본문·진행에 이미지/영상이 없음)")
        return
    for r in rows:
        where = "본문" if r["source"] == "content" else f"진행 {r.get('progressNumber')}"
        print(f"— [{r['kind']}] {r['url']}   ({where})")
    if not args.out_dir:
        return
    os.makedirs(args.out_dir, exist_ok=True)
    got = 0
    for r in rows:
        if not r.get("fileName"):
            print(f"  건너뜀(외부 URL): {r['url']}")   # deskG 업로드가 아닌 이미지
            continue
        status, raw, ctype = send("GET", "/api/v1/photos/" + urllib.parse.quote(r["fileName"]),
                                  base, key, accept="*/*", timeout=300, soft=True)
        if raw is None or ctype == "text/html":
            print(f"  실패(HTTP {status}): {r['fileName']}")
            continue
        dest = os.path.join(args.out_dir, r["fileName"])
        with open(dest, "wb") as f:
            f.write(raw)
        got += 1
        print(f"  저장됨: {dest}  ({len(raw):,} bytes)")
    print(f"{got}개 내려받음 → {args.out_dir}")


def build_parser():
    p = argparse.ArgumentParser(prog="deskg", description="deskG /api/v1 CLI helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("me", help="verify key, show account")

    sp = sub.add_parser("tasks", help="list/search tasks")
    sp.add_argument("--q", help="search title/body")
    sp.add_argument("--folder", type=int, help="filter by folderId")
    sp.add_argument("--json", action="store_true")

    sp = sub.add_parser("task", help="show one task")
    sp.add_argument("id", type=int)
    sp.add_argument("--json", action="store_true")

    sp = sub.add_parser("comments", help="list a task's comments (progress thread)")
    sp.add_argument("id", type=int)
    sp.add_argument("--json", action="store_true")

    sp = sub.add_parser("progresses", help="list a task's progress versions")
    sp.add_argument("id", type=int)
    sp.add_argument("--json", action="store_true")

    sp = sub.add_parser("progress", help="add a progress version (진행 추가)")
    sp.add_argument("id", type=int)
    sp.add_argument("--html-file", dest="html_file", help="file with HTML progress content")
    sp.add_argument("--body-file", dest="body_file", help="file with plain progress content")
    sp.add_argument("--body", help="inline plain content (prefer files)")
    sp.add_argument("--title", help="also update the task title")
    sp.add_argument("--copy-comments", dest="copy_comments", action="store_true",
                    help="copy the previous version's comments into this one")
    sp.add_argument("--no-bump", dest="no_bump", action="store_true",
                    help="do not bump the task to the top of the feed")
    sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("patch", help="update a task (status/done/title/html/folder/priority/…)")
    sp.add_argument("id", type=int)
    sp.add_argument("--title")
    sp.add_argument("--html-file", dest="html_file", help="file with new HTML body")
    sp.add_argument("--status", help="시작전 / 진행 중 / 검수중 / 완료 (또는 '' 로 해제)")
    sp.add_argument("--priority", help="S / A / B / C (또는 '' 로 해제)")
    sp.add_argument("--milestone")
    sp.add_argument("--done", choices=["true", "false"], help="완료 여부")
    sp.add_argument("--folder", type=int, help="folderId 로 이동")
    sp.add_argument("--clear-folder", dest="clear_folder", action="store_true", help="미분류로 이동")
    sp.add_argument("--assignee", help="담당자 userId ('' 로 해제)")
    sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("notifications", help="list my notifications (comments/@mentions)")
    sp.add_argument("--json", action="store_true")

    sub.add_parser("folders", help="derive folderId<->folder map from tasks")

    sp = sub.add_parser("new", help="create a task (the plan)")
    sp.add_argument("--title", required=True)
    sp.add_argument("--html-file", dest="html_file", help="file with HTML body (rich)")
    sp.add_argument("--body-file", dest="body_file", help="file with plain body")
    sp.add_argument("--body", help="inline plain body (prefer --html-file/--body-file)")
    sp.add_argument("--folder", type=int, help="folderId (default: config defaultFolderId)")
    sp.add_argument("--parent", type=int, help="parent task id (subtask)")
    sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("comment", help="add a comment / progress note")
    sp.add_argument("id", type=int)
    sp.add_argument("--body-file", dest="body_file", help="file with comment text")
    sp.add_argument("--body", help="inline comment text")
    sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("photo-upload", help="upload photo(s)/video(s), print the URL to embed")
    sp.add_argument("files", nargs="+", help="local image/video file(s)")
    sp.add_argument("--base64", action="store_true",
                    help="send as JSON base64 instead of multipart (fallback, +33%% traffic)")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("photo-download", help="download one photo by fileName or URL")
    sp.add_argument("ref", help="fileName, /uploads/x.png, /api/v1/photos/x.png or a full URL")
    sp.add_argument("--out", help="output path (default: the file name)")

    sp = sub.add_parser("photos", help="list a task's photos/videos (body + progress versions)")
    sp.add_argument("id", type=int)
    sp.add_argument("--out-dir", dest="out_dir", help="also download them into this directory")
    sp.add_argument("--json", action="store_true")
    return p


def main():
    args = build_parser().parse_args()
    base, key, folder = load_config()
    {
        "me": cmd_me,
        "tasks": cmd_tasks,
        "task": cmd_task,
        "comments": cmd_comments,
        "progresses": cmd_progresses,
        "progress": cmd_progress,
        "patch": cmd_patch,
        "notifications": cmd_notifications,
        "folders": cmd_folders,
        "new": cmd_new,
        "comment": cmd_comment,
        "photo-upload": cmd_photo_upload,
        "photo-download": cmd_photo_download,
        "photos": cmd_photos,
    }[args.cmd](args, base, key, folder)


if __name__ == "__main__":
    main()
