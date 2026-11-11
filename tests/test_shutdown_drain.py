"""Event-gated regressions for shutdown with work still using the database."""
import asyncio
import os
import threading
import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import api
from core.postprocessing import Postprocessing
from core.runtime import Run, Runtime


class ShutdownDrainTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('core.runtime.append_event'))
        self.stack.enter_context(patch('core.models.performance_configuration', return_value={}))
        self.stack.enter_context(patch('core.database.database_configured', return_value=False))

    def test_shutdown_waits_for_running_and_cancels_queued_work(self):
        runtime = Runtime(persistent=False)
        started, release, stopped = (threading.Event() for _ in range(3))
        effects = []
        def execute(run):
            started.set()
            release.wait()
            return {}
        run = runtime.submit('active', execute)
        self.assertTrue(started.wait(2))
        queued = runtime.submit('queued', lambda run: effects.append('unexpected'))
        worker = threading.Thread(target=lambda: (runtime.shutdown(), stopped.set()))
        worker.start()
        try:
            self.assertTrue(run.cancel.wait(2))
            self.assertFalse(stopped.is_set())
            with self.assertRaises(RuntimeError):
                runtime.submit('late', execute)
            self.assertTrue(queued.done.wait(2))
            self.assertEqual(effects, [])
        finally:
            release.set()
            worker.join(3)
        self.assertTrue(stopped.is_set())
        self.assertTrue(run.done.is_set())
        runtime.shutdown()  # Idempotent after draining.

    def test_terminal_worker_is_retained_and_awaited_during_final_database_write(self):
        runtime = Runtime(persistent=False)
        writing, release, stopped = (threading.Event() for _ in range(3))
        @contextmanager
        def connection():
            writing.set()
            release.wait()
            raise OSError('injected final write failure')
            yield
        with patch('core.database.database_configured', return_value=True), patch(
            'core.database.db_connection', connection
        ):
            run = runtime.submit('terminal', lambda run: {})
            self.assertTrue(writing.wait(2))
            self.assertEqual(run.status, 'completed')
            # Exercise history eviction while this terminal worker is unfinished.
            with runtime.lock:
                for n in range(200):
                    old = Run(str(n)); old.status = 'completed'; old.done.set()
                    runtime.runs[old.id] = old
            other = runtime.submit('next', lambda run: {})
            self.assertIn(run.id, runtime.runs)
            worker = threading.Thread(target=lambda: (runtime.shutdown(), stopped.set()))
            worker.start()
            try:
                self.assertTrue(other.cancel.wait(2))
                self.assertFalse(stopped.is_set())
            finally:
                release.set()
                worker.join(3)
            self.assertTrue(stopped.is_set())
            self.assertTrue(run.done.is_set())

    def test_lifespan_drains_late_and_queued_postprocessing_before_pool_close(self):
        self.check_lifespan_drain()

    def test_cancellation_finalization_waits_for_stop_transition(self):
        runtime = Runtime(persistent=False)
        run = Run('cancellation-race')
        run.status = 'running'
        stopping, release_stop, finalizing = (threading.Event() for _ in range(3))
        errors = []

        class ObservedLock:
            def __init__(self):
                self.lock = threading.RLock()

            def __enter__(self):
                if threading.current_thread() is finisher:
                    finalizing.set()
                self.lock.acquire()
                return self

            def __exit__(self, *args):
                self.lock.release()

        run.lock = ObservedLock()
        transition = run.transition

        def paused_transition(status):
            if threading.current_thread() is stopper and status == 'cancelling':
                stopping.set()
                if not release_stop.wait(3):
                    raise TimeoutError('Stop transition was not released')
            transition(status)

        def capture(fn):
            try:
                fn()
            except BaseException as error:
                errors.append(error)

        stopper = threading.Thread(target=lambda: capture(run.stop))
        finisher = threading.Thread(target=lambda: capture(lambda: runtime._finish(run, 'cancelled')))
        with patch.object(run, 'transition', paused_transition):
            stopper.start()
            try:
                self.assertTrue(stopping.wait(2))
                self.assertTrue(run.cancel.is_set())
                finisher.start()
                self.assertTrue(finalizing.wait(2))
            finally:
                release_stop.set()
                stopper.join(3)
                if finisher.ident is not None:
                    finisher.join(3)
        self.assertFalse(stopper.is_alive())
        self.assertFalse(finisher.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(run.status, 'cancelled')

    @unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'),
                         'Requires disposable PostgreSQL+pgvector')
    def test_lifespan_drain_with_real_pool_and_durable_run(self):
        self.check_lifespan_drain(use_postgres=True)

    def check_lifespan_drain(self, use_postgres=False):
        from core import database
        if use_postgres:
            self.stack.enter_context(patch('core.database.database_configured', return_value=True))
            with database.db_connection() as conn:
                conn.execute('SELECT 1')
            pool = database.get_pool()
        runtime, queue = Runtime(persistent=use_postgres), Postprocessing()
        running, release_run, processing, release_jobs, pool_closed = (
            threading.Event() for _ in range(5))
        draining = threading.Event()
        original_shutdown = queue.shutdown
        def drain():
            draining.set()
            original_shutdown()
        writes, errors = [], []
        def write(value):
            processing.set()
            release_jobs.wait()
            self.assertFalse(pool_closed.is_set())
            if use_postgres:
                self.assertFalse(pool.closed)
                with database.db_connection() as conn:
                    conn.execute('SELECT 1')
            writes.append(value)
        def close_pool():
            if use_postgres:
                database.close_pool()
            pool_closed.set()
        def execute(run):
            running.set()
            release_run.wait()
            # Accepted even after cooperative cancellation: drain runs first.
            queue.submit(write, 'late')
            return {}
        def lifecycle():
            async def run_lifecycle():
                async with api.lifespan(None):
                    queue.submit(write, 'first')
                    queue.submit(write, 'queued')
                    runtime.submit('active', execute)
                    self.assertTrue(running.wait(2))
            try:
                asyncio.run(run_lifecycle())
            except BaseException as error:
                errors.append(error)
        with ExitStack() as mocks:
            for target in ['api.validate_runtime_profile', 'core.runtime.recover_interrupted',
                           'core.observability.archive.start', 'core.observability.archive.stop',
                           'core.background_embeddings.start', 'core.background_embeddings.stop',
                           'core.library_monitor.start', 'core.library_monitor.stop',
                           'core.project_checks.start', 'core.project_checks.stop',
                           'api.notification_worker.start', 'api.notification_worker.stop']:
                mocks.enter_context(patch(target))
            mocks.enter_context(patch.object(api, 'runtime', runtime))
            mocks.enter_context(patch.object(api, 'postprocess', queue))
            mocks.enter_context(patch.object(queue, 'shutdown', drain))
            mocks.enter_context(patch.object(api, 'close_pool', close_pool))
            worker = threading.Thread(target=lifecycle)
            worker.start()
            try:
                self.assertTrue(running.wait(2))
                self.assertTrue(processing.wait(2))
                self.assertTrue(next(iter(runtime.runs.values())).cancel.wait(2))
                self.assertFalse(pool_closed.is_set())
                release_run.set()
                self.assertTrue(next(iter(runtime.runs.values())).done.wait(2))
                run = next(iter(runtime.runs.values()))
                self.assertEqual(run.status, 'cancelled')
                if use_postgres:
                    from core.run_lifecycle import get_run
                    self.assertEqual(get_run(run.id)['status'], 'cancelled')
                self.assertTrue(draining.wait(2))
                self.assertFalse(pool_closed.is_set())
            finally:
                release_run.set(); release_jobs.set(); worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(pool_closed.is_set())
            if use_postgres:
                self.assertTrue(pool.closed)
            self.assertEqual(writes, ['first', 'queued', 'late'])
            with self.assertRaises(RuntimeError):
                queue.submit(write, 'after shutdown')

    def test_postprocessing_can_restart_and_drains_after_a_failed_job(self):
        queue = Postprocessing()
        for _ in range(2):
            queue.start()
            failed = queue.submit(lambda: 1 / 0)
            completed = queue.submit(lambda: 'saved')
            queue.shutdown()
            self.assertIsInstance(failed.exception(), ZeroDivisionError)
            self.assertEqual(completed.result(), 'saved')


if __name__ == '__main__':
    unittest.main()
