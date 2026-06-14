# intent — ytgrab

<!-- The operator authors this project's intent. The machine has seeded the
understanding below, marked [machine], for the operator to ratify, rewrite,
or cut — it is not endorsed until the operator's word. -->

The engine is yt-dlp; this project is a thin, resilient wrapper that adds
the chronological order, a single-instance lock, the free-space guard, and
a tail-able progress log. The interface (operator's pick, 2026-06-13,
option 1): a desktop shortcut that starts or resumes the download with one
click, running detached, never double-running, with progress you can
open. [machine]
