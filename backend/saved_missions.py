"""Persistence for lightweight saved mission profiles.

Scientific calculations stay in ``src``. This module stores only the inputs
needed to recreate a mission plan, never derived telemetry or ML results.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID

logger = logging.getLogger("lunar_horizon.storage")
SCHEMA_PATH = Path(__file__).with_name("sql") / "001_saved_mission_profiles.sql"


class StoreUnavailable(RuntimeError):
    """Raised when the configured SQL store cannot be reached or is missing."""


def _owner_hash(owner_id: UUID) -> str:
    return hashlib.sha256(owner_id.bytes).hexdigest()


def _connection():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise StoreUnavailable("DATABASE_URL is not configured")
    try:
        import psycopg
        from psycopg.rows import dict_row

        connection = psycopg.connect(url, connect_timeout=5, row_factory=dict_row)
        return connection
    except Exception as exc:
        logger.warning("Could not connect to the saved mission SQL store (%s)", type(exc).__name__)
        raise StoreUnavailable("Saved mission storage is unavailable") from exc


def _run(operation):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                schema = SCHEMA_PATH.read_text(encoding="utf-8")
                for statement in schema.split(";"):
                    if statement.strip():
                        cursor.execute(statement)
                result = operation(cursor)
            return result
    except StoreUnavailable:
        raise
    except Exception as exc:
        logger.warning("Saved mission SQL operation failed (%s)", type(exc).__name__)
        raise StoreUnavailable("Saved mission storage is unavailable") from exc


def list_profiles(owner_id: UUID) -> list[dict[str, Any]]:
    owner_hash = _owner_hash(owner_id)

    def query(cursor):
        cursor.execute(
            """SELECT id, name, site_id, site_name, launch_utc, transit_days,
                      surface_days, step_minutes, created_at
               FROM saved_mission_profiles
               WHERE owner_hash = %s
               ORDER BY created_at DESC
               LIMIT 50""",
            (owner_hash,),
        )
        return list(cursor.fetchall())

    return _run(query)


def create_profile(owner_id: UUID, profile: dict[str, Any]) -> dict[str, Any]:
    owner_hash = _owner_hash(owner_id)

    def insert(cursor):
        cursor.execute(
            """INSERT INTO saved_mission_profiles
                   (owner_hash, name, site_id, site_name, launch_utc,
                    transit_days, surface_days, step_minutes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id, name, site_id, site_name, launch_utc, transit_days,
                         surface_days, step_minutes, created_at""",
            (
                owner_hash,
                profile["name"],
                profile["site_id"],
                profile["site_name"],
                profile["launch_utc"],
                profile["transit_days"],
                profile["surface_days"],
                profile["step_minutes"],
            ),
        )
        created = cursor.fetchone()
        cursor.execute(
            """DELETE FROM saved_mission_profiles
               WHERE owner_hash = %s
                 AND id NOT IN (
                     SELECT id FROM saved_mission_profiles
                     WHERE owner_hash = %s
                     ORDER BY created_at DESC
                     LIMIT 50
                 )""",
            (owner_hash, owner_hash),
        )
        return created

    return _run(insert)


def delete_profile(owner_id: UUID, profile_id: UUID) -> bool:
    owner_hash = _owner_hash(owner_id)

    def delete(cursor):
        cursor.execute(
            "DELETE FROM saved_mission_profiles WHERE id = %s AND owner_hash = %s",
            (profile_id, owner_hash),
        )
        return cursor.rowcount > 0

    return _run(delete)
