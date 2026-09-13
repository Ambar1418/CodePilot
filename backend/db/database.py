"""Database engine and session management."""
# pyrefly: ignore [missing-import]
from sqlmodel import SQLModel, create_engine, Session
from ..config import settings

engine = create_engine(settings.database_url, echo=False, connect_args={"check_same_thread": False})


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    """Create all tables. Called on application startup."""
    SQLModel.metadata.create_all(engine)
