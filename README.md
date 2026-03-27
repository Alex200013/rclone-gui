# RcloneGUI

A lightweight web-based GUI for [rclone](https://rclone.org/), designed to run locally on Linux (Ubuntu/Debian). No Electron, no heavy dependencies — just Python + Flask served in your browser.

## Features

- 📂 **File browser** — navigate all your configured remotes, double-click folders, breadcrumb navigation
- ⬆ **Upload** — drag & drop or select files to upload to any remote, with per-file progress
- ⬇ **Download** — right-click any file to download it directly to your machine
- ⇄ **Transfers** — copy, sync or move between any two remotes/paths with real-time log output
- ⏱ **Jobs** — track all running and past transfer jobs, cancel them mid-run
- ⚙ **Remote management** — add and delete remotes (S3, SFTP, Google Drive, OneDrive, Dropbox, B2, WebDAV, FTP, Mega, Box...)
- 🖱 **Context menu** — right-click files for quick actions (open, download, set as transfer source/dest, delete)
- ⌨ **Keyboard shortcuts** — `F5` refresh, `Backspace` go up, `Delete` remove selected file, `Escape` close modals

## Requirements

- **rclone** — [installation guide](https://rclone.org/install/)
- **Python 3.8+**
- **python3-venv** (required on Ubuntu 23+)

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/Alex200013/rclone-gui.git
cd rclone-gui

# 2. Make the launcher executable
chmod +x start.sh

# 3. Run
./start.sh
```

The script will automatically:
- Create a Python virtual environment (`.venv/`)
- Install Flask inside it
- Kill any previous instance running on port 7458
- Open your browser at `http://localhost:7458`

## Usage

```bash
./start.sh    # Start
Ctrl+C        # Stop
```

If the browser doesn't open automatically, go to: `http://localhost:7458`

## Installing rclone

```bash
# Ubuntu / Debian
sudo apt install rclone

# Or official installer (latest version)
curl https://rclone.org/install.sh | sudo bash
```

If you run into venv issues on Ubuntu 23+:
```bash
sudo apt install python3-venv python3-full
```

## Project structure

```
rclone-gui/
├── app.py              # Flask backend — wraps rclone CLI
├── start.sh            # Launcher (handles venv, browser, port cleanup)
├── requirements.txt
├── README.md
└── templates/
    └── index.html      # Frontend — vanilla JS, no framework, no build step
```

## How it works

`app.py` is a thin Flask server that shells out to `rclone` for every operation:

| Endpoint | rclone command |
|---|---|
| `GET /api/remotes` | `rclone listremotes` |
| `GET /api/ls?path=…` | `rclone lsjson … --max-depth=1` |
| `POST /api/copy` | `rclone copy src dst` (streamed) |
| `POST /api/sync` | `rclone sync src dst` (streamed) |
| `POST /api/move` | `rclone move src dst` (streamed) |
| `POST /api/upload` | `rclone copyto tmpfile remote:path` |
| `GET /api/download?path=…` | `rclone copyto remote:file tmpfile` |
| `POST /api/delete` | `rclone deletefile` / `rclone purge` |
| `POST /api/mkdir` | `rclone mkdir` (falls back to `.keep` file for S3) |

Long-running transfers run in background threads. The frontend polls `/api/job/:id` every second for live status and log output. Transfers use `--use-json-log` so rclone output is parseable without a TTY.

The frontend is a single vanilla JS + HTML file — no React, no build step, no bundler.

## Supported remotes

Any remote supported by rclone works. The GUI includes dedicated setup forms for:

| Provider | Notes |
|---|---|
| Amazon S3 | Also works with Scaleway, Cloudflare R2, Wasabi, MinIO, etc. |
| Google Drive | OAuth — rclone opens browser for auth |
| Microsoft OneDrive | OAuth |
| Dropbox | OAuth |
| Backblaze B2 | |
| SFTP | Key file or password |
| FTP | |
| WebDAV | |
| Mega | |
| Box | OAuth |

## Keyboard shortcuts

| Key | Action |
|---|---|
| `F5` | Refresh current folder |
| `Backspace` | Go to parent folder |
| `Delete` | Delete selected file |
| `Escape` | Close modal / context menu |
| Double-click | Open folder |

## Notes

- Runs **locally only** on `127.0.0.1:7458` — not exposed to the network
- All rclone config is stored in the standard `~/.config/rclone/rclone.conf`
- Folder creation on S3-compatible object storage uses a `.keep` placeholder file (object storage has no real directories)
- Download of large files works — rclone copies to a temp file first, then Flask serves it

## License

MIT
