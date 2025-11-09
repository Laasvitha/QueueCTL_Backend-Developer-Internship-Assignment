import click
import json
import sqlite3
from .manager import JobQueueManager
from .worker import Worker
from multiprocessing import Process

DB_PATH = "queuectl.db"

@click.group()
def cli():
    """QueueCTL - Background Job Queue System"""
    pass

@cli.command()
@click.argument('job_json')
def enqueue(job_json):
    """Enqueue a new job.

    Example: queuectl enqueue '{"command":"echo hello"}'
    """
    try:
        job_data = json.loads(job_json)
        manager = JobQueueManager(DB_PATH)

        command = job_data.get('command')
        max_retries = job_data.get('max_retries', 3)

        if not command:
            click.echo("Error: 'command' field is required", err=True)
            return

        job_id = manager.enqueue(command, max_retries)
        click.echo(f"✓ Job {job_id} enqueued")

    except json.JSONDecodeError:
        click.echo("Error: Invalid JSON format", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.group()
def worker():
    """Manage workers"""
    pass


@worker.command()
@click.option('--count', default=1, help='Number of workers to start')
def start(count):
    """Start worker(s)"""
    click.echo(f"Starting {count} worker(s)...", err=True)

    processes = []
    for i in range(count):
        w = Worker(i, DB_PATH)
        p = Process(target=w.start, daemon=False)
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        click.echo("\nShutting down workers gracefully...", err=True)
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join()


# ============ STATUS COMMAND ============

@cli.command()
def status():
    """Show queue status"""
    manager = JobQueueManager(DB_PATH)
    summary = manager.get_queue_summary()
    dlq_jobs = manager.get_dlq_jobs()

    click.echo("\n=== Queue Status ===")
    for state in ['pending', 'processing', 'completed', 'failed']:
        count = summary.get(state, 0)
        click.echo(f"{state:15}: {count:5}")

    click.echo(f"{'dlq':15}: {len(dlq_jobs):5}")


@cli.group()
def jobs():
    """Manage jobs"""
    pass


@jobs.command()
@click.option('--state', default='pending', help='Filter by state')
def list(state):
    """List jobs by state"""
    manager = JobQueueManager(DB_PATH)
    jobs_list = manager.list_jobs_by_state(state)

    if not jobs_list:
        click.echo(f"No jobs in state: {state}")
        return

    click.echo(f"\n=== {state.upper()} Jobs ({len(jobs_list)}) ===")
    for job in jobs_list:
        attempts = f"{job['attempts']}/{job['max_retries']}"
        click.echo(f"{job['id']:10} | {job['command']:50} | Attempts: {attempts}")



@cli.group()
def dlq():
    """Manage Dead Letter Queue"""
    pass


@dlq.command()
def list():
    """List DLQ jobs"""
    manager = JobQueueManager(DB_PATH)
    dlq_jobs = manager.get_dlq_jobs()

    if not dlq_jobs:
        click.echo("DLQ is empty")
        return

    click.echo(f"\n=== Dead Letter Queue ({len(dlq_jobs)} jobs) ===")
    for job in dlq_jobs:
        click.echo(f"\n{job['id']}")
        click.echo(f"  Command: {job['command']}")
        click.echo(f"  Reason:  {job['reason'][:80]}")


@dlq.command()
@click.argument('job_id')
def retry(job_id):
    """Retry a DLQ job"""
    manager = JobQueueManager(DB_PATH)

    if manager.retry_dlq_job(job_id):
        click.echo(f"✓ Job {job_id} moved back to queue for retry")
    else:
        click.echo(f"Error: Job {job_id} not found in DLQ", err=True)



@cli.group()
def config():
    """Manage configuration"""
    pass


@config.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """Set configuration value"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)',
            (key, value)
        )
        conn.commit()

    click.echo(f"✓ Config: {key} = {value}")


if __name__ == '__main__':
    cli()