# daisy-native (content missing)

`daisy-layer/` is a git submodule pointer to commit
`0b6bbcf2014f08e5e6fb678ef84e0cb1a06afdb8`, but there is no `.gitmodules` entry
(so no remote URL) and the directory is empty on disk.

It held the Python "daisy-layer": roughly 79 services and the desktop apps that
`../audit-report.json` audits. The working copy is believed lost in the
2026-07-09 `~/Projects` deletion. Recovery options:

1. Find commit `0b6bbcf` in a backup, another clone, or a forgotten remote.
2. If found, add a proper `.gitmodules` entry pointing at it.
3. If confirmed unrecoverable, decide whether to remove the gitlink.

The gitlink is intentionally kept as the recovery breadcrumb.
