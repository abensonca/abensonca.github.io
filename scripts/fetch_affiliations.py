#!/usr/bin/env python3
"""
Refresh `current_affiliation` for group members that list an ORCID iD.

The ORCID public API exposes a person's employments at:
    https://pub.orcid.org/v3.0/{orcid}/employments
No auth required for the public record.

Usage:
    python scripts/fetch_affiliations.py            # update _data/members.yml in place
    python scripts/fetch_affiliations.py --check    # only print proposed changes

Members can opt out of automatic updates by setting `affiliation_locked: true`
in _data/members.yml.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time
from typing import Any

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEMBERS_FILE = ROOT / "_data" / "members.yml"
ORCID_API = "https://pub.orcid.org/v3.0"


def fetch_employments(orcid: str) -> list[dict[str, Any]]:
    r = requests.get(
        f"{ORCID_API}/{orcid}/employments",
        headers={"Accept": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    payload = r.json() or {}
    summaries = payload.get("affiliation-group") or []
    out: list[dict[str, Any]] = []
    for group in summaries:
        for s in group.get("summaries", []):
            out.append(s.get("employment-summary") or {})
    return out


def is_current(employment: dict[str, Any]) -> bool:
    end = employment.get("end-date")
    return end is None


def affiliation_string(employment: dict[str, Any]) -> str | None:
    role = employment.get("role-title")
    org = (employment.get("organization") or {}).get("name")
    if not org:
        return None
    return f"{role}, {org}" if role else org


def best_affiliation(employments: list[dict[str, Any]]) -> str | None:
    current = [e for e in employments if is_current(e)]
    pool = current or employments
    if not pool:
        return None

    def start_year(e: dict[str, Any]) -> int:
        sd = e.get("start-date") or {}
        y = (sd.get("year") or {}).get("value")
        try:
            return int(y) if y else 0
        except ValueError:
            return 0

    pool_sorted = sorted(pool, key=start_year, reverse=True)
    for e in pool_sorted:
        s = affiliation_string(e)
        if s:
            return s
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="print changes without writing")
    args = parser.parse_args()

    text = MEMBERS_FILE.read_text()
    members = yaml.safe_load(text) or []

    changed = 0
    for m in members:
        orcid = m.get("orcid")
        if not orcid:
            continue
        if m.get("affiliation_locked"):
            continue
        try:
            emps = fetch_employments(orcid)
        except requests.RequestException as e:
            print(f"  {m['name']}: ORCID fetch failed: {e}", file=sys.stderr)
            continue
        new = best_affiliation(emps)
        if not new:
            continue
        old = m.get("current_affiliation")
        if old != new:
            print(f"  {m['name']}: {old!r} → {new!r}")
            m["current_affiliation"] = new
            changed += 1
        # Be polite with the public ORCID API.
        time.sleep(0.3)

    if changed == 0:
        print("No affiliation changes.")
        return 0

    if args.check:
        print(f"{changed} member(s) would be updated (dry run).")
        return 0

    MEMBERS_FILE.write_text(yaml.safe_dump(members, sort_keys=False, allow_unicode=True, width=100))
    print(f"Updated {changed} member(s) in {MEMBERS_FILE.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
