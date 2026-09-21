# Retrospective

Accident narratives for this repo.

Routing: narrative stays here. A project-specific rule that will recur may become one line in `CLAUDE.md`. Cross-project lessons go to nmem or a global rule. If it can be checked by a machine, add a hook or test instead of prose.


## 2026-09-21 · Installation continued after a failed prerequisite query

During the v0.1.5 local upgrade, Stop had completed and the plugin was disabled. Herdr then removed the old pane automatically, so the next `pane.get` query failed. The shell command put the installer after the Python verification block without checking its exit status; installation continued even though the intended pre-install process/lock verification had not completed.

Follow-up inspection before Resume confirmed that every captured old process had exited, the Profile was unused, the supervisor lock was free and intent remained paused. The installed checkout matched the release, and subsequent native checks reached READY with one Gateway and unchanged configuration. No unrelated process or Profile was modified.

Dependent operations must be separate checked tool calls or one process using checked subprocess results. A missing pane is only an already-closed case after the recorded processes and locks are verified. A failed prerequisite must stop the sequence before installation.
