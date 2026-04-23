# VS Code + Cursor Recents

Open recent **VS Code** and **Cursor** projects from Alfred.

It prefers each editor's native recent history from `state.vscdb` and falls back to `storage.json` when needed.

## Requirements

- macOS
- Alfred 5
- VS Code or Cursor

## Preview

![vscode](images/vscode.png)

![cursor](images/cursor.png)

## Usage

- `vs` → search VS Code recents
- `co` → search Cursor recents
- `Enter` → open in the matching editor

## Highlights

- prefers each editor's native recent history from `state.vscdb`
- supports VS Code, VS Code Insiders, Cursor, and Cursor Insiders
- does **not** scan your filesystem

## Configuration

The workflow should work out of the box on standard macOS installs.

Only change these overrides if your editor stores recent history in a custom `state.vscdb` location:

- `vscode_recent_history_paths`
- `cursor_recent_history_paths`
- `debug_mode`

Supported path formats:

- `:` separated paths
- one path per line

## Notes

- Only items already present in each editor's recent history are shown
- The workflow does **not** scan your filesystem
- `debug_mode=1` is only for troubleshooting

## License

MIT
