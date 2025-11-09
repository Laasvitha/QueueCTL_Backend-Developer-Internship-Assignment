import json
import subprocess
import time

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def test_basic_flow():
    job = json.dumps({"command": "echo hello", "max_retries": 2})
    r = run(f"queuectl enqueue '{job}'")
    assert r.returncode == 0, r.stderr
    job_id = r.stdout.strip().split()[-1]

    wp = subprocess.Popen(["queuectl", "worker", "start"], text=True)
    time.sleep(3)
    wp.terminate()

    r = run("queuectl jobs list --state completed")
    assert job_id in r.stdout, "Job did not complete"

def test_dlq_flow():
    job = json.dumps({"command": "exit 1", "max_retries": 1})
    r = run(f"queuectl enqueue '{job}'")
    assert r.returncode == 0, r.stderr
    job_id = r.stdout.strip().split()[-1]

    wp = subprocess.Popen(["queuectl", "worker", "start"], text=True)
    time.sleep(6)
    wp.terminate()

    r = run("queuectl dlq list")
    assert job_id in r.stdout, "Job not in DLQ"

if __name__ == "__main__":
    try:
        test_basic_flow()
        print("✓ Basic flow passed")
        test_dlq_flow()
        print("✓ DLQ flow passed")
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
        raise