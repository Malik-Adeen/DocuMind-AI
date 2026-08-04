#!/usr/bin/env python3
"""Stop hook: warn when code changed but Docs/ did not.

Source of truth is the git working tree, not the session transcript. Claude Code
documents no schema for the transcript JSONL and does not document a per-session
list of edited files, so there is no supported way to ask "what did this session
edit". The working tree answers a slightly broader question -- "what is uncommitted
right now" -- which is the question AGENT_RULES.md §2 actually cares about, since
the rule binds the commit, not the session.

Never blocks. Exit 0 always.
"""

import json
import subprocess
import sys

CODE_MARKERS = ("backend/app/", "backend/tests/")
DOCS_MARKER = "Docs/"
RULES = "Docs/AGENT_RULES.md"


def git(root, *args):
    try:
        out = subprocess.run(
            ["git", "-C", root, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def changed_paths(root):
    out = git(root, "status", "--porcelain", "-uall")
    if out is None:
        return []
    paths = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip().strip('"'))
    return paths


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cwd = payload.get("cwd") or "."
    root = git(cwd, "rev-parse", "--show-toplevel")
    if root is None:
        return 0
    root = root.strip()

    paths = changed_paths(root)
    code = sorted(p for p in paths if any(m in "/" + p for m in CODE_MARKERS))
    docs = [p for p in paths if DOCS_MARKER in "/" + p]

    if not code or docs:
        return 0

    listed = "\n".join(f"  - {p}" for p in code[:10])
    if len(code) > 10:
        listed += f"\n  - ... and {len(code) - 10} more"

    warning = (
        f"Code changed, no doc changed. Uncommitted under backend/app/ or backend/tests/:\n"
        f"{listed}\n"
        f"Nothing under Docs/ is modified.\n\n"
        f"Check the trigger table in {RULES} §2 -- it maps each code area to the "
        f"document that change obliges you to update, in the same commit. If your change "
        f"genuinely fits no row, say so in the commit message rather than skipping silently."
    )

    print(
        json.dumps(
            {
                "systemMessage": f"docs check: {len(code)} code file(s) changed, Docs/ untouched "
                f"-- see {RULES} §2",
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": warning,
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
