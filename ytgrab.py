#!/usr/bin/env python3
"""ytgrab — download every video of one YouTube channel, chronologically,
slowly, and resumably.

The hard parts are yt-dlp's: a download-archive records every finished
video so a rerun skips it (exact resume across stops and restarts);
partial files keep their .part and continue; a randomised sleep between
videos keeps the pace polite; a format cap holds quality at <=720p.
This wrapper adds the operator's requirements around it — chronological
(oldest first) order, a single-instance lock so a second start never
double-runs, a free-space guard that warns instead of crashing, and a
progress log you can tail. It also hardens the pacing: real rate-limit
backoff (when YouTube pushes back with a 429 or a bot-check, it pauses
and lengthens the gap for the rest of the run, rather than retrying into
the same wall), a throttled gap between the metadata requests that
enumerate the channel at the start, and optional browser-cookie auth so a
run need not be logged out — off by default, because turning it on trusts
the tool with your YouTube session.

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
    cfg.setdefault("sleep_requests", 2)   # gap between metadata requests —
                                          # throttles the start-of-run channel
                                          # enumeration, not just downloads
    cfg.setdefault("backoff_max", 300)    # ceiling (s) the per-video gap and a
                                          # rate-limit pause may grow to
    cfg.setdefault("min_free_gb", 2)      # stop before the disk is full
    # Optional auth so a run need not be logged out. Both default off; turning
    # either on hands the tool your YouTube session. cookies_from_browser is a
    # browser name yt-dlp reads cookies live from (e.g. "firefox", "chrome");
    # cookiefile is a path to an exported cookies.txt.
    cfg.setdefault("cookies_from_browser", None)
    cfg.setdefault("cookiefile", None)
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


class BackoffLogger:
    """Set as yt-dlp's `logger`, this takes over every line yt-dlp would
    print, and does two things.

    First, it keeps the quiet run's visible behaviour: warnings and errors go
    to stderr (so "see the errors above" still holds), the per-byte progress
    chatter stays hidden. yt-dlp routes screen output to .debug, warnings to
    .warning, errors to .error.

    Second — the point of it — it catches the one failure the fixed inter-
    video sleep cannot pace away: a rate-limit or bot-check signal (HTTP 429,
    "rate-limited", "sign in to confirm you're not a bot", a captcha). A plain
    retry just walks back into the same wall. The cure is to back off: pause
    now to let a short-term limit clear, and lengthen the gap before every
    following video so the run eases off the channel instead of leaning
    harder. The lengthen works by raising the live YoutubeDL's sleep_interval
    params, which the downloader re-reads before each video — so it sticks for
    the rest of the run, not just the next one."""

    SIGNALS = ("429", "too many requests", "rate-limit", "rate limited",
               "sign in to confirm", "not a bot", "captcha",
               "this content isn't available, try again later")

    def __init__(self, state_dir, cfg):
        self.state_dir = state_dir
        self.cfg = cfg
        self.ydl = None          # set to the live YoutubeDL once it is built
        self.hits = 0
        self._quiet_until = 0    # de-bounce: one 429 fans out into many lines

    def _looks_rate_limited(self, msg):
        m = msg.lower()
        return any(s in m for s in self.SIGNALS)

    def _backoff(self, trigger):
        # A single wall produces a burst of log lines; act once per burst, and
        # again only after the pause we just took has elapsed.
        now = time.time()
        if now < self._quiet_until:
            return
        self.hits += 1
        cap = self.cfg["backoff_max"]
        params = self.ydl.params if self.ydl is not None else {}
        lo = params.get("sleep_interval") or self.cfg["sleep_min"]
        hi = params.get("max_sleep_interval") or self.cfg["sleep_max"]
        req = params.get("sleep_interval_requests") or self.cfg["sleep_requests"]
        new_lo, new_hi = min(lo * 2, cap), min(hi * 2, cap)
        if self.ydl is not None:
            params["sleep_interval"] = new_lo
            params["max_sleep_interval"] = new_hi
            params["sleep_interval_requests"] = min(req * 2, cap)
        pause = min(new_hi * 2, cap)
        self._quiet_until = now + pause + 1
        log(self.state_dir,
            "rate-limit signal — backing off: pausing %ds now and raising the "
            "per-video gap to %d-%ds for the rest of the run (hit #%d). "
            "Trigger: %s" % (pause, new_lo, new_hi, self.hits, trigger[:200]))
        time.sleep(pause)

    # --- yt-dlp's logger interface ---------------------------------------
    def debug(self, msg):
        if self._looks_rate_limited(msg):   # progress chatter — scanned, hidden
            self._backoff(msg.strip())

    def info(self, msg):
        if self._looks_rate_limited(msg):
            self._backoff(msg.strip())

    def warning(self, msg):
        print(msg, file=sys.stderr, flush=True)
        if self._looks_rate_limited(msg):
            self._backoff(msg.strip())

    def error(self, msg):
        print(msg, file=sys.stderr, flush=True)
        if self._looks_rate_limited(msg):
            self._backoff(msg.strip())


def cookie_opts(cfg):
    """The optional auth, off unless the operator set it. Returns the yt-dlp
    opts that hand it the session — empty when logged out (the default)."""
    opts = {}
    browser = cfg.get("cookies_from_browser")
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    if cfg.get("cookiefile"):
        opts["cookiefile"] = os.path.expanduser(cfg["cookiefile"])
    return opts


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
    backoff = BackoffLogger(state_dir, cfg)

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
        "sleep_interval_requests": cfg["sleep_requests"],  # throttle the
                                                 # metadata requests too, so the
                                                 # start-of-run channel
                                                 # enumeration is paced, not a burst
        "progress_hooks": [hook],
        "logger": backoff,                       # catches 429/bot-check and backs off
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
    }
    opts.update(cookie_opts(cfg))

    auth = ("%s cookies" % cfg["cookies_from_browser"]
            if cfg.get("cookies_from_browser") else
            "cookies file" if cfg.get("cookiefile") else "logged out")
    log(state_dir, "start — channel %s -> %s (<=%dp, %.1f GB free, %s)"
        % (cfg["channel"], out, h, free_gb(out), auth))
    try:
        with YoutubeDL(opts) as ydl:
            backoff.ydl = ydl
            ydl.download([cfg["channel"]])
    except LowSpace:
        log(state_dir, "stopped: under %s GB free — freed space and a "
                       "rerun resumes where this left off." % min_free)
        sys.exit(2)
    finally:
        lock.close()

    if backoff.hits:
        log(state_dir, "note: met a rate-limit signal %d time(s) this run and "
            "backed off each time — the per-video gap was lengthened. If this "
            "keeps happening, set cookies_from_browser in the config so the "
            "run is not logged out." % backoff.hits)

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
        # Why a run can find nothing — name the likely cause instead of always
        # blaming yt-dlp, which only misleads when yt-dlp is in fact current.
        import yt_dlp
        age = _ytdlp_age_days(yt_dlp.version.__version__)
        logged_out = not (cfg.get("cookies_from_browser") or cfg.get("cookiefile"))
        reasons = ["Check the channel URL/@handle is right."]
        if not (shutil.which("deno") or shutil.which("node") or shutil.which("bun")):
            reasons.insert(0, "No JavaScript runtime (deno) is installed — recent "
                           "yt-dlp needs one to read YouTube, and without it a "
                           "channel can return empty. Install deno: "
                           "`curl -fsSL https://deno.land/install.sh | sh`")
        if backoff.hits:
            reasons.append("This run met a rate-limit / bot-check %d time(s) and "
                           "YouTube served no list — set `cookies_from_browser` in "
                           "config.json so the run isn't logged out." % backoff.hits)
        elif logged_out:
            reasons.append("A logged-out bulk run can draw a silent bot-check that "
                           "returns an empty list — set `cookies_from_browser` in "
                           "config.json to run with your YouTube session.")
        if age is not None and age > 120:
            reasons.append("yt-dlp is %d days old — update it (`pip install -U "
                           "yt-dlp`); a stale yt-dlp reads YouTube empty." % age)
        elif age is not None:
            reasons.append("(yt-dlp is current at %d days old, so a stale copy is "
                           "not the cause.)" % age)
        log(state_dir, "WARNING: the channel yielded no videos — nothing was "
            "downloaded. " + " ".join(reasons))
        sys.exit(3)


def _ytdlp_age_days(ver):
    """yt-dlp's version is its release date, YYYY.MM.DD (e.g. 2026.06.09).
    Turn it into an age in days so the preflight can warn before a stale
    copy reads YouTube empty — the failure that returns nothing rather than
    erroring. None if the string doesn't parse."""
    try:
        y, m, d = (int(p) for p in ver.split(".")[:3])
        return (datetime.now().date() - datetime(y, m, d).date()).days
    except Exception:
        return None


def doctor(path):
    """Preflight — check everything a run needs and print a clear pass/fail
    list, so trouble is found in one command before a download is attempted,
    and so the person this was made for can self-diagnose their setup. Exits
    0 when ready to run, 1 when a required check fails. Needs no valid config:
    a fresh machine can run it first."""
    checks = []  # (ok, required, label, fix-line)

    v = sys.version_info
    checks.append((v >= (3, 8), True, "Python %d.%d.%d" % v[:3],
                   "need Python 3.8 or newer"))

    try:
        import yt_dlp
        ver = yt_dlp.version.__version__
        age = _ytdlp_age_days(ver)
        if age is None:
            checks.append((True, True, "yt-dlp %s" % ver,
                           "version date unreadable — update if channels read empty"))
        elif age > 120:
            checks.append((False, True, "yt-dlp %s — %d days old" % (ver, age),
                           "stale; YouTube changes often and an old yt-dlp reads "
                           "channels empty. Update: pip install -U yt-dlp"))
        else:
            checks.append((True, True, "yt-dlp %s (%d days old)" % (ver, age), ""))
    except Exception:
        checks.append((False, True, "yt-dlp",
                       "not installed — pip install -U yt-dlp"))

    checks.append((shutil.which("ffmpeg") is not None, True, "ffmpeg",
                   "not installed — sudo apt install ffmpeg "
                   "(yt-dlp needs it to merge each video's picture and sound)"))

    # Recent yt-dlp needs a JavaScript runtime to read YouTube; deno is its
    # default. Without one, extraction is degraded and a channel can come back
    # empty (the failure that looks like "nothing downloaded").
    if shutil.which("deno"):
        checks.append((True, True, "deno (JavaScript runtime for YouTube)", ""))
    elif shutil.which("node") or shutil.which("bun"):
        other = "node" if shutil.which("node") else "bun"
        checks.append((False, False,
                       "JavaScript runtime: %s found, but yt-dlp uses deno by default" % other,
                       "install deno (`curl -fsSL https://deno.land/install.sh | sh`), "
                       "or point yt-dlp at %s with its --js-runtimes option" % other))
    else:
        checks.append((False, True, "JavaScript runtime (deno) — yt-dlp needs it for YouTube",
                       "none found — recent yt-dlp needs a JS runtime to read YouTube, "
                       "and without one a channel can return empty. Install deno: "
                       "`curl -fsSL https://deno.land/install.sh | sh`"))

    checks.append((shutil.which("zenity") is not None, False,
                   "zenity (one-click launcher only)",
                   "not installed — sudo apt install zenity; only the .desktop "
                   "launcher's dialogs need it, the command line does not"))

    cfg = None
    name = os.path.basename(path)
    if not os.path.exists(path):
        checks.append((False, True, "config %s" % name,
                       "missing — run `python3 ytgrab.py` once to write it from "
                       "the example, then set channel and output"))
    else:
        try:
            cfg = json.load(open(path))
        except Exception as e:
            checks.append((False, True, "config %s" % name, "invalid JSON: %s" % e))
        else:
            ok = bool(cfg.get("channel") and cfg.get("output"))
            checks.append((ok, True, "config: channel and output set",
                           "" if ok else "set both `channel` and `output` in %s" % path))

    if cfg and cfg.get("output"):
        out = os.path.expanduser(cfg["output"])
        floor = cfg.get("min_free_gb", 2)
        if os.path.isdir(out):
            free = free_gb(out)
            checks.append((free >= floor, True,
                           "output %s — %.1f GB free" % (out, free),
                           "" if free >= floor else "below the %s GB floor" % floor))
            checks.append((os.access(out, os.W_OK), True, "output is writable",
                           "" if os.access(out, os.W_OK) else "no write permission to %s" % out))
        else:
            parent = os.path.dirname(out) or "."
            ok = os.path.isdir(parent) and os.access(parent, os.W_OK)
            checks.append((ok, True, "output %s (created on first run)" % out,
                           "" if ok else "parent %s is missing or not writable" % parent))

    print("ytgrab preflight\n")
    ready = True
    for ok, required, label, fix in checks:
        mark = "OK  " if ok else ("FAIL" if required else "warn")
        print("  [%s] %s" % (mark, label))
        if fix and not ok:
            print("         %s" % fix)
        if not ok and required:
            ready = False
    print()
    if ready:
        print("ready — `python3 ytgrab.py` will run. (any 'warn' item is optional.)")
        return 0
    print("not ready — fix the FAIL items above, then re-run: python3 ytgrab.py --check")
    return 1


def main():
    args = sys.argv[1:]
    if args and args[0] in ("--check", "-c", "doctor"):
        path = args[1] if len(args) > 1 else DEFAULT_CONFIG
        sys.exit(doctor(path))
    path = args[0] if args else DEFAULT_CONFIG
    run(load_config(path))


if __name__ == "__main__":
    main()
