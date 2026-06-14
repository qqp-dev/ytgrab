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
- result: built this session — ytgrab.py + config.example.json + README, py_compile clean. Not run here (it downloads gigabytes over the network — the operator's to trigger; that is the acceptance try). Awaiting the operator's acceptance on the card.
- state: open
- of: ytgrab — a resilient channel downloader

## the desktop shortcut + detached launcher

- op: do
- ask: the second slice — a `.desktop` shortcut (and a small launcher) that starts or resumes ytgrab with one click, detached from any terminal, opening or refreshing a progress view; relies on the core's lock so a second click never double-runs. Installs to the applications menu.
- check: clicking the shortcut starts the download or resumes it, runs detached, shows progress, and a second click never double-runs — accepted by the operator.
- state: open
- of: ytgrab — a resilient channel downloader
