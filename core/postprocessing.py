"""Lifespan-owned queue for derived conversation writes."""
from concurrent.futures import ThreadPoolExecutor
from threading import RLock


class Postprocessing:
    def __init__(self):
        self._lock = RLock()
        self._executor = None

    def start(self):
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="cora-postprocess")

    def submit(self, fn, *args, **kwargs):
        with self._lock:
            if self._executor is None:
                raise RuntimeError("Post-processing is not running")
            return self._executor.submit(fn, *args, **kwargs)

    def shutdown(self):
        # Keep the executor visible until all accepted jobs have finished.
        # Its own shutdown gate rejects submissions while draining.
        with self._lock:
            executor = self._executor
        if executor is not None:
            executor.shutdown(wait=True)
            with self._lock:
                self._executor = None
