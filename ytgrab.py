#!/usr/bin/env python3
"""ytgrab — download every video of one YouTube channel, chronologically,
slowly, and resumably.

The hard parts are yt-dlp's: a download-archive records every finished
video so a rerun skips it (exact resume across stops and restarts);
partial files keep their .part and continue; a sleep between videos keeps
us politely under any rate limit; a format cap holds quality at <=720p.
This wrapper adds the operator's requirements around it — chronological
(oldest first) order, a single-instance lock so a second start never
double-runs, a free-space guard that warns instead of crashing, and a
progress log you can tail.

Run:  python3 ytgrab.py            (reads ./config.json)
      python3 ytgrab.py PATH       (reads PATH)

On the first run with no config it writes config.json from the example and
asks you to fill in the channel and the output folder.
"""

import json
import os
import shutil
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "config.json")
EXAMPLE_CONFIG = os.path.join(HERE, "config.example.json")


def log(state_dir, msg):
    """One progress line — to the screen and to state/ytgrab.log, so a
    detached run leaves a tail-able record."""
    line = "%s  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(os.path.join(state_dir, "ytgrab.log"), "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def channel_url(channel):
    """yt-dlp needs a real URL — handed a bare `@handle` it refuses with
    "'@handle' is not a valid URL" and, under ignoreerrors, downloads
    nothing. Both the config and the launcher invite an @handle, so turn
    one into the channel's videos page here. Full URLs pass through."""
    c = channel.strip()
    if "://" in c:
        return c
    if c.startswith("@"):
        return "https://www.youtube.com/%s/videos" % c
    if c.startswith(("www.", "youtube.com", "m.youtube.com")):
        return "https://%s" % c
    # a bare word — the only meaning ytgrab has for it is a handle
    return "https://www.youtube.com/@%s/videos" % c


def load_config(path):
    """The config, or a written template and a clear exit. Required keys:
    channel (the channel URL or @handle) and output (the local folder).
    Everything else has a sensible default."""
    if not os.path.exists(path):
        if os.path.exists(EXAMPLE_CONFIG):
            shutil.copy(EXAMPLE_CONFIG, path)
            sys.exit("wrote %s from the example — fill in `channel` and "
                     "`output`, then run again." % path)
        sys.exit("no config at %s and no example beside it." % path)
    with open(path) as f:
        cfg = json.load(f)
    if not cfg.get("channel") or not cfg.get("output"):
        sys.exit("config %s needs both `channel` and `output` set." % path)
    cfg["channel"] = channel_url(cfg["channel"])
    cfg["output"] = os.path.expanduser(cfg["output"])
    cfg.setdefault("max_height", 720)
    cfg.setdefault("sleep_min", 8)        # seconds before each video
    cfg.setdefault("sleep_max", 20)       # ... up to this, at random
    cfg.setdefault("min_free_gb", 2)      # stop before the disk is full
    return cfg


class LowSpace(Exception):
    """Raised to stop the run cleanly when the disk is nearly full — the
    .part file and the archive mean a rerun resumes once space is freed."""


def free_gb(path):
    return shutil.disk_usage(path).free / 1024 ** 3


def single_instance_lock(state_dir):
    """A click (or a cron, or a second terminal) while one run is going
    must not start a second — option 1's 'never double-runs'. flock is
    released automatically if the holding process dies, so a crash never
    leaves a stuck lock. Returns the held file handle (keep it open) or
    None if another run holds it."""
    import fcntl
    fh = open(os.path.join(state_dir, "ytgrab.lock"), "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fh.write("%d\n" % os.getpid())
    fh.flush()
    return fh


def run(cfg):
    from yt_dlp import YoutubeDL

    # yt-dlp downloads the best video and best audio as separate streams and
    # merges them into one mp4 — that merge is ffmpeg's job. Without it, every
    # video errors at merge time and `ignoreerrors` skips it, so a whole run
    # would quietly save nothing. Fail loud and early instead.
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg is not installed — yt-dlp needs it to merge each "
                 "video's picture and sound into one mp4. Install it (e.g. "
                 "`sudo apt install ffmpeg`) and run again.")

    out = cfg["output"]
    state_dir = os.path.join(out, ".ytgrab")
    os.makedirs(state_dir, exist_ok=True)

    lock = single_instance_lock(state_dir)
    if lock is None:
        sys.exit("another ytgrab run is already going (lock held) — "
                 "nothing started.")

    min_free = cfg["min_free_gb"]
    if free_gb(out) < min_free:
        sys.exit("only %.1f GB free at %s, below the %s GB floor — free "
                 "some space and run again." % (free_gb(out), out, min_free))

    archive = os.path.join(state_dir, "archive.txt")
    h = cfg["max_height"]
    tally = {"file": None, "attempted": 0, "saved": 0}

    def hook(d):
        # at the start of each new file, guard the disk; mid-file the OS
        # error and the resumable .part cover a sudden fill
        if d.get("status") == "downloading":
            fn = d.get("filename")
            if fn != tally["file"]:
                tally["file"] = fn
                tally["attempted"] += 1
                if free_gb(out) < min_free:
                    raise LowSpace()
                idx = d.get("info_dict", {}).get("playlist_index")
                n = d.get("info_dict", {}).get("n_entries")
                title = d.get("info_dict", {}).get("title", "?")
                where = ("%s/%s" % (idx, n)) if idx and n else "?"
                log(state_dir, "downloading %s: %s" % (where, title))
        elif d.get("status") == "finished":
            tally["saved"] += 1
            log(state_dir, "saved: %s" % os.path.basename(d.get("filename", "?")))

    opts = {
        # highest quality up to the cap, merged to mp4
        "format": ("bestvideo[height<=%d]+bestaudio/best[height<=%d]/best"
                   % (h, h)),
        "merge_output_format": "mp4",
        # date-prefixed names sort chronologically in the folder
        "outtmpl": os.path.join(
            out, "%(upload_date)s - %(title).80s [%(id)s].%(ext)s"),
        "download_archive": archive,   # exact resume — skip what is done
        "continuedl": True,            # resume a partial .part
        "playlistreverse": True,       # oldest first — chronological
        "ignoreerrors": True,          # a dead/blocked video is skipped, not fatal
        "retries": 20,
        "fragment_retries": 20,
        "sleep_interval": cfg["sleep_min"],      # polite gap before each video
        "max_sleep_interval": cfg["sleep_max"],
        "sleep_interval_requests": 1,            # and a small gap between API calls
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
    }

    log(state_dir, "start — channel %s -> %s (<=%dp, %.1f GB free)"
        % (cfg["channel"], out, h, free_gb(out)))
    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([cfg["channel"]])
    except LowSpace:
        log(state_dir, "stopped: under %s GB free — freed space and a "
                       "rerun resumes where this left off." % min_free)
        sys.exit(2)
    finally:
        lock.close()

    # What actually happened — never report success on a no-op. yt-dlp under
    # ignoreerrors swallows extraction failures (a wrong handle, or an
    # outdated yt-dlp that can no longer read YouTube) and returns as if
    # done; a finished run that saved nothing must say so, not lie "done".
    try:
        with open(archive) as f:
            archived = sum(1 for _ in f)
    except OSError:
        archived = 0

    if tally["saved"]:
        log(state_dir, "done — saved %d new video(s) this run; %d downloaded "
            "in all (rerun any time to pick up new uploads)."
            % (tally["saved"], archived))
    elif archived:
        log(state_dir, "up to date — every video already downloaded (%d in "
            "all); nothing new this run." % archived)
    elif tally["attempted"]:
        log(state_dir, "WARNING: found %d video(s) but saved none — every "
            "download or merge failed. Is ffmpeg installed? See the errors "
            "above." % tally["attempted"])
        sys.exit(3)
    else:
        log(state_dir, "WARNING: the channel yielded no videos — nothing was "
            "downloaded. Check the channel URL/@handle is right, and update "
            "yt-dlp (`pip install -U yt-dlp`): an outdated yt-dlp can no "
            "longer read YouTube and returns empty without erroring.")
        sys.exit(3)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG
    run(load_config(path))


if __name__ == "__main__":
    main()
