"""Create or update the schema. Runs once per deployment, before the app starts."""
import os

import psycopg

LOCK_ID = 727001

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code       TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    visits     BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def migrate() -> None:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as connection:
        # The lock stops two replicas from migrating at the same moment.
        connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            connection.execute(SCHEMA)
        finally:
            connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


if __name__ == "__main__":
    migrate()
    print("migration complete")
