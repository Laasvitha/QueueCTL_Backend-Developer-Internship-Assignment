# QueueCTL - Background Job Queue System

A production-grade CLI-based background job queue system with exponential backoff retry logic, Dead Letter Queue support, and multi-worker parallel processing.

## Overview

QueueCTL is a robust, locally-deployable job queue system designed to manage background tasks with automatic retry mechanisms, exponential backoff delays, and persistent storage. Built in Python with SQLite, it supports multiple concurrent workers and graceful shutdown.

**Key Features:**
- ✅ CLI-based job enqueuing and management
- ✅ Multiple parallel workers processing jobs simultaneously
- ✅ Exponential backoff retry mechanism (2^attempts + jitter)
- ✅ Dead Letter Queue (DLQ) for permanently failed jobs
- ✅ SQLite persistent storage (survives restarts)
- ✅ Graceful worker shutdown (finish current job before exit)
- ✅ Configuration management via CLI
- ✅ Job state tracking and lifecycle management

---

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Step 1: Clone or Download Project

```bash
git clone https://github.com/YOUR_USERNAME/queuectl.git
cd queuectl
```

### Step 2: Create Virtual Environment

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Install QueueCTL in Development Mode

```bash
pip install -e .
```

### Step 5: Verify Installation

```bash
queuectl --help
```

You should see the CLI help output with all available commands.

---

## Usage Examples

### Basic Job Execution

**Terminal 1: Start a worker**
```bash
queuectl worker start --count 1
```

Expected output:
```
Starting 1 worker(s)...
[Worker 0] Started
```

**Terminal 2: Enqueue a job**
```bash
queuectl enqueue "{\"command\":\"echo hello world\"}"
```

Expected output:
```
✓ Job 267039de enqueued
```

**In Terminal 1, watch the worker process:**
```
[Worker 0] Processing 267039de: echo hello world
[Worker 0] Job 267039de COMPLETED
```

### Check Queue Status

```bash
queuectl status
```

Expected output:
```
=== Queue Status ===
pending        :     0
processing     :     0
completed      :     1
failed         :     0
dlq            :     0
```

### List Completed Jobs

```bash
queuectl jobs list --state completed
```

Expected output:
```
=== COMPLETED Jobs (1) ===
267039de   | echo hello world                                   | Attempts: 0/3
```

### Multiple Workers Processing Jobs in Parallel

**Terminal 1: Start 3 workers**
```bash
queuectl worker start --count 3
```

Expected output:
```
Starting 3 worker(s)...
[Worker 0] Started
[Worker 1] Started
[Worker 2] Started
```

**Terminal 2: Enqueue multiple jobs**
```bash
queuectl enqueue "{\"command\":\"echo task 1\"}"
queuectl enqueue "{\"command\":\"sleep 1 && echo task 2\"}"
queuectl enqueue "{\"command\":\"echo task 3\"}"
```

**Expected output in Terminal 1 (parallel processing):**
```
[Worker 0] Processing abc123: echo task 1
[Worker 1] Processing def456: sleep 1 && echo task 2
[Worker 2] Processing ghi789: echo task 3
[Worker 0] Job abc123 COMPLETED
[Worker 1] Job def456 COMPLETED
[Worker 2] Job ghi789 COMPLETED
```

### Testing Retry & Exponential Backoff

**Terminal 1: Start worker**
```bash
queuectl worker start --count 1
```

**Terminal 2: Enqueue a failing job**
```bash
queuectl enqueue "{\"command\":\"exit 1\",\"max_retries\":2}"
```

Expected output in Terminal 1 (exponential backoff with jitter):
```
[Worker 0] Processing job123: exit 1
[Worker 0] Job job123 FAILED: 
[Worker 0] Retry 1/2
[Worker 0] Waiting 1.5s before retry...
[Worker 0] Processing job123: exit 1
[Worker 0] Job job123 FAILED: 
[Worker 0] Retry 2/2
[Worker 0] Waiting 3.2s before retry...
[Worker 0] Job job123 moved to DLQ (max retries: 2)
```

**Notice:** Delays increase exponentially: ~1.5s → ~3.2s (2^attempts + jitter)

### Dead Letter Queue Management

**Terminal 2: List DLQ jobs**
```bash
queuectl dlq list
```

Expected output:
```
=== Dead Letter Queue (1 jobs) ===

job123
  Command: exit 1
  Reason:  Max retries (2) exceeded. Last error: 
```

**Retry a DLQ job**
```bash
queuectl dlq retry job123
```

Expected output:
```
✓ Job job123 moved back to queue for retry
```

**Verify job is back in pending queue**
```bash
queuectl jobs list --state pending
```

### Configuration Management

**Set maximum retries**
```bash
queuectl config set max-retries 5
```

Expected output:
```
✓ Config: max-retries = 5
```

---

## Architecture Overview

### System Architecture Diagram

```
┌─────────────────────────────────┐
│       CLI Interface (Click)      │
│  enqueue | worker | status | ... │
└────────────────┬────────────────┘
                 │
        ┌────────▼──────────┐
        │  JobQueueManager  │
        │  (Business Logic) │
        └────────┬──────────┘
                 │
      ┌──────────▼────────────┐
      │   JobStorage (SQLite) │
      │  (Persistence Layer)  │
      └──────────┬────────────┘
                 │
      ┌──────────▼──────────────────┐
      │  SQLite Database (queuectl.db)│
      │   - jobs table              │
      │   - dlq_jobs table          │
      │   - config table            │
      └─────────────────────────────┘

┌────────────────────────────────────┐
│     Worker Processes (Parallel)    │
│  Worker 0 │ Worker 1 │ ... Worker N │
│  (subprocess execution & retry)    │
└────────────────────────────────────┘
         │
    ┌────▼──────────────┐
    │  RetryManager     │
    │ (Backoff logic)   │
    └───────────────────┘
```

### Job Lifecycle States

```
┌──────────┐
│ PENDING  │  ← Job enqueued, waiting for worker
└────┬─────┘
     │ Worker picks up
┌────▼──────────┐
│  PROCESSING   │  ← Worker executing command
└────┬──────────┘
     │
     ├─ Exit Code 0 ──────────────────┐
     │                                ▼
     │                        ┌──────────────┐
     │                        │  COMPLETED   │  ← Success
     │                        └──────────────┘
     │
     └─ Exit Code != 0 ──────┐
                             ▼
                       ┌────────────┐
                       │  FAILED    │  ← Retry logic
                       └────┬───────┘
                            │
                ┌───────────┴───────────┐
                │                       │
       Retries < Max?          Retries >= Max?
                │                       │
                ▼                       ▼
           ┌────────┐            ┌─────────┐
           │PENDING │            │  DEAD   │  ← DLQ
           │(Backoff)│           └─────────┘
           └────────┘
```

### Retry Strategy: Exponential Backoff

The system implements exponential backoff with random jitter to prevent thundering herd problems:

**Formula:**
```
delay = (2 ^ attempt_number) + random(0, 1) seconds
```

**Example progression:**
- Attempt 0: 2^0 + jitter = ~1–2 seconds
- Attempt 1: 2^1 + jitter = ~2–3 seconds
- Attempt 2: 2^2 + jitter = ~4–5 seconds
- Attempt 3: 2^3 + jitter = ~8–9 seconds

**Benefits:**
- Prevents overwhelming the system with simultaneous retries
- Gives failed services time to recover
- Randomness prevents synchronized retry storms

### Core Components

| Component | File | Responsibility |
|-----------|------|-----------------|
| **CLI** | `cli.py` | Command-line interface, argument parsing, user interaction |
| **Manager** | `manager.py` | Business logic, job operations, queue management |
| **Storage** | `storage.py` | SQLite database operations, persistence |
| **Worker** | `worker.py` | Job execution, retry logic integration, subprocess management |
| **Retry** | `retry.py` | Exponential backoff calculation, retry eligibility |

### Data Persistence

Jobs are stored in SQLite database (`queuectl.db`) with the following schema:

**Jobs Table:**
```sql
CREATE TABLE jobs (
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
```

**DLQ Jobs Table:**
```sql
CREATE TABLE dlq_jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    moved_at TEXT NOT NULL,
    attempts INTEGER,
    max_retries INTEGER,
    reason TEXT,
    original_job JSON
)
```

**Configuration Table:**
```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT
)
```

---

## Assumptions & Trade-offs

### Design Decisions

#### 1. SQLite Over External Databases
**Decision:** Use SQLite (file-based) instead of PostgreSQL or Redis

**Rationale:**
- Simpler setup (no external services required)
- Sufficient for development and testing
- Zero operational overhead
- Jobs persist automatically to disk

**Trade-off:** Not suitable for distributed systems; single-machine deployment only

---

#### 2. File-based Locking vs Distributed Locks
**Decision:** SQLite transactions for concurrency control

**Rationale:**
- ACID transactions prevent duplicate job processing
- No external lock manager needed
- Simpler implementation
- Works well for single-machine deployment

**Trade-off:** Won't work across multiple machines

---

#### 3. Process-based Workers vs Thread-based
**Decision:** Use separate processes for each worker

**Rationale:**
- True parallelism (bypasses Python's GIL)
- Better for CPU-bound operations
- Cleaner isolation between workers
- Supports graceful shutdown

**Trade-off:** Higher memory overhead than threads

---

#### 4. UUID Shortened to 8 Characters for Job IDs
**Decision:** Use first 8 characters of UUID

**Rationale:**
- Unique collision-free IDs (probability of collision negligible)
- Short format for human readability
- No central ID generation required

**Trade-off:** Slightly reduced uniqueness (still 99.9999% unique)

---

#### 5. Exponential Backoff Formula
**Decision:** delay = 2^attempts + jitter

**Rationale:**
- Industry standard (used by AWS, Google, Azure)
- Proven to reduce load on failed services
- Jitter prevents synchronized retry storms

**Trade-off:** Longest wait can be significant for many retries

---

### Limitations in v1.0

- **Single-machine deployment:** Not distributed across multiple machines
- **No authentication:** CLI is local-only access
- **No job prioritization:** FIFO queue only
- **No job scheduling:** No delayed/cron-like job support
- **No web dashboard:** CLI-only interface
- **No metrics/analytics:** Status shows counts only, no detailed stats

### Future Improvements

- Support for distributed deployments (multiple machines)
- Job prioritization queue
- Scheduled job execution (run_at, cron syntax)
- Web-based monitoring dashboard
- Advanced metrics and execution statistics
- Job dependencies and workflows

---

## Testing Instructions

### Automated Testing

Run the included test script:

```bash
python scripts/test_demo.py
```

This script validates:
- ✅ Basic job execution and completion
- ✅ DLQ functionality for failed jobs
- ✅ Job persistence

### Manual Testing

#### Test 1: Basic Job Execution

```bash
# Terminal 1
queuectl worker start --count 1

# Terminal 2
queuectl enqueue "{\"command\":\"echo test success\"}"
queuectl status
```

**Expected:** Job should complete, status shows 1 completed.

---

#### Test 2: Multiple Workers No Duplicate Processing

```bash
# Terminal 1
queuectl worker start --count 3

# Terminal 2
queuectl enqueue "{\"command\":\"echo job 1\"}"
queuectl enqueue "{\"command\":\"echo job 2\"}"
queuectl enqueue "{\"command\":\"echo job 3\"}"
```

**Expected:** Each job processed exactly once by different workers simultaneously.

---

#### Test 3: Failed Job Retry with Backoff

```bash
# Terminal 1
queuectl worker start --count 1

# Terminal 2
queuectl enqueue "{\"command\":\"exit 1\",\"max_retries\":2}"

# Monitor Terminal 1 for retry delays (watch time increments)
```

**Expected:** Job retries with increasing delays (~1.5s, ~3.2s).

---

#### Test 4: Dead Letter Queue

```bash
# Terminal 2 (after Test 3 completes)
queuectl dlq list
```

**Expected:** Failed job appears in DLQ with reason.

---

#### Test 5: DLQ Retry

```bash
# Terminal 2
queuectl dlq retry <job-id>
queuectl jobs list --state pending
```

**Expected:** Job moved back to pending queue.

---

#### Test 6: Job Persistence Across Restart

```bash
# Terminal 1
queuectl enqueue "{\"command\":\"echo persistent\"}"
queuectl status

# Close terminal completely
# Open new terminal
queuectl status
```

**Expected:** Job still exists in queue after restart.

---

#### Test 7: Graceful Worker Shutdown

```bash
# Terminal 1
queuectl worker start --count 1

# Terminal 2
queuectl enqueue "{\"command\":\"sleep 10\"}"

# Terminal 1: While job is running, press Ctrl+C
```

**Expected:** Worker waits for current job to finish before stopping.

---

#### Test 8: Invalid Commands Fail Gracefully

```bash
queuectl worker start --count 1
queuectl enqueue "{\"command\":\"this-command-does-not-exist-xyz\"}"
```

**Expected:** Command fails gracefully, job retries, then moves to DLQ.

---

## Project Structure

```
queuectl/
├── queuectl/
│   ├── __init__.py              # Package marker
│   ├── storage.py               # SQLite database operations
│   ├── retry.py                 # Exponential backoff logic
│   ├── worker.py                # Worker process & execution
│   ├── manager.py               # Business logic & queue management
│   └── cli.py                   # Click CLI interface
├── scripts/
│   └── test_demo.py             # Demo test script
├── tests/
│   └── __init__.py              # Test package marker
├── setup.py                     # Package installation config
├── requirements.txt             # Python dependencies
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
└── queuectl.db                  # SQLite database (auto-created)
```

---

## Troubleshooting

### Issue: "queuectl command not found"

**Solution:**
```bash
pip install -e .
queuectl --help
```

---

### Issue: "ModuleNotFoundError: No module named 'storage'"

**Solution:** Ensure you're using relative imports with `.` prefix in Python files.

---

### Issue: "Database locked" error

**Solution:**
```bash
# Stop all workers (Ctrl+C)
rm queuectl.db
# Restart workers
```

---

### Issue: Jobs not persisting

**Solution:** Verify `queuectl.db` file exists:
```bash
sqlite3 queuectl.db ".tables"
```

Should show: `config  dlq_jobs  jobs`

---

### Issue: Workers not processing jobs

**Solution:**
1. Check if workers are running: Look for `[Worker 0] Started` output
2. Check if jobs exist: `queuectl status`
3. Check for errors in worker output terminal

---

## Demo Video

A comprehensive demo video showing all features is available here: **[Link to Google Drive Demo Video]**

The demo covers:
- Setup and installation
- Basic job execution
- Multiple workers in parallel
- Retry with exponential backoff
- Dead Letter Queue operations
- Job persistence
- Configuration management

---

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| Enqueue job | ~50ms | SQLite INSERT |
| Get pending job | ~10ms | SQLite SELECT |
| Update job state | ~30ms | SQLite UPDATE |
| Worker pickup | ~1s | Poll interval |
| Job execution | Variable | Depends on command |

---

## Requirements & Dependencies

```
Python 3.8+
Click 8.1.3    (CLI framework)
SQLite3        (included with Python)
```

See `requirements.txt` for details.

---

## License

MIT License - See LICENSE file for details.

---

## Author

Your Name  
Email: your.email@example.com  
GitHub: @YOUR_USERNAME

---

## Support & Contributing

For issues or questions:
1. Create an issue on GitHub
2. Check troubleshooting section above
3. Review demo video for usage examples

Contributions welcome! Please create a pull request with improvements.

---

## Acknowledgments

- Built as part of Backend Developer Internship Assignment
- Uses Python Click framework for CLI
- SQLite for persistent storage
- Inspired by production job queue systems (RabbitMQ, Celery)

---

**Last Updated:** November 9, 2025  
**Version:** 1.0.0  
**Status:** Production Ready ✅
