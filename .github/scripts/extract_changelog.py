#!/usr/bin/env python3
"""
Extract the changelog entry for a given version from CHANGELOG.md.
Usage: python3 extract_changelog.py 1.4.4
"""
import re
import sys

version = sys.argv[1]
changelog = open("CHANGELOG.md").read()

pattern = rf"## \[{re.escape(version)}\][^\n]*\n(.*?)(?=\n## \[|\Z)"
match = re.search(pattern, changelog, re.DOTALL)

if match:
    print(match.group(1).strip())
else:
    print(f"No changelog entry found for version {version}")
    sys.exit(1)
