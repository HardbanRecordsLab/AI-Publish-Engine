#!/usr/bin/env python3
"""Cleanup script — removes output files older than N days.
Run via cron: 0 3 * * * cd /var/www/ai-publish-engine && python scripts/cleanup_outputs.py --days 30
"""
import os
import time
import argparse
from pathlib import Path

DEFAULT_DAYS = 30
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"


def clean_outputs(days: int, dry_run: bool = False) -> int:
    cutoff = time.time() - (days * 86400)
    removed = 0
    for f in OUTPUT_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            if dry_run:
                print(f"[DRY RUN] Would remove: {f.name}")
            else:
                f.unlink()
                print(f"Removed: {f.name}")
            removed += 1
    return removed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean old output files")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Age in days (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="List files without deleting")
    args = parser.parse_args()
    n = clean_outputs(args.days, args.dry_run)
    print(f"Cleanup complete: {n} files {'would be ' if args.dry_run else ''}removed")
