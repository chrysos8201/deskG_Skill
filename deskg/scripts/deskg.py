#!/usr/bin/env python3
"""
deskg.py — deskG(/api/v1) CLI helper for the deskG Claude skill.

Uses ONLY the Python 3 standard library (no pip install needed).
Talks to the per-account API-key REST API of deskG (https://deskg.kr).

Config resolution (first hit wins), so every user brings their own key:
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
  folders                  Derive folderId<->folder map from existing tasks
                           (the API has no folder-list endpoint).
  new  --title T (--html-file F | --body-file F | --body T)
       [--folder ID] [--parent ID] [--dry-run]     Create a task (the "plan").
  comment ID (--body-file F | --body T) [--dry-run] Add a comment / progress note.

Bodies are read from files by default to avoid shell-quoting problems with
Korean text / HTML on Windows PowerShell. Always writes/reads UTF-8.
"""
import argparse
import json
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


def request(method, path, base, key, payload=None, soft=False):
    """Do one API call. Returns (status, parsed_json_or_None).

    On failure it prints a clean error and exits — unless soft=True, in which
    case it returns (status_or_None, None) so callers (e.g. `folders`) can keep
    going after a single failed request instead of aborting the whole command.
    """
    url = base + path
    data = None
    headers = {
        "X-Api-Key": key,
        "Accept": "application/json",
        "User-Agent": "deskg-skill/1.0",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if soft:
            return e.code, None
        raw = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(raw).get("error", raw)
        except Exception:
            detail = raw[:500]
        die(f"HTTP {e.code} on {method} {path}: {detail}", code=2)
    except OSError as e:
        # URLError, socket/read timeout (TimeoutError), connection reset — all OSError.
        if soft:
            return None, None
        reason = getattr(e, "reason", None) or e
        die(f"network error reaching {url}: {reason}", code=3)

    if not raw.strip():
        return status, None
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        if soft:
            return status, None
        die(f"non-JSON response (HTTP {status}) from {method} {path}: {raw[:300]}", code=2)


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


def cmd_folders(args, base, key, folder):
    """No folder-list endpoint exists — derive crumb<->folderId from tasks."""
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
    return p


def main():
    args = build_parser().parse_args()
    base, key, folder = load_config()
    {
        "me": cmd_me,
        "tasks": cmd_tasks,
        "task": cmd_task,
        "comments": cmd_comments,
        "folders": cmd_folders,
        "new": cmd_new,
        "comment": cmd_comment,
    }[args.cmd](args, base, key, folder)


if __name__ == "__main__":
    main()
