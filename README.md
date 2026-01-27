# Nexus AI Backend

This is the backend service for the Nexus AI platform, built with FastAPI, SQLModel, and PostgreSQL.

## Prerequisites

- **Python**: 3.10+
- **Docker**: For running the database and local services.
- **Packages**: [uv](https://github.com/astral-sh/uv) (Recommended) or `pip`.

## Setup Instructions

### 1. Installation

Clone the repository and navigate to the backend directory:

```bash
cd Backend
```

Install dependencies using `uv`:

```bash
uv sync
```

Or using `pip`:

```bash
pip install -r requirements.txt # (If you generate one)
# OR
pip install "fastapi[standard]" sqlmodel pyyaml psycopg[binary] passlib[bcrypt] python-jose[cryptography]
```

### 2. Environment Configuration

The application uses sane defaults for local development. You can verify the settings in `app/core/settings.py`.

If you need to override settings, create a `.env` file in the `Backend` directory:

```env
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=nexus_password
POSTGRES_DB=nexus_db
SECRET_KEY=your_secret_key
```

### 3. Database Setup

Start the PostgreSQL database using Docker Compose:

```bash
docker-compose up -d
```

This will run:

- **PostgreSQL**: Port 5432
- **PgAdmin**: Port 5050 (<http://localhost:5050>)
  - User: `admin@nexus.ai`
  - Pass: `nexus_password`

Seed the database with initial data (Roles, Permissions, Superuser):

```bash
uv run seed_db.py
```

## Running the Application

Start the development server:

```bash
uv run main.py
```

The API will be available at:

- **API**: <http://localhost:8000>
- **Docs**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>

## Verification

To verify the setup and RBAC system:

```bash
uv run verify_rbac.py
```
