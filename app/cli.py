import sys
import subprocess
import argparse

def run_command(command):
    try:
        subprocess.run(command, check=True, shell=True)
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
    seed_parser = subparsers.add_parser("seed", help="Seed the database with initial data")
    seed_parser.add_argument("--modules", nargs="+", help="Specific modules to seed (e.g. users projects)")

    args = parser.parse_args()

    if args.command == "db-up":
        db_up()
    elif args.command == "db-down":
        db_down()
    elif args.command == "db-logs":
        db_logs()
    elif args.command == "init-db":
        from app.modules.database.service.connection import init_db
        print("Creating database tables...")
        init_db()
        print("Tables created successfully.")
    elif args.command == "seed":
        from app.modules.database.service.seed_runner import register_seeder, run_seeds
        from app.modules.authorization.seeds.role_seeder import AuthorizationSeeder
        from app.modules.users.seeds.user_seeder import UserSeeder
        from app.modules.projects.seeds.project_seeder import ProjectSeeder
        
        # Register and run
        register_seeder(AuthorizationSeeder)
        register_seeder(UserSeeder)
        register_seeder(ProjectSeeder)
        
        target = args.modules if args.modules else None
        run_seeds(target)
    else:
        parser.print_help()

def dev_server():
    """Entry point for 'uv run dev'"""
    db_up()
    print("\nStarting Backend Server...")
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
