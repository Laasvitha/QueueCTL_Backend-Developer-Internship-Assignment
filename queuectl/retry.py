import time
import random


class RetryManager:

    def __init__(self, base: int = 2, max_jitter: float = 1.0):

        self.base = base
        self.max_jitter = max_jitter

    def calculate_backoff(self, attempt: int) -> float:
        """
        Formula: delay = (base ^ attempts) + random(0, max_jitter)
        """
        exponential_delay = self.base ** attempt
        jitter = random.uniform(0, self.max_jitter)
        return exponential_delay + jitter

    def should_retry(self, current_attempts: int, max_retries: int) -> bool:
        return current_attempts < max_retries

    def wait_before_retry(self, attempt: int):
        delay = self.calculate_backoff(attempt)
        time.sleep(delay)
