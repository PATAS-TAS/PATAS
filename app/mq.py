"""
Simple message-queue abstraction for async processing (vision-stage).
Current backend: in-memory queue with background worker stubs.
Future backends: Redis Stream, RabbitMQ, SQS.
"""
import threading
import queue
import time
import uuid
from typing import Callable, Dict, Optional, Any


class InMemoryQueue:
    def __init__(self):
        self.q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.status: Dict[str, Dict[str, Any]] = {}
        self._stop = False
        self._thread: Optional[threading.Thread] = None

    def start(self, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        if self._thread and self._thread.is_alive():
            return

        def _run():
            while not self._stop:
                try:
                    job = self.q.get(timeout=0.5)
                except queue.Empty:
                    continue
                job_id = job["job_id"]
                self.status[job_id] = {"state": "processing"}
                try:
                    result = handler(job)
                    self.status[job_id] = {"state": "done", "result": result}
                except Exception as e:
                    self.status[job_id] = {"state": "error", "error": str(e)}
                finally:
                    self.q.task_done()

        self._stop = False
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.join(timeout=2)

    def enqueue(self, payload: Dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        job = {"job_id": job_id, **payload}
        self.status[job_id] = {"state": "queued"}
        self.q.put(job)
        return job_id

    def get_status(self, job_id: str) -> Dict[str, Any]:
        return self.status.get(job_id, {"state": "not_found"})


_queue: Optional[InMemoryQueue] = None


def get_queue() -> InMemoryQueue:
    global _queue
    if _queue is None:
        _queue = InMemoryQueue()
        # Default no-op handler
        _queue.start(lambda job: {"ok": True, "job_id": job["job_id"]})
    return _queue


