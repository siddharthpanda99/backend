from sqlmodel import SQLModel, create_engine, Session
from app.core.settings import get_settings

settings = get_settings()

# Connection arguments for pooling and performance
connect_args = {}

# Create the SQLAlchemy engine with pooling
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=False,  # Set to True for debugging SQL queries
    pool_pre_ping=True, # Verify connection before usage
    pool_size=10,       # Number of connections to keep open
    max_overflow=20,    # Max extra connections to create
    connect_args=connect_args
)

def get_session():
    """
    Dependency to get a database session.
    Yields a Session object and closes it after use.
    """
    with Session(engine) as session:
        yield session

def init_db():
    """
    Initialize the database by creating all tables defined in SQLModel metadata.
    """
    SQLModel.metadata.create_all(engine)
