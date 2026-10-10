"""
main.py
-------
Orchestrates the lead-generation pipeline:

    scrape URLs  ->  Gemini qualification  ->  append High leads to Sheets

Usage:
    python main.py
    python main.py --url data/mock_leads.html
    python main.py --url https://example.com/directory --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys

from ai_filter import score_lead
from config import DEFAULT_SOURCE_URLS
from scraper import scrape_businesses
from sheet_manager import append_high_priority_leads

 
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automated Lead Generation Engine (scrape → Gemini → Sheets)"
    )
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="Webpage or local HTML file to scrape. Repeatable. "
        "Defaults to data/mock_leads.html.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Score leads but do not write to Google Sheets.",
    )
    return parser.parse_args(argv)


def run(urls: list[str], dry_run: bool = False) -> dict:
    print(f"[1/3] Scraping {len(urls)} source(s)...")
    leads = scrape_businesses(urls)
    print(f"      Found {len(leads)} business record(s).")

    if not leads:
        print("No businesses found. Check the HTML structure or URL.")
        return {"scraped": 0, "high": 0, "written": 0}

    print("[2/3] Scoring leads with Gemini...")
    scored = score_lead(leads)
    for lead in scored:
        print(
            f"      {lead['company_name']}: {lead['priority']} "
            f"— {lead.get('reason', '')[:120]}"
        )

    high_count = sum(1 for lead in scored if lead.get("priority") == "High")
    written = 0

    if dry_run:
        print("[3/3] Dry run — skipping Google Sheets write.")
        print(json.dumps(scored, indent=2))
    else:
        print("[3/3] Appending High-priority leads to Google Sheets...")
        written = append_high_priority_leads(scored)
        print(f"      Wrote {written} High-priority row(s).")

    summary = {"scraped": len(leads), "high": high_count, "written": written}
    print(f"Done. {summary}")
    return summary


def main() -> int:
    args = parse_args()
    urls = args.urls or DEFAULT_SOURCE_URLS
    try:
        run(urls, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
