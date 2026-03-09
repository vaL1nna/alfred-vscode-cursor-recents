#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

HOME = Path.home()
EDITOR = (sys.argv[1] if len(sys.argv) > 1 else "code").strip().lower()
QUERY = (sys.argv[2] if len(sys.argv) > 2 else "")
Q = QUERY.strip().lower()


def env_or(default, *names):
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return default


CONFIG = {
    "code": {
        "display": "VS Code",
        "app_name": env_or("Visual Studio Code", "vscode_app_name", "VSCODE_APP_NAME"),
        "storage": [
            env_or(str(HOME / "Library/Application Support/Code/User/globalStorage/storage.json"), "vscode_storage_path", "VSCODE_STORAGE_PATH"),
            str(HOME / "Library/Application Support/Code/storage.json"),
            str(HOME / "Library/Application Support/Code - Insiders/User/globalStorage/storage.json"),
            str(HOME / "Library/Application Support/VSCodium/User/globalStorage/storage.json"),
        ],
    },
    "cursor": {
        "display": "Cursor",
        "app_name": env_or("Cursor", "cursor_app_name", "CURSOR_APP_NAME"),
        "storage": [
            env_or(str(HOME / "Library/Application Support/Cursor/User/globalStorage/storage.json"), "cursor_storage_path", "CURSOR_STORAGE_PATH"),
            str(HOME / "Library/Application Support/Cursor/storage.json"),
            str(HOME / "Library/Application Support/Cursor - Insiders/User/globalStorage/storage.json"),
        ],
    },
}

CFG = CONFIG.get(EDITOR, CONFIG["code"])


def shorten_home(path_str):
    home = str(HOME)
    return path_str.replace(home, "~", 1) if path_str.startswith(home) else path_str


def load_storage():
    for candidate in CFG["storage"]:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8")), str(path)
            except Exception:
                pass
    return None, None


def menu_recent_items(data):
    try:
        file_items = data["lastKnownMenubarData"]["menus"]["File"]["items"]
    except Exception:
        return []

    recent = []

    def walk(items):
        for item in items or []:
            if item.get("label") == "Open &&Recent":
                submenu = (item.get("submenu") or {}).get("items") or []
                for sub in submenu:
                    item_id = sub.get("id")
                    uri = sub.get("uri") or {}
                    if uri.get("scheme") != "file":
                        continue
                    path_str = uri.get("path")
                    if not path_str:
                        continue
                    if item_id == "openRecentFolder":
                        kind = "folder"
                    elif path_str.endswith(".code-workspace"):
                        kind = "workspace"
                    else:
                        continue
                    title = os.path.basename(path_str.rstrip("/")) or path_str
                    recent.append({
                        "uid": "%s:%s:%s" % (EDITOR, kind, path_str),
                        "title": title,
                        "subtitle": "%s • %s" % ("Workspace" if kind == "workspace" else "Folder", shorten_home(path_str)),
                        "arg": path_str,
                        "kind": kind,
                    })
                return
            submenu = (item.get("submenu") or {}).get("items")
            if submenu:
                walk(submenu)

    walk(file_items)

    dedup = []
    seen = set()
    for item in recent:
        if item["arg"] in seen:
            continue
        seen.add(item["arg"])
        dedup.append(item)
    return dedup


def normalize_segment(seg):
    return seg.strip().lstrip('.').lower()


def score_item(item, q):
    if not q:
        return 0
    title = item["title"].lower()
    base = os.path.basename(item["arg"].rstrip("/")).lower()

    if title == q or base == q:
        return 0
    if title.startswith(q) or base.startswith(q):
        return 10
    title_words = title.replace("-", " ").replace("_", " ").split()
    if any(word.startswith(q) for word in title_words):
        return 15
    if q in title or q in base:
        return 30

    rel_segments = [normalize_segment(seg) for seg in shorten_home(item["arg"]).split("/")]
    rel_segments = [seg for seg in rel_segments if seg and seg not in ("~", HOME.name.lower(), "users")]
    for idx, seg in enumerate(rel_segments[:-1]):
        if seg.startswith(q):
            return 60 + idx
    return None


def filter_items(items, q):
    if not q:
        return items
    out = []
    for item in items:
        score = score_item(item, q)
        if score is None:
            continue
        clone = dict(item)
        clone["_score"] = score
        out.append(clone)
    out.sort(key=lambda x: (x["_score"], x["title"].lower(), x["arg"].lower()))
    return out


def icon_for(item):
    app_path = "/Applications/%s.app" % CFG["app_name"]
    target = item["arg"] if os.path.exists(item["arg"]) else app_path
    if os.path.exists(target):
        return {"type": "fileicon", "path": target}
    return None


def output(items):
    payload = {"items": []}
    for item in items:
        row = {
            "uid": item["uid"],
            "title": item["title"],
            "subtitle": item["subtitle"],
            "arg": item["arg"],
            "autocomplete": item["title"],
        }
        icon = icon_for(item)
        if icon:
            row["icon"] = icon
        payload["items"].append(row)
    print(json.dumps(payload, ensure_ascii=False))


def fallback(title, subtitle, valid=False):
    print(json.dumps({"items": [{"title": title, "subtitle": subtitle, "valid": valid}]}, ensure_ascii=False))


def main():
    data, source = load_storage()
    if not data:
        fallback("Could not find %s recent data" % CFG["display"], "Set a custom storage path in Workflow Variables if needed.")
        return

    items = menu_recent_items(data)
    if not items:
        fallback("No %s recent projects found" % CFG["display"], "Source: %s" % (source or "unknown"))
        return

    items = filter_items(items, Q)
    if not items:
        fallback("No matching projects", "Try a different query.")
        return

    output(items)


if __name__ == "__main__":
    main()
