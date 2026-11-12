"""Persist only successful advisory assessments; never change map or test states."""
from uuid import uuid4


def latest():
    try:
        from core.infra.database import DATABASE_URL, db_connection
        if not DATABASE_URL:
            return {"evaluation": None, "available": False}
        with db_connection(ensure_schema=False) as conn:
            row = conn.execute("SELECT snapshot FROM roadmap_priority_evaluations ORDER BY created_at DESC,id DESC LIMIT 1").fetchone()
        return {"evaluation": row["snapshot"] if row else None, "available": True}
    except Exception:
        return {"evaluation": None, "available": False}


def save(evaluation):
    try:
        from psycopg.types.json import Jsonb

        from core.infra.database import db_connection
        with db_connection(ensure_schema=False) as conn:
            conn.execute("INSERT INTO roadmap_priority_evaluations (id,snapshot) VALUES (%s,%s)",
                         (str(uuid4()), Jsonb(evaluation)))
        return True
    except Exception:
        return False
