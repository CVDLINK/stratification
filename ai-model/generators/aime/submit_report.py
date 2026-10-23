#!/usr/bin/env python3
"""
Submit a generated AIMe report to a (self-hosted) registry backend and STORE the key.

`generate_aime_entry.py` builds the answers tree; this script POSTs it as a real report and
persists the credentials the backend returns — crucially the **password**, which the API
returns only once and which you need to update the report later.

Pipeline:  model description YAML  ->  build answers  ->  POST /report  ->  store {id, password}

Usage:
    python submit_report.py                      # submit ../../model-description/example-model-description.yaml
    python submit_report.py path/to/model.yaml   # a specific model description file
    python submit_report.py list                 # show stored report credentials
    python submit_report.py --public model.yaml  # submit with isPublic:true (default false)

  --base-url  backend base URL (default http://localhost:9000)
  --store     credentials file (default output/reports.json)
  --email     contact email (default: provenance.contacts[0].email)

Credentials are saved to output/reports.json. That file contains report PASSWORDS — keep it
private (it is local-only; do not commit it).

Note: the self-hosted backend questionnaire has sections MD/P/D/M/R only. It stores the PR/EP
sections verbatim (no server-side validation) but its UI will not render them; the live
registry does. Use --no-pr-ep to drop them for a strict backend-shaped payload.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # noqa: F401  (ensures a clear error if deps missing; used via generate module)
except ImportError:
    sys.exit("Missing dep. Run:  pip install -r requirements.txt")

import generate_aime_entry as gen  # same folder: reuse build_answers + HTTP transport

SCRIPT_DIR = Path(__file__).parent
DEFAULT_STORE = SCRIPT_DIR / "output" / "reports.json"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_store(path):
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            sys.exit(f"Store {p} exists but is not valid JSON — refusing to overwrite.")
    return []


def save_store(path, records):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records, indent=2))


def cmd_submit(args):
    answers, name = gen.load_and_build(args.input)
    if args.no_pr_ep:
        answers = {k: v for k, v in answers.items() if k not in ("PR", "EP")}

    email = gen.contact_email(args.input, args.email)
    payload = {"answers": answers, "email": email,
               "isPublic": bool(args.public), "attachReport": False}
    status, resp = gen._request("POST", f"{args.base_url}/report", payload)
    if status != 200 or not isinstance(resp, dict) or "id" not in resp:
        sys.exit(f"POST /report failed: HTTP {status}: {resp}")

    rid, pw, ver = resp["id"], resp["password"], resp.get("version", 1)
    report_url = f"{args.base_url}/report/{rid}"

    # round-trip check: read it back and confirm the stored answers match what we sent
    status, got = gen._request("GET", report_url)
    match = status == 200 and isinstance(got, dict) and got.get("answers") == answers

    record = {
        "name": name, "id": rid, "password": pw, "version": ver,
        "is_public": bool(args.public), "base_url": args.base_url, "report_url": report_url,
        "input": str(args.input), "email": email,
        "sections": list(answers), "round_trip": "match" if match else "MISMATCH",
        "submitted_at": _now(),
    }
    records = load_store(args.store)
    records.append(record)
    save_store(args.store, records)

    print(f"✓ Submitted '{name}'  (sections: {', '.join(answers)})")
    print(f"    id       : {rid}")
    print(f"    password : {pw}      <- needed to update; stored, keep private")
    print(f"    version  : {ver}")
    print(f"    url      : {report_url}")
    print(f"    round-trip: {'MATCH' if match else 'MISMATCH'}")
    print(f"  -> credentials saved to {args.store}")
    if not match:
        sys.exit(1)


def cmd_list(args):
    records = load_store(args.store)
    if not records:
        print(f"No stored reports in {args.store}.")
        return
    print(f"{len(records)} stored report(s) in {args.store}:\n")
    for r in records:
        print(f"  {r['submitted_at']}  {r['name']}")
        print(f"      id={r['id']}  password={r['password']}  v{r['version']}  ({r['report_url']})")


def main():
    p = argparse.ArgumentParser(description="Submit an AIMe report and store its key")
    p.add_argument("--base-url", default=gen.DEFAULT_BASE, help=f"backend base URL (default {gen.DEFAULT_BASE})")
    p.add_argument("--email", default=None, help="contact email (default: provenance.contacts[0].email)")
    p.add_argument("--store", default=str(DEFAULT_STORE), help=f"credentials file (default {DEFAULT_STORE})")
    p.add_argument("--public", action="store_true", help="submit with isPublic:true (default false)")
    p.add_argument("--no-pr-ep", action="store_true", help="drop PR/EP sections (strict backend payload)")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("submit", help="build + POST + store credentials (default)")
    s.add_argument("input", nargs="?", default=str(gen.DEFAULT_INPUT))
    sub.add_parser("list", help="show stored report credentials")

    # allow a bare positional path as shorthand for `submit <path>`
    argv = sys.argv[1:]
    known = {"submit", "list"}
    if argv and argv[0] not in known and not argv[0].startswith("-"):
        argv = ["submit"] + argv
    args = p.parse_args(argv)

    if args.cmd == "list":
        cmd_list(args)
    else:
        if not hasattr(args, "input"):
            args.input = str(gen.DEFAULT_INPUT)
        cmd_submit(args)


if __name__ == "__main__":
    main()
