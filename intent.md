# intent — ytgrab

<!-- The operator authors this project's intent. The machine has seeded the
understanding below, marked [machine], for the operator to ratify, rewrite,
or cut — it is not endorsed until the operator's word. -->

Download every video of a single YouTube channel to a local folder, in
chronological order (oldest first), at the highest quality up to 720p —
slowly enough never to be rate-limited, and resilient above all: any stop,
restart, or crash resumes exactly where it left off without losing track,
and a nearly-full disk stops cleanly with a warning rather than
failing. [machine]

The engine is yt-dlp; this project is a thin, resilient wrapper that adds
the chronological order, a single-instance lock, the free-space guard, and
a tail-able progress log. The interface (operator's pick, 2026-06-13,
option 1): a desktop shortcut that starts or resumes the download with one
click, running detached, never double-running, with progress you can
open. [machine]
