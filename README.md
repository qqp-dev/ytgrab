# ytgrab

Download every video of one YouTube channel, oldest first, slowly and
resumably, to a local folder.

The hard parts are [yt-dlp](https://github.com/yt-dlp/yt-dlp)'s; this is a
thin, resilient wrapper around it:

- **Chronological** — oldest upload first (`playlistreverse`), filenames
  prefixed with the upload date so the folder sorts the same way.
- **Never rate-limited** — a randomised sleep before each video and a
  small gap between API calls. Slow on purpose.
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

## Use

1. First run writes `config.json` from the example and stops:

   ```
   python3 ytgrab.py
   ```

2. Edit `config.json` — set `channel` (the channel URL or `@handle`) and
   `output` (the local folder). The rest have sensible defaults:

   | key          | meaning                                   | default          |
   |--------------|-------------------------------------------|------------------|
   | `channel`    | channel URL or `@handle`                  | —                |
   | `output`     | where videos go (`~` expands)             | —                |
   | `max_height` | quality cap in pixels                     | `720`            |
   | `sleep_min`  | min seconds before each video             | `8`              |
   | `sleep_max`  | max seconds before each video             | `20`             |
   | `min_free_gb`| stop if free space falls below this        | `2`              |

3. Run it again to start downloading:

   ```
   python3 ytgrab.py
   ```

   Progress prints to the screen and appends to
   `<output>/.ytgrab/ytgrab.log`, which you can `tail -f`.

A desktop shortcut that starts-or-resumes with one click, detached, is
the next slice.
