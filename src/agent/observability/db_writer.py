# src/agent/observability/db_writer.py
#
# Writes agent run data to PostgreSQL.
# Called at key points in the pipeline to persist state.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import uuid
from datetime import datetime
from src.agent.core.settings import DATABASE_URL

# Use synchronous psycopg2 for simple writes
# (async would require restructuring the entire agent)


def get_sync_connection():
    """Returns a synchronous PostgreSQL connection."""
    try:
        import psycopg2

        # Convert asyncpg URL to psycopg2 format
        sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        return psycopg2.connect(sync_url)
    except Exception as e:
        print(f"  ⚠️  DB connection failed: {e}")
        return None


def save_agent_run(run_id: str) -> bool:
    """
    Creates a new agent_run record when the agent starts.
    Returns True if saved successfully.
    """
    conn = get_sync_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_runs (id, started_at, status, total_tokens, cost_usd)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """,
            (run_id, datetime.utcnow(), "running", 0, 0.0),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  ⚠️  save_agent_run failed: {e}")
        return False
    finally:
        conn.close()


def complete_agent_run(
    run_id: str,
    status: str = "completed",
    error: str = "",
) -> bool:
    """
    Updates agent_run when pipeline finishes.
    Status: completed | failed
    """
    conn = get_sync_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE agent_runs
            SET ended_at = %s,
                status = %s,
                error = %s
            WHERE id = %s
        """,
            (datetime.utcnow(), status, error, run_id),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  ⚠️  complete_agent_run failed: {e}")
        return False
    finally:
        conn.close()


def save_post(
    post_id: str,
    content: str,
    pillar: str,
    selected_idea: str,
    status: str = "draft",
) -> bool:
    """
    Saves a generated post to the posts table.
    Called after draft node completes.
    """
    conn = get_sync_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO posts (id, content, status, pillar, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET content = EXCLUDED.content,
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at
        """,
            (
                post_id,
                content,
                status,
                pillar,
                datetime.utcnow(),
                datetime.utcnow(),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  ⚠️  save_post failed: {e}")
        return False
    finally:
        conn.close()


def save_critique(
    post_id: str,
    score_json: dict,
    feedback: str,
    draft_version: int = 1,
) -> bool:
    """
    Saves critique scores to the critiques table.
    Called after critique node completes.
    """
    conn = get_sync_connection()
    if not conn:
        return False

    try:
        import json

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO critiques (id, post_id, draft_version, score_json, feedback, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (
                str(uuid.uuid4()),
                post_id,
                draft_version,
                json.dumps(score_json),
                feedback,
                datetime.utcnow(),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  ⚠️  save_critique failed: {e}")
        return False
    finally:
        conn.close()


def update_post_status(
    post_id: str,
    status: str,
    linkedin_urn: str = "",
    scheduled_for: str = "",
) -> bool:
    """
    Updates post status after approval/publishing.
    Status: pending_approval | approved | scheduled | published | rejected
    """
    conn = get_sync_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE posts
            SET status = %s,
                linkedin_post_urn = %s,
                updated_at = %s
            WHERE id = %s
        """,
            (
                status,
                linkedin_urn,
                datetime.utcnow(),
                post_id,
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  ⚠️  update_post_status failed: {e}")
        return False
    finally:
        conn.close()
