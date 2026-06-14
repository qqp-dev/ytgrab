# work

## publish ytgrab to a public remote

- ask: you said (2026-06-13, in hypercore's words) "unrelated - push it to a public remote (needs to be created) under qqp-dev." I read "it" as ytgrab — it has no remote yet ("needs to be created" fits), it is a standalone tool worth sharing, and qqp-dev is the GitHub account this machine is authed as (active, repo + delete_repo scopes). Publishing is safe: your real config.json (channel + output folder) is gitignored, so only the code, README, config.example.json, the empty intent, and the folded graph would go public. I did not push on my own word: a public repo leaves the project folder and can be cached or indexed even after a delete, so the surfacing floor makes publishing your call — and the antecedent "it" is mine to confirm, not assume.
- options: publish ytgrab — create a public qqp-dev/ytgrab and push main . a different repo — you meant something other than ytgrab (say which, e.g. a public mirror of hypercore) . not now — leave ytgrab local
- state: decided (2026-06-13) — option 1 — publish ytgrab — create a public qqp-dev/ytgrab and push main
- since: 2026-06-13
- blocks: nothing runs unbacked; ytgrab stays local until you settle this. The settle triggers the push — a session creates qqp-dev/ytgrab public and pushes main in the ytgrab repo.

