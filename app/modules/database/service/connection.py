from sqlmodel import SQLModel, create_engine, Session
from app.core.settings import get_settings

settings = get_settings()

# Use postgresql+psycopg scheme to use the psycopg 3 driver
# Use postgresql+psycopg scheme to use the psycopg 3 driver
if settings.SQLALCHEMY_DATABASE_URI.startswith("postgresql://"):
    DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI.replace("postgresql://", "postgresql+psycopg://")
else:
    DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI

engine = create_engine(DATABASE_URL, echo=True)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
