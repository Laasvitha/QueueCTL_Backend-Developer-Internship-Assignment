import subprocess
import signal
import time
import sys
from typing import Optional, Dict
from .storage import JobStorage
from .retry import RetryManager


class Worker:

    def __init__(self, worker_id: int, db_path: str = "queuectl.db"):
        self.worker_id = worker_id
        self.storage = JobStorage(db_path)
        self.retry_manager = RetryManager()
        self.running = True
        self.current_job_id: Optional[str] = None

        # Graceful shutdown handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        print(f"\n[Worker {self.worker_id}] Received shutdown signal", file=sys.stderr)
        self.running = False

    def start(self):
        print(f"[Worker {self.worker_id}] Started", file=sys.stderr)
        sys.stderr.flush()

        while self.running:
            try:
                # Get a pending job
                jobs = self.storage.get_pending_jobs(limit=1)

                if not jobs:
                    # No jobs available, sleep briefly
                    time.sleep(1)
                    continue

                job = jobs[0]
                self.current_job_id = job['id']
                self._execute_job(job)

            except Exception as e:
                print(f"[Worker {self.worker_id}] Error: {e}", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(1)

        print(f"[Worker {self.worker_id}] Stopped", file=sys.stderr)
        sys.stderr.flush()

    def _execute_job(self, job: Dict):
        job_id = job['id']
        command = job['command']

        try:
            print(f"[Worker {self.worker_id}] Processing {job_id}: {command}", file=sys.stderr)
            sys.stderr.flush()

            self.storage.update_job_state(job_id, "processing")

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                self.storage.update_job_state(
                    job_id,
                    "completed",
                    output=result.stdout
                )
                print(f"[Worker {self.worker_id}] Job {job_id} COMPLETED", file=sys.stderr)
                sys.stderr.flush()
            else:
                self._handle_job_failure(job, result.stderr or result.stdout)

        except subprocess.TimeoutExpired:
            self._handle_job_failure(job, "Command timeout (5 minutes exceeded)")
        except Exception as e:
            self._handle_job_failure(job, str(e))

    def _handle_job_failure(self, job: Dict, error_msg: str):
        job_id = job['id']
        attempts = job['attempts']
        max_retries = job['max_retries']

        print(f"[Worker {self.worker_id}] Job {job_id} FAILED: {error_msg}", file=sys.stderr)
        sys.stderr.flush()

        self.storage.increment_attempts(job_id)

        if self.retry_manager.should_retry(attempts + 1, max_retries):
            print(f"[Worker {self.worker_id}] Retry {attempts + 1}/{max_retries}", file=sys.stderr)
            sys.stderr.flush()

            self.storage.update_job_state(job_id, "failed", error=error_msg)

            delay = self.retry_manager.calculate_backoff(attempts)
            print(f"[Worker {self.worker_id}] Waiting {delay:.1f}s before retry...", file=sys.stderr)
            sys.stderr.flush()

            if self.running:
                time.sleep(delay)
                self.storage.update_job_state(job_id, "pending")
        else:
            print(f"[Worker {self.worker_id}] Job {job_id} moved to DLQ (max retries: {max_retries})",
                  file=sys.stderr)
            sys.stderr.flush()

            reason = f"Max retries ({max_retries}) exceeded. Last error: {error_msg}"
            self.storage.move_to_dlq(job_id, reason)
            self.storage.update_job_state(job_id, "dead", error=error_msg)