import sys
import subprocess
import argparse


def run_command(command: str) -> None:
    """Run a CLI command safely without shell=True.

    P1-4: Using shell=False (list form) prevents shell injection.
    Commands are split on whitespace; complex pipes/redirects must be
    expressed as multiple run_command calls.
    """
    try:
        subprocess.run(command.split(), check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        sys.exit(1)


def db_up():
    print("Starting Database Services (Postgres & pgAdmin)...")
    print("Pulling Docker images (this may take a while)...")
    run_command("docker-compose pull")
    print("Starting containers...")
    run_command("docker-compose up -d")
    print("Database Services Started.")
    print("pgAdmin is available at http://localhost:5050")
    print("Default credentials: admin@nexus.ai / nexus_password")


def db_down():
    print("Stopping Database Services...")
    run_command("docker-compose down")
    print("Database Services Stopped.")


def db_logs():
    run_command("docker-compose logs -f")


def main():
    parser = argparse.ArgumentParser(description="Nexus AI Backend Utility CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("db-up", help="Start database services")
    subparsers.add_parser("db-down", help="Stop database services")
    subparsers.add_parser("db-logs", help="View database logs")
    subparsers.add_parser("init-db", help="Create database tables")
    subparsers.add_parser(
        "db-migrate", help="Run pending Alembic migrations (upgrade head)"
    )
    seed_parser = subparsers.add_parser(
        "seed", help="Seed the database with initial data"
    )
    seed_parser.add_argument(
        "--modules", nargs="+", help="Specific modules to seed (e.g. users projects)"
    )

    args = parser.parse_args()

    if args.command == "db-up":
        db_up()
    elif args.command == "db-down":
        db_down()
    elif args.command == "db-logs":
        db_logs()
    elif args.command == "init-db":
        from common_lib.modules.data_storage.database.connection import init_db

        print("Creating database tables...")
        init_db()
        print("Tables created successfully.")
    elif args.command == "db-migrate":
        from alembic.config import main as alembic_main
        from pathlib import Path

        ini = (
            Path(__file__).parent.parent.parent
            / "Python Libs"
            / "common_lib"
            / "alembic.ini"
        )
        print(f"Running Alembic migrations ({ini})...")
        alembic_main(["-c", str(ini), "upgrade", "head"])
        print("Migrations complete.")
    elif args.command == "seed":
        # The seeder registry this command was written against no longer exists:
        #   app/modules/database/service/seed_runner.py  (missing)
        #   app/modules/authorization/seeds/role_seeder.py (missing)
        #   app/modules/users/seeds/user_seeder.py         (missing)
        #   app/modules/projects/seeds/project_seeder.py   (missing)
        # All four raise ModuleNotFoundError, so this branch could only ever
        # crash. It is left explicit rather than importing dead paths, so the
        # breakage is discoverable instead of looking like a transient fault.
        # TODO(platform): reimplement seeding against the entity sync path
        # (`uv run sync init`) or restore a seeder registry.
        # Not a bare print(): golden rule 11 forbids them in app/ code, and this
        # message is a diagnostic rather than command output, so it goes to
        # stderr — which is also what a CLI diagnostic should do.
        sys.stderr.write(
            "seed: unavailable — the seeder registry was removed. "
            "Use `uv run sync init` to sync entities from the filesystem.\n"
        )
    else:
        parser.print_help()


def dev_server():
    """Entry point for 'uv run dev'"""
    # Pre-check for syntax errors
    import ast
    from pathlib import Path

    routes_dir = Path(__file__).parent / "modules" / "workflows" / "routes"
    for f in routes_dir.glob("*.py"):
        try:
            ast.parse(f.read_text())
        except SyntaxError as e:
            print(f"Syntax error in {f.name}: {e}")
            print("Fix the error and restart")
            return

    db_up()
    print("\nStarting Backend Server...")
    import uvicorn
    import sys
    from pathlib import Path

    app_dir = str(Path(__file__).parent.resolve())  # Matches app/
    common_lib_dir = str(
        (
            Path(__file__).parent.parent.parent / "Python Libs" / "common_lib" / "src"
        ).resolve()
    )

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[app_dir, common_lib_dir],
    )


if __name__ == "__main__":
    main()
