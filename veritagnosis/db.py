
from __future__ import annotations

import os
import stat

import reflex as rx
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from veritagnosis import config


def _url() -> str:
    """Reflex's own db_url, so the app and `reflex db migrate` agree."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return rx.config.get_config().db_url or f"sqlite:///{config.DB_PATH}"


engine = create_engine(
    _url(),
    echo=config.DEBUG,
    # Reflex serves event handlers from a thread pool, and SQLite's default
    # would refuse a connection reused across them.
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _harden(dbapi_conn, _record):  # noqa: ANN001
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA secure_delete=ON")
    cur.close()


def restrict_file_permissions() -> None:
    """Owner-only on the database file. POSIX only — on Windows the equivalent
    is an ACL, which Python cannot set portably."""
    if os.name == "posix" and config.DB_PATH.exists():
        os.chmod(config.DB_PATH, stat.S_IRUSR | stat.S_IWUSR)


def ensure_schema(target: "Engine | None" = None) -> list[str]:
    from sqlalchemy import inspect, text

    # SQLModel.metadata only knows about tables whose classes have been
    # imported. Without this the repair silently finds nothing to do.
    from veritagnosis import models  # noqa: F401

    # Explicit parameter rather than reaching for the module global: it makes
    # the repair testable against a throwaway database.
    eng = target if target is not None else engine
    changed: list[str] = []
    inspector = inspect(eng)
    existing_tables = set(inspector.get_table_names())

    for table in SQLModel.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all() handles brand-new tables

        have = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in have:
                continue

            col_type = column.type.compile(eng.dialect)
            with eng.begin() as conn:
                conn.execute(text(
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
                ))
                # Backfill a sensible value so old rows behave like new ones.
                default = getattr(column.default, "arg", None)
                if default is not None and not callable(default):
                    conn.execute(
                        text(f'UPDATE "{table.name}" SET "{column.name}" = :v '
                             f'WHERE "{column.name}" IS NULL'),
                        {"v": default},
                    )
            changed.append(f"{table.name}.{column.name}")

    return changed


def init_db() -> None:
    from veritagnosis import models  # noqa: F401  (registers the tables)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)

    added = ensure_schema()
    if added:
        print(f"[veritagnosis] database brought up to date: {', '.join(added)}")

    restrict_file_permissions()


def get_session() -> Session:
    """Use as `with db.get_session() as s:`."""
    return Session(engine)
