# alfred-vscode-cursor-recents

Search and open recent **VS Code** and **Cursor** projects from Alfred.

## Features

- `vs ` → show VS Code recent projects
- `co ` → show Cursor recent projects
- Type after the keyword to filter results
- Press Enter to open the selected project in the matching editor
- Reads each editor's **Open Recent** menu cache, so results closely match the native list

## Platform

Currently supports **macOS** only.

## How it works

This workflow reads the editors' local `storage.json` files and extracts recent folders/workspaces from the cached **File → Open Recent** menu data.

Default paths:

- VS Code: `~/Library/Application Support/Code/User/globalStorage/storage.json`
- Cursor: `~/Library/Application Support/Cursor/User/globalStorage/storage.json`

## Install

1. Download the latest `.alfredworkflow` file from Releases, or build it yourself.
2. Double-click the file to import it into Alfred.

## Build

```bash
chmod +x build.sh
./build.sh
```

That will generate:

```bash
alfred-vscode-cursor-recents.alfredworkflow
```

## Configure

If your app names or storage paths differ, open Alfred and configure the workflow variables:

- `vscode_app_name` — default: `Visual Studio Code`
- `cursor_app_name` — default: `Cursor`
- `vscode_storage_path` — optional custom path
- `cursor_storage_path` — optional custom path

## Why the results may differ from the editor UI

The workflow intentionally uses the editors' cached **Open Recent** menu data. If the editor has not written its latest state to disk yet, Alfred may lag behind briefly.

## Repo layout

- `info.plist` — Alfred workflow definition
- `recent_projects.py` — reads and filters recent projects
- `open_in_editor.sh` — opens the selected project in the target editor
- `build.sh` — packages the workflow into a `.alfredworkflow` file

## License

MIT
