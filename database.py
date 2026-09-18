"""
database.py
===========
Initialisation du moteur SQLAlchemy et fabrique de sessions.
Fonctionne aussi bien avec SQLite (démo locale) qu'avec MySQL/PostgreSQL
en production, selon la valeur de DATABASE_URL (voir config.py).
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from models import Base

connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(config.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db():
    """Crée toutes les tables si elles n'existent pas encore."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Fournit une session avec commit/rollback automatique."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    init_db()
    print(f"Base de données initialisée -> {config.DATABASE_URL}")
