import os
import sys
import dotenv
from pathlib import Path

# Setup paths to import etl_seed directly, bypassing parent module imports
current_dir = Path(__file__).resolve().parent
repo_root = current_dir.parent.parent
sys.path.insert(0, str(repo_root / "Backend Monorepo" / "Python Libs" / "common_lib" / "src" / "common_lib" / "modules" / "multi_source_etl"))

# Load environment variables
dotenv.load_dotenv(repo_root / "resources" / ".env")

import etl_seed.service as seeder

if __name__ == "__main__":
    print("=== Starting ETL Seeder Runner ===")
    seeder.seed_all()
    print("=== ETL Seeding Complete ===")
