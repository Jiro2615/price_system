"""Read-only cooperative pause signal, checked only between worker batches."""
import os
from db_config import connect_db


def maintenance_pause_requested(run_id=None):
    run_id = run_id or os.environ.get('WEB_ORCHESTRATOR_MANAGED_RUN_ID', '')
    if not run_id:
        return False
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload_json->>'_maintenance_pause_requested' FROM job_runs WHERE run_id=%s", (run_id,))
            row=cur.fetchone()
            return bool(row and row[0]=='true')
