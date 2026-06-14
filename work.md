# work

## preflight check command

- ask: the operator kept hitting setup trouble running ytgrab and wanted to test it before the friend it was made for hits trouble setting it up. Added `python3 ytgrab.py --check` (also `-c` / `doctor`): a one-shot preflight that verifies every requirement and prints a clear pass/fail list with a one-line fix for each — Python; yt-dlp AND whether it has gone stale (its version is a release date, so it warns past ~120 days, the exact failure that reads YouTube empty without erroring); ffmpeg; zenity (launcher only, a warn not a fail); config channel+output; and the output folder's free space and writability. Exits 0 when ready, 1 when a required check fails. Needs no valid config, so a fresh machine runs it first. README gains a "Check your setup" section.
- try: run `python3 ytgrab.py --check` — on this machine it prints all-OK and "ready" (everything present and current: Python 3.12.3, yt-dlp 2026.06.09 5 days old, ffmpeg, zenity, config set, 265 GB free, exit 0). Point it at a missing config — `python3 ytgrab.py --check /tmp/none.json` — to see a FAIL line carrying the fix and exit 1.
- blocks: nothing — ytgrab runs today; this makes setup self-diagnosing so the operator and the friend find trouble in one command instead of from a download that quietly saved nothing.
- state: awaiting acceptance
