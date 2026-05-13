"""
CLI script for wildcard sync - uses WildcardService.
Usage: python sync_wildcards.py [--force] [--root-dir PATH]
"""

import sys
import os

repo_root = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo"
sys.path.insert(0, os.path.join(repo_root, "Backend"))

from app.modules.wildcards.service import sync_wildcards

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync wildcards to database")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force overwrite existing wildcards"
    )
    parser.add_argument("--root-dir", "-r", help="Custom wildcard root directory")
    args = parser.parse_args()

    result = sync_wildcards(force=args.force, root_dir=args.root_dir)
    print(f"Sync complete: {result}")
