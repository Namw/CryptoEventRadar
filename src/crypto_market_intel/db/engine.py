from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_database_url() -> str:
	return os.getenv("DATABASE_URL", "sqlite:///./data/app.db")


def create_db_engine(database_url: str | None = None) -> Engine:
	db_url = database_url or get_database_url()
	if db_url.startswith("sqlite"):
		return create_engine(db_url, echo=False, future=True, connect_args={"check_same_thread": False})
	return create_engine(db_url, echo=False, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
	return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
