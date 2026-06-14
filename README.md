# ytgrab

Download every video of one YouTube channel, oldest first, slowly and
resumably, to a local folder.

The hard parts are [yt-dlp](https://github.com/yt-dlp/yt-dlp)'s; this is a
thin, resilient wrapper around it:

- **Chronological** — oldest upload first (`playlistreverse`), filenames
  prefixed with the upload date so the folder sorts the same way.
- **Paced, and backs off when pushed** — a randomised sleep before each
  video, a throttled gap between the metadata requests that enumerate the
  channel at the start, and real rate-limit backoff: if YouTube ever
  pushes back (an HTTP 429, a "confirm you're not a bot" challenge), it
  pauses and *lengthens* the gap for the rest of the run instead of
  retrying into the same wall. Slow on purpose — but it can't promise
  *never*: a logged-out bulk run can still draw a bot-check however slowly
  it sleeps, which is what the optional cookie auth below is for.
- **Resumable** — a download-archive records every finished video, so a
  rerun skips what is done; a partial file keeps its `.part` and
  continues. Stop it any time (Ctrl-C, logout, crash, reboot) and run it
  again to pick up exactly where it left off.
- **Quality capped** — highest available up to 720p, merged to mp4.
- **Storage-safe** — checks free space before starting and before each
  video; if it drops below the floor it stops with a clear message
  instead of crashing, and a rerun resumes once you free space.
- **Single-instance** — a lock means a second start (a second click, a
  cron, another terminal) never runs a colliding copy.

## Requirements

- Python 3
- `yt-dlp` (the Python module; `pip install yt-dlp`). Keep it current —
  `pip install -U yt-dlp` — because YouTube changes often and a yt-dlp more
  than a few months old can stop reading channels entirely, returning
  nothing rather than erroring.
- `ffmpeg` (`sudo apt install ffmpeg`). yt-dlp downloads picture and sound
  as separate streams and merges them into one mp4 with ffmpeg; without it
  every video fails at the merge, so ytgrab refuses to start until it is
  installed.
- A **JavaScript runtime** — `deno` is yt-dlp's default
  (`curl -fsSL https://deno.land/install.sh | sh`). Recent yt-dlp needs one
  to read YouTube; without it extraction is degraded and a channel can come
  back empty (looking like "nothing downloaded"). `node` or `bun` also work
  but need yt-dlp's `--js-runtimes` option; `deno` needs no configuration.

## Check your setup

Before a download — or when something won't run — ask ytgrab what it needs:

```
python3 ytgrab.py --check
```

It prints one pass/fail line per requirement (Python, yt-dlp **and whether
it has gone stale**, ffmpeg, zenity for the launcher, the config, and the
output folder's space and writability), then says `ready` or names exactly
what to fix. It needs no config — run it first on a fresh machine. This is
the quickest way to find trouble: a stale yt-dlp reads YouTube empty
without erroring, and `--check` catches that before a run wastes time.

## Use

1. First run writes `config.json` from the example and stops:

   ```
   python3 ytgrab.py
   ```

2. Edit `config.json` — set `channel` (the channel URL or `@handle`) and
   `output` (the local folder). The rest have sensible defaults:

   | key                   | meaning                                          | default |
   |-----------------------|--------------------------------------------------|---------|
   | `channel`             | channel URL or `@handle`                         | —       |
   | `output`              | where videos go (`~` expands)                    | —       |
   | `max_height`          | quality cap in pixels                            | `720`   |
   | `sleep_min`           | min seconds before each video                    | `8`     |
   | `sleep_max`           | max seconds before each video                    | `20`    |
   | `sleep_requests`      | seconds between metadata requests (throttles the start-of-run enumeration) | `2` |
   | `backoff_max`         | ceiling (s) the per-video gap and a rate-limit pause grow to | `300` |
   | `min_free_gb`         | stop if free space falls below this              | `2`     |
   | `cookies_from_browser`| browser to read YouTube cookies from (`firefox`, `chrome`, …) — off when unset | `null` |
   | `cookiefile`          | path to an exported `cookies.txt` — off when unset | `null` |

3. Run it again to start downloading:

   ```
   python3 ytgrab.py
   ```

   Progress prints to the screen and appends to
   `<output>/.ytgrab/ytgrab.log`, which you can `tail -f`.

## Rate limits — honest version

The pacing is deliberately polite, but no download tool can *promise* it
will never be rate-limited: what trips YouTube's bot-check on a bulk run is
mostly login state and IP reputation, not the gap between videos. So ytgrab
does two things instead of overclaiming:

- **It backs off when pushed.** If a run meets a 429 or a "confirm you're
  not a bot" challenge, it pauses to let the limit clear and lengthens the
  per-video gap for the rest of the run (doubling each time it's hit, up to
  `backoff_max`), rather than retrying straight back into the wall. The log
  says so when it happens.
- **It can carry your session.** Set `cookies_from_browser` to a browser
  name (e.g. `firefox`) and the run uses your logged-in YouTube cookies
  instead of running logged-out, which is what most often avoids the
  bot-check on a large channel. Alternatively point `cookiefile` at an
  exported `cookies.txt`. **Both are off by default, on purpose:** turning
  either on hands this tool your YouTube session, so it's your call, not the
  default.

## One-click launcher

`ytgrab-launch.sh` (installed to the applications menu as `ytgrab.desktop`)
starts or resumes the download with one click, detached — no terminal to open,
no `config.json` to edit. The first click asks for the channel and the save
folder with dialogs; a later click resumes. If a channel has downloaded
nothing yet (a wrong handle, or an outdated yt-dlp that reads YouTube empty),
each click re-offers the channel — pre-filled, so a mistake is always
correctable and you are never stuck with a wrong link — until the first video
lands, after which clicks resume silently. The core's lock means a second
click never double-runs. A full channel URL is surest; a bare `@handle` also
works.
