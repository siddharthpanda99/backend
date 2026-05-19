"""
Wildcard Service - Sync and manage wildcards.
Used by both API routes and CLI scripts.
"""

import logging
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from common_lib.modules.image_processing.functions.text.dynamic_engine.sync import (
    WildcardSyncManager,
)
from common_lib.modules.image_processing.functions.text.dynamic_engine.models import (
    WildcardRecord,
)
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.paths import get_repo_root

logger = logging.getLogger(__name__)


class WildcardService:
    DEFAULT_ROOT_DIR = Path(get_repo_root()) / "Resources" / "wildcards"

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = Path(root_dir) if root_dir else self.DEFAULT_ROOT_DIR

    def sync(self, session: Session, force: bool = False) -> dict:
        """
        Sync all wildcards from filesystem to database.
        Scans: Resources/wildcards/* (collections/, nsfw/, and root YAML files)
        """
        logger.info(f"Starting wildcard sync from {self.root_dir}")

        if not self.root_dir.is_dir():
            raise ValueError(f"Wildcard directory does not exist: {self.root_dir}")

        manager = WildcardSyncManager(session, root_dir=str(self.root_dir))
        manager.sync(force=force)

        return {"status": "completed", "root_dir": str(self.root_dir)}

    def get_stats(self, session: Session) -> dict:
        """Get wildcard statistics."""
        from sqlalchemy import select, func, desc

        total = session.execute(
            select(func.count()).select_from(WildcardRecord)
        ).scalar()

        stmt = (
            select(WildcardRecord.category, func.count())
            .group_by(WildcardRecord.category)
            .order_by(desc(func.count()))
        )
        results = session.execute(stmt).all()

        categories = {cat: count for cat, count in results if cat}

        last_updated = session.execute(
            select(func.max(WildcardRecord.updated_at))
        ).scalar()

        return {
            "total": total,
            "categories": categories,
            "last_sync": last_updated.isoformat() if last_updated else None,
        }


def sync_wildcards(force: bool = False, root_dir: Optional[str] = None) -> dict:
    """
    CLI/API entry point for wildcard sync.
    """
    service = WildcardService(root_dir=root_dir)

    with next(get_session()) as session:
        result = service.sync(session, force=force)
        session.commit()

    return result


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
