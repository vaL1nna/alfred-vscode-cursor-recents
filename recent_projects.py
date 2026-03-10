#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote

HOME = Path.home()
SYSTEM = sys.platform
EDITOR = (sys.argv[1] if len(sys.argv) > 1 else "code").strip().lower()
QUERY = (sys.argv[2] if len(sys.argv) > 2 else "")
Q = QUERY.strip().lower()
DEBUG = os.environ.get("debug_mode", "").strip().lower() in {"1", "true", "yes", "on"}
OPEN_RECENT_LABELS = {"open &&recent", "open &recent", "open recent"}
SCORE_EXACT = 0
SCORE_PREFIX = 10
SCORE_WORD_PREFIX = 20
SCORE_INITIALS = 25
SCORE_SUBSTRING = 30
SCORE_PATH_PREFIX = 50

DEFAULTS = {
    "code": {
        "display": "VS Code",
        "env_prefix": "vscode",
        "storage": [
            "~/Library/Application Support/Code/User/globalStorage/storage.json",
            "~/Library/Application Support/Code/storage.json",
            "~/Library/Application Support/Code - Insiders/User/globalStorage/storage.json",
        ],
        "icon_paths": [
            "/Applications/Visual Studio Code.app",
            "~/Applications/Visual Studio Code.app",
            "/Applications/Visual Studio Code - Insiders.app",
            "~/Applications/Visual Studio Code - Insiders.app",
        ],
    },
    "cursor": {
        "display": "Cursor",
        "env_prefix": "cursor",
        "storage": [
            "~/Library/Application Support/Cursor/User/globalStorage/storage.json",
            "~/Library/Application Support/Cursor/storage.json",
            "~/Library/Application Support/Cursor - Insiders/User/globalStorage/storage.json",
        ],
        "icon_paths": [
            "/Applications/Cursor.app",
            "~/Applications/Cursor.app",
            "/Applications/Cursor - Insiders.app",
            "~/Applications/Cursor - Insiders.app",
        ],
    },
}

CFG = DEFAULTS.get(EDITOR, DEFAULTS["code"])


def debug(message):
    if DEBUG:
        print(f"[debug] {message}", file=sys.stderr)


def split_path_values(raw):
    if not raw:
        return []

    text = str(raw).strip()
    if not text:
        return []

    values = []
    lines = text.splitlines() if "\n" in text or "\r" in text else [text]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            values.extend(part.strip() for part in line.split(":") if part.strip())
            continue
        values.append(line)
    return values


def expand_candidate(candidate):
    return os.path.expanduser(str(candidate).strip())


def unique_paths(*groups):
    merged = []
    seen = set()
    for group in groups:
        for candidate in group:
            expanded = expand_candidate(candidate)
            if not expanded or expanded in seen:
                continue
            seen.add(expanded)
            merged.append(expanded)
    return merged


def configured_storage_paths():
    env_name = f"{CFG['env_prefix']}_storage_paths"
    return unique_paths(split_path_values(os.environ.get(env_name, "")), CFG["storage"])


CFG["storage"] = configured_storage_paths()


def shorten_home(path_str):
    home = str(HOME)
    return path_str.replace(home, "~", 1) if path_str.startswith(home) else path_str


def format_path_list(paths):
    return " • ".join(shorten_home(path) for path in paths[:3])


def load_storage():
    parse_errors = []
    searched = []

    for candidate in CFG["storage"]:
        path_str = expand_candidate(candidate)
        searched.append(path_str)
        path = Path(path_str)
        if not path.exists():
            continue
        try:
            debug(f"Loading storage from {path}")
            return json.loads(path.read_text(encoding="utf-8")), str(path), parse_errors, searched
        except Exception as exc:
            debug(f"Failed to parse {path}: {exc}")
            parse_errors.append(f"{shorten_home(str(path))}: {exc}")
    return None, None, parse_errors, searched


def is_open_recent_item(item):
    label = str(item.get("label") or "").strip().lower()
    if label in OPEN_RECENT_LABELS:
        return True
    return "open" in label and "recent" in label


def menu_recent_items(data):
    try:
        file_items = data["lastKnownMenubarData"]["menus"]["File"]["items"]
    except Exception as exc:
        debug(f"Menu structure missing expected keys: {exc}")
        return []

    recent = []

    def build_recent_item(item_id, path_str):
        if item_id == "openRecentFolder":
            kind = "folder"
        elif path_str.endswith(".code-workspace"):
            kind = "workspace"
        else:
            return None

        title = os.path.basename(path_str.rstrip("/\\")) or path_str
        return {
            "uid": f"{EDITOR}:{kind}:{path_str}",
            "title": title,
            "subtitle": f"{'Workspace' if kind == 'workspace' else 'Folder'} • {shorten_home(path_str)}",
            "arg": path_str,
            "kind": kind,
            "recent_index": len(recent),
        }

    def walk(items):
        for item in items or []:
            if is_open_recent_item(item):
                submenu = (item.get("submenu") or {}).get("items") or []
                for sub in submenu:
                    item_id = sub.get("id")
                    uri = sub.get("uri") or {}
                    if uri.get("scheme") != "file":
                        continue
                    path_str = unquote(uri.get("path") or "")
                    if not path_str:
                        continue
                    recent_item = build_recent_item(item_id, path_str)
                    if recent_item is None:
                        continue
                    recent.append(recent_item)
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


def normalize_segment(segment):
    return segment.strip().lstrip(".").lower()


def score_term(item, term):
    title = item["title"].lower()
    base = os.path.basename(item["arg"].rstrip("/\\")).lower()

    if title == term or base == term:
        return SCORE_EXACT
    if title.startswith(term) or base.startswith(term):
        return SCORE_PREFIX

    title_words = title.replace("-", " ").replace("_", " ").split()
    if any(word.startswith(term) for word in title_words):
        return SCORE_WORD_PREFIX

    initials = "".join(word[0] for word in title_words if word)
    if initials and initials.startswith(term):
        return SCORE_INITIALS

    if term in title or term in base:
        return SCORE_SUBSTRING

    rel_segments = [normalize_segment(seg) for seg in shorten_home(item["arg"]).replace("\\", "/").split("/")]
    rel_segments = [seg for seg in rel_segments if seg and seg not in ("~", HOME.name.lower(), "users")]
    for idx, seg in enumerate(rel_segments[:-1]):
        if seg.startswith(term):
            return SCORE_PATH_PREFIX + idx
    return None


def score_item(item, query):
    if not query:
        return 0

    terms = [term for term in query.split() if term]
    if not terms:
        return 0

    total = 0
    for term in terms:
        score = score_term(item, term)
        if score is None:
            return None
        total += score
    return total


def filter_items(items, query):
    if not query:
        return items

    ranked = []
    for item in items:
        score = score_item(item, query)
        if score is None:
            continue
        clone = dict(item)
        clone["_score"] = score
        ranked.append(clone)

    ranked.sort(key=lambda item: (item["_score"], item["recent_index"], item["title"].lower(), item["arg"].lower()))
    return ranked


def resolve_app_icon_path():
    for candidate in CFG["icon_paths"]:
        if os.path.exists(candidate):
            return candidate
    return None


APP_ICON_PATH = resolve_app_icon_path()


def icon_for(item):
    if APP_ICON_PATH:
        return {"type": "fileicon", "path": APP_ICON_PATH}

    if os.path.exists(item["arg"]):
        return {"type": "fileicon", "path": item["arg"]}
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
            "match": f"{item['title']} {item['arg']}",
        }
        icon = icon_for(item)
        if icon:
            row["icon"] = icon
        payload["items"].append(row)
    print(json.dumps(payload, ensure_ascii=False))


def fallback(title, subtitle, valid=False):
    print(json.dumps({"items": [{"title": title, "subtitle": subtitle, "valid": valid}]}, ensure_ascii=False))


def main():
    if SYSTEM != "darwin":
        fallback("macOS only", "This Alfred workflow supports macOS only.")
        return

    data, source, parse_errors, searched = load_storage()
    if not data:
        if parse_errors:
            subtitle = "Failed to parse storage.json. Enable debug_mode=1 for details."
            if DEBUG:
                subtitle = parse_errors[0]
            fallback(f"Could not load {CFG['display']} recent data", subtitle)
            return

        searched_hint = format_path_list(searched) if searched else "No paths configured"
        fallback(
            f"Could not find {CFG['display']} recent data",
            f"Check Workflow Configuration. Tried: {searched_hint}",
        )
        return

    items = menu_recent_items(data)
    if not items:
        subtitle = f"Source: {shorten_home(source)}" if source else "Open the editor once to refresh its Open Recent cache."
        fallback(f"No {CFG['display']} recent projects found", subtitle)
        return

    items = filter_items(items, Q)
    if not items:
        fallback("No matching projects", "Only items already present in the editor's Open Recent menu are shown.")
        return

    output(items)


if __name__ == "__main__":
    main()
