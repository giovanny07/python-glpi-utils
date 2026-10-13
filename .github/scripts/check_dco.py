#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Giovanny Rodriguez, Imagunet
"""
Check that every non-merge commit in a range carries a DCO sign-off
(``Signed-off-by: Name <email>``) whose email matches the commit author.
Usage: python3 check_dco.py <base_sha> <head_sha>
"""
import re
import subprocess
import sys

SIGNOFF_RE = re.compile(r"^Signed-off-by: .+ <([^>]+)>\s*$", re.MULTILINE)

base, head = sys.argv[1], sys.argv[2]
log = subprocess.run(
    ["git", "log", "--no-merges", "--format=%H%x00%ae%x00%B%x01", f"{base}..{head}"],
    check=True, capture_output=True, text=True,
).stdout

failures = []
for entry in filter(None, (e.strip("\n") for e in log.split("\x01"))):
    sha, author_email, body = entry.split("\x00", 2)
    signoffs = {e.lower() for e in SIGNOFF_RE.findall(body)}
    if author_email.lower() not in signoffs:
        subject = body.strip().splitlines()[0] if body.strip() else ""
        failures.append(f"{sha[:10]} {subject}  (author: {author_email})")

if failures:
    print("These commits lack a 'Signed-off-by' line matching their author:\n")
    print("\n".join(f"  {f}" for f in failures))
    print(
        "\nSign off with `git commit -s` (see the DCO file). To fix existing commits:\n"
        "  git rebase --signoff origin/main && git push --force-with-lease"
    )
    sys.exit(1)
print("All commits are signed off.")
