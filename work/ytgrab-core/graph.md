# graph: ytgrab-core

## ytgrab — a resilient channel downloader

- ask: the operator's first outside project (decided 2026-06-13, option 1 of the "new project: youtube channel downloader" card): a simple, resilient Python program that downloads every video of one YouTube channel oldest-first to a local folder, ≤720p, slowly enough never to be rate-limited, resuming exactly after any stop or restart, warning instead of crashing on a full disk. Engine yt-dlp. Interface (option 1): a desktop shortcut that starts or resumes with one click, detached, never double-running, progress openable. Worked slice by slice: (1) the core downloader; (2) the desktop shortcut + detached launcher.
- check: a click (or a rerun) downloads the whole channel oldest-first ≤720p, resumes exactly after any interruption, never trips a rate limit, stops cleanly when the disk is low, and never double-runs — each slice accepted by the operator.
- state: open
- since: 2026-06-13
- of: ytgrab

## the core downloader

- op: do
- ask: the first slice — `ytgrab.py`: yt-dlp wrapped with chronological (oldest-first) order, ≤720p merged to mp4, exact resume (download-archive + partial continue), polite randomised sleeps, a free-space guard that stops with a message, a single-instance lock, and a tail-able progress log. `config.json` carries the channel and the output folder.
- check: the operator accepts the card "ytgrab core: the resilient downloader" — running it downloads the channel oldest-first, resumes after a stop, paces politely, and stops cleanly on low space. How to try it: in ~/projects/ytgrab run `python3 ytgrab.py` (writes config.json), fill in channel+output, run again; stop partway and rerun to see resume; tail `<output>/.ytgrab/ytgrab.log`.
- result: built this session — ytgrab.py + config.example.json + README, py_compile clean. Not run here (it downloads gigabytes over the network — the operator's to trigger; that is the acceptance try). Hardened in a later session: a preflight now guards ffmpeg, which yt-dlp needs to merge bestvideo+bestaudio into mp4 — an environment probe found ffmpeg absent, and with ignoreerrors set a missing ffmpeg would have skipped every video silently; it now exits with an install hint before any download. Awaiting the operator's acceptance on the card.
- state: open
- of: ytgrab — a resilient channel downloader

## the desktop shortcut + detached launcher

- op: do
- ask: the second slice — a `.desktop` shortcut (and a small launcher) that starts or resumes ytgrab with one click, detached from any terminal, opening or refreshing a progress view; relies on the core's lock so a second click never double-runs. Installs to the applications menu.
- check: clicking the shortcut starts the download or resumes it, shows progress in a terminal, and a second click never double-runs — accepted by the operator.
- result: built this session, brought forward on the operator's word ("I'm not going to do that myself" — they picked the shortcut to avoid the terminal, so the CLI-only core was not theirs to try). ytgrab-launch.sh (zenity dialogs for channel + folder on first click, a progress terminal, a shell flock(2) check against the core's lock so a second click never double-runs) + ytgrab.desktop, installed as a symlink in ~/.local/share/applications (desktop-file validated). bash -n clean; not exercised here (needs the operator's desktop session — the click is the acceptance try). Hardened in a later session: an ffmpeg check now sits beside the python3 and yt_dlp checks (a zenity error with an install hint), since ffmpeg is the third required dependency and was found absent in this environment; gnome-terminal is present (Cinnamon session), so the click path runs. This slice and the core share the one card "ytgrab core: the resilient downloader" — the whole click-to-run experience.
- state: open
- of: ytgrab — a resilient channel downloader
