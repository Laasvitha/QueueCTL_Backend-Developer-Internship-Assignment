import uuid
from .storage import JobStorage

class JobQueueManager:
    
    def __init__(self, db_path: str = "queuectl.db"):
        self.storage = JobStorage(db_path)
    
    def enqueue(self, command: str, max_retries: int = 3) -> str:
        job_id = str(uuid.uuid4())[:8]
        success = self.storage.add_job(job_id, command, max_retries)
        
        if success:
            return job_id
        else:
            raise Exception("Failed to enqueue job")
    
    def get_status(self, job_id: str):
        return self.storage.get_job(job_id)
    
    def list_jobs_by_state(self, state: str):
        return self.storage.get_jobs_by_state(state)
    
    def get_queue_summary(self):
        return self.storage.get_job_summary()
    
    def get_dlq_jobs(self):
        return self.storage.get_dlq_jobs()
    
    def retry_dlq_job(self, job_id: str) -> bool:
        dlq_jobs = self.storage.get_dlq_jobs()
        job = next((j for j in dlq_jobs if j['id'] == job_id), None)
        
        if not job:
            return False


        self.storage.add_job(job_id, job['command'], job['max_retries'])
        

        self.storage.remove_from_dlq(job_id)
        
        return True
