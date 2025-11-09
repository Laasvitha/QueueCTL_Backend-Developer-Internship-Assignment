import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict

class JobStorage:

    def __init__(self, db_path: str = "queuectl.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                         CREATE TABLE IF NOT EXISTS jobs
                         (
                             id TEXT PRIMARY KEY,
                             command TEXT NOT NULL,
                             state TEXT NOT NULL DEFAULT 'pending',
                             attempts INTEGER DEFAULT 0,
                             max_retries INTEGER DEFAULT 3,
                             created_at TEXT NOT NULL,
                             updated_at TEXT NOT NULL,
                             output TEXT,
                             error TEXT
                         )
                         ''')
            conn.execute('''
                         CREATE TABLE IF NOT EXISTS dlq_jobs
                         (
                             id TEXT PRIMARY KEY,
                             command TEXT NOT NULL,
                             moved_at TEXT NOT NULL,
                             attempts INTEGER,
                             max_retries INTEGER,
                             reason TEXT,
                             original_job JSON
                         )
                         ''')
            conn.execute('''
                         CREATE TABLE IF NOT EXISTS config
                         (
                             key TEXT PRIMARY KEY,
                             value TEXT
                         )
                         ''')
            conn.commit()

    def add_job(self, job_id: str, command: str, max_retries: int = 3) -> bool:
        now = datetime.utcnow().isoformat() + "Z"
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                             INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at)
                             VALUES (?, ?, 'pending', 0, ?, ?, ?)
                             ''', (job_id, command, max_retries, now, now))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_job(self, job_id: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def get_pending_jobs(self, limit: int = 10) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                                  SELECT *
                                  FROM jobs
                                  WHERE state = 'pending'
                                  ORDER BY created_at ASC LIMIT ?
                                  ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_job_state(self, job_id: str, new_state: str,
                         output: str = "", error: str = ""):
        now = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                         UPDATE jobs
                         SET state      = ?,
                             updated_at = ?,
                             output     = ?,
                             error      = ?
                         WHERE id = ?
                         ''', (new_state, now, output, error, job_id))
            conn.commit()

    def increment_attempts(self, job_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                         UPDATE jobs
                         SET attempts = attempts + 1
                         WHERE id = ?
                         ''', (job_id,))
            conn.commit()

    def move_to_dlq(self, job_id: str, reason: str):
        job = self.get_job(job_id)
        if not job:
            return

        now = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                         INSERT INTO dlq_jobs
                             (id, command, moved_at, attempts, max_retries, reason, original_job)
                         VALUES (?, ?, ?, ?, ?, ?, ?)
                         ''', (
                             job_id,
                             job['command'],
                             now,
                             job['attempts'],
                             job['max_retries'],
                             reason,
                             json.dumps(dict(job))
                         ))
            conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
            conn.commit()

    def get_dlq_jobs(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM dlq_jobs ORDER BY moved_at DESC')
            return [dict(row) for row in cursor.fetchall()]

    def remove_from_dlq(self, job_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM dlq_jobs WHERE id = ?', (job_id,))
            conn.commit()

    def get_job_summary(self) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                                  SELECT state, COUNT(*) as count
                                  FROM jobs
                                  GROUP BY state
                                  ''')
            summary = {}
            for state, count in cursor.fetchall():
                summary[state] = count
        return summary

    def get_jobs_by_state(self, state: str) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM jobs WHERE state = ? ORDER BY created_at DESC',
                (state,)
            )
            return [dict(row) for row in cursor.fetchall()]
