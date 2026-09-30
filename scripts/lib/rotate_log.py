#!/usr/bin/env python3
"""
Size-capped log sink for scripts/dev-up.sh — reads stdin, writes a bounded,
rotating log file.

    some-command 2>&1 | rotate_log.py LOG_FILE [MAX_MB] [BACKUPS]

Total disk use per log is at most MAX_MB * (BACKUPS + 1) (defaults: 10 MB * 4
= 40 MB), no matter how much the producer writes. This exists because a plain
``>> file`` redirect has no ceiling: a runaway process previously wrote tens of
gigabytes into one dev log. Standard library only; never raises on bad input.

Implementation notes:
- Reads raw byte chunks (not lines), so a producer that never emits a newline
  cannot make this process buffer unboundedly.
- Ignores SIGINT/SIGHUP so it keeps draining (and thus keeps the log complete
  and the producer unblocked) until the producer closes the pipe, then exits.
"""

from __future__ import annotations

import os
import signal
import sys

_CHUNK = 64 * 1024


def _rotate(path: str, backups: int) -> None:
    """LOG -> LOG.1 -> LOG.2 ... ; the oldest is overwritten (or removed if backups == 0)."""
    if backups <= 0:
        os.truncate(path, 0)
        return
    for i in range(backups - 1, 0, -1):
        src = f"{path}.{i}"
        if os.path.exists(src):
            os.replace(src, f"{path}.{i + 1}")
    os.replace(path, f"{path}.1")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: rotate_log.py LOG_FILE [MAX_MB] [BACKUPS]", file=sys.stderr)
        return 2
    path = argv[1]
    max_bytes = int(float(argv[2]) * 1024 * 1024) if len(argv) > 2 else 10 * 1024 * 1024
    backups = int(argv[3]) if len(argv) > 3 else 3
    max_bytes = max(max_bytes, _CHUNK)

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    out = open(path, "ab")  # noqa: SIM115 - held open for the process lifetime
    size = out.tell()
    stdin = sys.stdin.buffer
    while True:
        chunk = stdin.read1(_CHUNK)
        if not chunk:
            break
        if size + len(chunk) > max_bytes and size > 0:
            out.close()
            _rotate(path, backups)
            out = open(path, "ab")  # noqa: SIM115
            size = 0
        # A single chunk is at most _CHUNK bytes, so the file can never exceed
        # max_bytes by more than that.
        out.write(chunk)
        out.flush()
        size += len(chunk)
    out.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except BrokenPipeError:  # pragma: no cover
        sys.exit(0)
