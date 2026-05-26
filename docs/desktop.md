# Desktop App

Event Face Finder includes an experimental Tauri desktop wrapper. It keeps the
existing Python engine and local web GUI, then opens them inside a desktop window
with native folder pickers.

## Requirements

- Python 3.10 or newer
- Node.js and npm
- Rust/Cargo from <https://rustup.rs>
- The Python dependencies installed from `requirements.txt`

## Run From Source

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
npm install
npm run desktop:dev
```

On Windows PowerShell, activate Python with:

```powershell
.\.venv\Scripts\Activate.ps1
```

The desktop launcher starts:

```bash
python -m event_face_finder gui --host 127.0.0.1 --port 8765 --no-open
```

When running from the source checkout, generated `outputs/` stay in the repo. When
running a packaged app bundle, the launcher uses `~/Documents/Event Face Finder` as
the working folder so outputs and caches are written somewhere user-visible and
writable.

If you want to force a specific Python executable, set `EFF_PYTHON` before starting
the desktop app:

```bash
EFF_PYTHON=/path/to/python npm run desktop:dev
```

## Build A Local App Bundle

```bash
npm run desktop:build
```

The current desktop build bundles the Event Face Finder Python package source, but
it still expects Python and the project dependencies to be available on the user's
machine. A fully self-contained desktop installer with bundled Python is planned
after the MVP stabilizes.

## Notes

- The CLI and browser GUI remain supported.
- Folder picker buttons appear in the desktop app and gracefully fall back in a
  regular browser.
- The app still processes biometric data locally. Review `PRIVACY.md` before
  scanning real event photos.
