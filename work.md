# work

## ytgrab core: the resilient downloader

- ask: the first slice of ytgrab (your settled option 1) — the core program. `ytgrab.py` wraps yt-dlp to download a whole channel oldest-first to your folder: highest quality up to 720p merged to mp4; a download-archive plus partial-file resume so any stop, restart, or crash picks up exactly where it left off; a randomised sleep before each video and between API calls so it is never rate-limited; a free-space check before the run and before each video that stops cleanly with a message instead of crashing (a rerun resumes once space is freed); a single-instance lock so a second start never double-runs; and progress to the screen and to `<output>/.ytgrab/ytgrab.log`. Config is `config.json` (channel + output folder; the first run writes it from the example and asks you to fill it in). The desktop shortcut + detached one-click start/resume is the next slice.
- try: install yt-dlp if needed (`pip install yt-dlp`), then in ~/projects/ytgrab run `python3 ytgrab.py` once — it writes config.json and stops; set `channel` and `output` in it; run `python3 ytgrab.py` again and watch it download oldest-first with a polite pause between videos. Stop it (Ctrl-C) partway and run it again — it skips what finished and resumes the partial one. `tail -f <output>/.ytgrab/ytgrab.log` shows progress.
- blocks: nothing you have is touched — net-new. Until this is accepted the channel is not downloading, and the desktop shortcut slice waits behind it.
- state: awaiting acceptance
- since: 2026-06-13
