"""Active Database driver, selected by config.DATABASE.

Today only `sqlite` ships; a MySQL/Postgres driver would be a sibling file
implementing db/base.Database, added here. A Database is built only when something
needs persistence (the self-hosted store, db-backed sessions, or db-backed tenants);
the github form builds none, so its deployment never imports a DB driver.
"""
from ..config import DATABASE
from .base import Database


def build_database() -> Database:
    if DATABASE == "sqlite":
        from .sqlite import SqliteDatabase
        return SqliteDatabase()
    raise RuntimeError(f"unknown DATABASE={DATABASE!r}; expected 'sqlite' (more drivers TBD)")
