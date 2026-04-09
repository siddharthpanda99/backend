from sqlmodel import SQLModel, create_engine, Session, text
from app.core.settings import get_settings

settings = get_settings()

# Use postgresql+psycopg scheme to use the psycopg 3 driver
# Use postgresql+psycopg scheme to use the psycopg 3 driver
if settings.SQLALCHEMY_DATABASE_URI.startswith("postgresql://"):
    DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI.replace("postgresql://", "postgresql+psycopg://")
else:
    DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI

# Connection arguments for pooling and performance
connect_args = {"connect_timeout": 5}

engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True, # Verify connection before usage
    pool_size=10,       # Number of connections to keep open
    max_overflow=20,    # Max extra connections to create
    connect_args=connect_args
)

def create_db_if_not_exists():
    """Context requires connecting to 'postgres' db to create the target db"""
    # Create url for default postgres database
    default_db_url = f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/postgres"
    
    # Create temp engine with autocommit for database creation
    temp_engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
    
    try:
        with temp_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{settings.POSTGRES_DB}'"))
            if not result.scalar():
                print(f"Database '{settings.POSTGRES_DB}' does not exist. Creating...")
                conn.execute(text(f'CREATE DATABASE "{settings.POSTGRES_DB}"'))
                print(f"Database '{settings.POSTGRES_DB}' created successfully.")
            else:
                print(f"Database '{settings.POSTGRES_DB}' already exists.")
    except Exception as e:
        print(f"Warning: Could not check/create database: {e}")
    finally:
        temp_engine.dispose()

def init_db():
    create_db_if_not_exists()
    
    # Import all models to ensure they are registered with SQLModel.metadata
    from app.modules.users.models.index import User
    from app.modules.authorization.models.index import Role, Permission, UserRole, RolePermission, UserResourceRole
    from app.modules.projects.models.index import Project, ProjectModule, Workflow, Task
    
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
