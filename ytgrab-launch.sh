#!/usr/bin/env bash
# ytgrab launcher — one click starts or resumes the download (the
# operator's pick, 2026-06-13, option 1). No terminal to open, no file to
# edit: the first click asks for the channel and the folder with a dialog,
# then a terminal window shows the download progressing. Click again any
# time to resume — the core's lock means a second click never double-runs.

DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
CONFIG="$DIR/config.json"
PY="$(command -v python3)"

err() { zenity --error --title="ytgrab" --text="$1" 2>/dev/null; exit 0; }
[ -n "$PY" ] || err "python3 is not installed."
"$PY" -c "import yt_dlp" 2>/dev/null || err \
    "yt-dlp (the Python module) is not installed.\nInstall it with:  pip install yt-dlp"
command -v ffmpeg >/dev/null 2>&1 || err \
    "ffmpeg is not installed.\nyt-dlp needs it to merge each video's picture and sound into one mp4.\nInstall it with:  sudo apt install ffmpeg"

config_ok() {
    "$PY" - "$CONFIG" <<'PY' 2>/dev/null
import json, sys
try:
    c = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
sys.exit(0 if c.get("channel") and c.get("output") else 1)
PY
}

# first run (or an incomplete config): ask, with dialogs, never a terminal
if ! config_ok; then
    channel=$(zenity --entry --title="ytgrab — channel" \
        --text="Paste the YouTube channel URL or @handle:") || exit 0
    [ -n "$channel" ] || err "No channel given — nothing saved."
    folder=$(zenity --file-selection --directory \
        --title="ytgrab — choose where to save the videos") || exit 0
    "$PY" - "$CONFIG" "$channel" "$folder" <<'PY' || err "Could not write the config."
import json, os, sys
path, channel, folder = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = {}
if os.path.exists(path):
    try:
        cfg = json.load(open(path))
    except Exception:
        cfg = {}
cfg["channel"] = channel
cfg["output"] = folder
cfg.setdefault("max_height", 720)
cfg.setdefault("sleep_min", 8)
cfg.setdefault("sleep_max", 20)
cfg.setdefault("min_free_gb", 2)
json.dump(cfg, open(path, "w"), indent=2)
PY
fi

# already downloading? the core holds an flock on the lock file; a shell
# flock(2) attempt on the same file conflicts with it, so this detects a
# live run without starting a second
OUT="$("$PY" -c "import json,os;print(os.path.expanduser(json.load(open('$CONFIG'))['output']))" 2>/dev/null)"
LOCK="$OUT/.ytgrab/ytgrab.lock"
if [ -e "$LOCK" ] && ! flock -n "$LOCK" -c true 2>/dev/null; then
    zenity --info --title="ytgrab" \
        --text="ytgrab is already downloading — let it run, or check its open terminal window." 2>/dev/null
    exit 0
fi

# show progress in its own terminal window, detached from this click
exec gnome-terminal --title="ytgrab — downloading" -- bash -c \
    "'$PY' '$DIR/ytgrab.py'; echo; echo '── ytgrab stopped — close this window (click the shortcut again to resume) ──'; read -n1 -s"
