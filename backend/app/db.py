from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.url_do_banco, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos."""


def get_session() -> Generator[Session, None, None]:
    """Dependency do FastAPI: abre uma sessão por request."""
    with SessionLocal() as session:
        yield session
