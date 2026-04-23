#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

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
        "state_db": [
            "~/Library/Application Support/Code/User/globalStorage/state.vscdb",
            "~/Library/Application Support/Code/state.vscdb",
            "~/Library/Application Support/Code - Insiders/User/globalStorage/state.vscdb",
        ],
        "storage_json": [
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
        "state_db": [
            "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb",
            "~/Library/Application Support/Cursor/state.vscdb",
            "~/Library/Application Support/Cursor - Insiders/User/globalStorage/state.vscdb",
        ],
        "storage_json": [
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



def configured_state_db_paths():
    env_name = f"{CFG['env_prefix']}_recent_history_paths"
    configured = split_path_values(os.environ.get(env_name, ""))
    if configured:
        return unique_paths(configured)
    return unique_paths(CFG["state_db"])


def configured_storage_paths():
    derived = [
        str(Path(expand_candidate(path)).with_name("storage.json"))
        for path in CFG.get("state_db", [])
        if Path(expand_candidate(path)).name == "state.vscdb"
    ]
    return unique_paths(derived, CFG["storage_json"])


CFG["state_db"] = configured_state_db_paths()
CFG["storage_json"] = configured_storage_paths()


def shorten_home(path_str):
    home = str(HOME)
    return path_str.replace(home, "~", 1) if path_str.startswith(home) else path_str


def format_path_list(paths):
    return " • ".join(shorten_home(path) for path in paths[:3])


def build_recent_item(path_str, kind, recent_index):
    title = os.path.basename(path_str.rstrip("/\\")) or path_str
    return {
        "uid": f"{EDITOR}:{kind}:{path_str}",
        "title": title,
        "subtitle": f"{'Workspace' if kind == 'workspace' else 'Folder'} • {shorten_home(path_str)}",
        "arg": path_str,
        "kind": kind,
        "recent_index": recent_index,
    }


def dedupe_recent_items(items):
    deduped = []
    seen = set()
    for item in items:
        if item["arg"] in seen:
            continue
        seen.add(item["arg"])
        deduped.append(item)
    return deduped


def decode_file_uri(uri):
    if not uri:
        return None

    parsed = urlparse(uri)
    if parsed.scheme and parsed.scheme != "file":
        return None

    if not parsed.scheme:
        return unquote(uri)

    path = unquote(parsed.path or "")
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"
    return path or None


def load_state_recent_items():
    parse_errors = []
    searched = []

    for candidate in CFG.get("state_db", []):
        path_str = expand_candidate(candidate)
        searched.append(path_str)
        path = Path(path_str)
        if not path.exists():
            continue

        connection = None
        try:
            debug(f"Loading recent history from {path}")
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            row = connection.execute(
                "SELECT value FROM ItemTable WHERE key = ?",
                ("history.recentlyOpenedPathsList",),
            ).fetchone()
            if not row:
                continue

            raw = row[0]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            data = json.loads(raw)
            recent = []
            for entry in data.get("entries") or []:
                path_str = None
                kind = None

                folder_uri = entry.get("folderUri")
                if folder_uri:
                    path_str = decode_file_uri(folder_uri)
                    kind = "folder"
                else:
                    workspace = entry.get("workspace") or {}
                    workspace_uri = (
                        entry.get("workspaceUri")
                        or workspace.get("configPath")
                        or workspace.get("workspaceUri")
                        or workspace.get("uri")
                    )
                    if workspace_uri:
                        path_str = decode_file_uri(workspace_uri)
                        kind = "workspace"

                if not path_str or kind is None:
                    continue

                recent.append(build_recent_item(path_str, kind, len(recent)))

            if recent:
                return dedupe_recent_items(recent), str(path), parse_errors, searched
        except Exception as exc:
            debug(f"Failed to read {path}: {exc}")
            parse_errors.append(f"{shorten_home(str(path))}: {exc}")
        finally:
            if connection is not None:
                connection.close()

    return [], None, parse_errors, searched


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
                    if item_id == "openRecentFolder":
                        kind = "folder"
                    elif path_str.endswith(".code-workspace"):
                        kind = "workspace"
                    else:
                        continue
                    recent.append(build_recent_item(path_str, kind, len(recent)))
                return

            submenu = (item.get("submenu") or {}).get("items")
            if submenu:
                walk(submenu)

    walk(file_items)
    return dedupe_recent_items(recent)


def load_storage_recent_items():
    parse_errors = []
    searched = []

    for candidate in CFG.get("storage_json", []):
        path_str = expand_candidate(candidate)
        searched.append(path_str)
        path = Path(path_str)
        if not path.exists():
            continue
        try:
            debug(f"Loading fallback storage from {path}")
            data = json.loads(path.read_text(encoding="utf-8"))
            recent = menu_recent_items(data)
            if recent:
                return recent, str(path), parse_errors, searched
        except Exception as exc:
            debug(f"Failed to parse {path}: {exc}")
            parse_errors.append(f"{shorten_home(str(path))}: {exc}")

    return [], None, parse_errors, searched


def load_recent_items():
    state_items, state_source, state_errors, state_searched = load_state_recent_items()
    if state_items:
        return state_items, state_source, state_errors, state_searched

    storage_items, storage_source, storage_errors, storage_searched = load_storage_recent_items()
    return (
        storage_items,
        storage_source,
        state_errors + storage_errors,
        unique_paths(state_searched, storage_searched),
    )


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
        if os.path.exists(os.path.expanduser(candidate)):
            return os.path.expanduser(candidate)
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

    items, source, parse_errors, searched = load_recent_items()
    if parse_errors and not items:
        subtitle = "Failed to load recent history. Enable debug_mode=1 for details."
        if DEBUG:
            subtitle = parse_errors[0]
        fallback(f"Could not load {CFG['display']} recent history", subtitle)
        return

    if not items:
        if source:
            subtitle = f"Source: {shorten_home(source)}"
            fallback(f"No {CFG['display']} recent projects found", subtitle)
            return
        searched_hint = format_path_list(searched) if searched else "No paths configured"
        fallback(
            f"Could not find {CFG['display']} recent history",
            f"Set the advanced state.vscdb override if your history lives elsewhere. Tried: {searched_hint}",
        )
        return

    items = filter_items(items, Q)
    if not items:
        fallback("No matching projects", "Only items already present in the editor's recent history are shown.")
        return

    output(items)


if __name__ == "__main__":
    main()
