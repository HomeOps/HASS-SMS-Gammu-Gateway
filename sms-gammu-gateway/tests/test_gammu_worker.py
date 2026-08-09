"""Tests for GammuWorkerProxy.

The integration tests drive gammu's dummy phone, so they need no modem and run in
CI. The dummy phone never stalls, so the timeout path is covered separately with a
stub worker that can be made slow on demand.
"""

import asyncio
import queue
import threading
import time

import gammu
import pytest

from gammu_worker import GammuWorkerProxy, _ExceptionPreservingThread, _Worker
from support import retrieveAllSms


class _RecordingStateMachine:
    """Minimal StateMachine stand-in that records which commands were executed."""

    def __init__(self):
        self.calls = []

    def GetIMEI(self):  # noqa: N802 - mirrors the gammu API
        self.calls.append("GetIMEI")
        return "IMEI"


class _StubWorker:
    """Stand-in for GammuAsyncWorker: one thread, one command at a time.

    Records what it executed and in which order, which is how the tests assert that
    a timed out command is neither cancelled nor overlapped by the next one.
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="stub-worker")
        self._thread.start()
        self.delays = {}
        self.completed = []
        self.config = None
        # Commands that block until release is set, standing in for a modem that
        # never answers and a libGammu call that therefore never returns.
        self.hangs = set()
        self.release = threading.Event()

    def configure(self, config):
        self.config = config

    async def init_async(self):
        return None

    def enqueue(self, future, commands=None):
        self._queue.put((future, commands[0][0]))

    async def terminate_async(self):
        self._queue.put(None)

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            future, name = item
            if name in self.hangs:
                self.release.wait()
            # Mirrors _ExceptionPreservingThread: abandoned commands are dropped
            # before they reach the modem, and a result is never forced onto a
            # future the caller has given up on.
            if future.cancelled():
                continue
            time.sleep(self.delays.get(name, 0))
            self.completed.append(name)
            self._loop.call_soon_threadsafe(self._deliver, future, name)

    @staticmethod
    def _deliver(future, name):
        if not future.done():
            future.set_result(name)


def _stub_factory(created):
    def factory():
        worker = _StubWorker()
        created.append(worker)
        return worker

    return factory


@pytest.mark.integration
class TestAgainstDummyPhone:
    def test_command_reaches_the_state_machine(self, dummy_worker):
        status = dummy_worker.GetSMSStatus()
        assert status["SIMUsed"] == 0
        assert status["PhoneUsed"] == 0

    def test_positional_argument_is_forwarded(self, dummy_worker, smsc):
        dummy_worker.AddSMS(
            {
                "Folder": 1,
                "State": "UnRead",
                "Number": "+15555550100",
                "SMSC": smsc,
                "Text": "through the worker",
                "Class": -1,
            }
        )
        # Folder 1 is SIM storage on the dummy backend, so count both rather than
        # pinning the test to that mapping.
        status = dummy_worker.GetSMSStatus()
        assert status["SIMUsed"] + status["PhoneUsed"] == 1

    def test_existing_helpers_work_unchanged(self, dummy_worker, smsc):
        """support.retrieveAllSms drives the proxy exactly as it drove a StateMachine."""
        dummy_worker.AddSMS(
            {
                "Folder": 1,
                "State": "UnRead",
                "Number": "+15555550100",
                "SMSC": smsc,
                "Text": "stored message",
                "Class": -1,
            }
        )
        messages = retrieveAllSms(dummy_worker)
        assert len(messages) == 1
        assert messages[0]["Number"] == "+15555550100"

    def test_gammu_error_subclass_survives_the_worker(self, dummy_worker, dummy_phone):
        """GammuAsyncWorker downgrades GSMError subclasses; the proxy must not.

        support.py catches gammu.ERR_NOSIM and gammu.ERR_NOTSUPPORTED by class, so a
        generic GSMError would silently stop matching.
        """
        with pytest.raises(gammu.GSMError) as direct:
            dummy_phone.GetNextSMS(Start=True, Folder=0)

        with pytest.raises(type(direct.value)) as through_worker:
            dummy_worker.GetNextSMS(Start=True, Folder=0)

        assert type(through_worker.value) is type(direct.value)

    def test_concurrent_callers_all_succeed(self, dummy_worker):
        """The property the old executor-per-call design could not provide.

        Eight threads, no application lock: every command still lands on the single
        worker thread, so none of them corrupts another's exchange.
        """
        errors = []

        def hammer():
            try:
                for _ in range(10):
                    dummy_worker.GetSMSStatus()
            except Exception as exc:  # noqa: BLE001 - reported through the list
                errors.append(exc)

        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert errors == []
        assert not any(thread.is_alive() for thread in threads)

    def test_rejects_positional_and_keyword_together(self, dummy_worker):
        """gammu's _execute_command can pass one or the other, never both."""
        with pytest.raises(TypeError):
            dummy_worker.GetNextSMS(True, Folder=0)


class TestTimeoutHandling:
    def test_timeout_neither_cancels_nor_overlaps(self):
        created = []
        proxy = GammuWorkerProxy({}, timeout=0.05, worker_factory=_stub_factory(created))
        worker = created[0]
        worker.delays["Slow"] = 0.3

        try:
            with pytest.raises(TimeoutError):
                proxy.Slow()

            # Giving up on the result does not stop the command: libGammu cannot be
            # interrupted, so the worker runs it to completion.
            assert worker.completed == []
            time.sleep(0.45)
            assert worker.completed == ["Slow"]

            # And the next command ran after it rather than alongside it, which is
            # what the discarded ThreadPoolExecutor could not guarantee.
            assert proxy.Fast() == "Fast"
            assert worker.completed == ["Slow", "Fast"]
        finally:
            proxy.terminate()

    def test_abandoned_command_is_dropped_before_execution(self):
        """A cancelled future means nobody is waiting; the modem should not be driven.

        Without this, a 29s stall leaves a backlog of ReadDevice ticks that replay in
        a burst the moment the worker frees up.
        """
        thread = object.__new__(_ExceptionPreservingThread)
        thread._sm = _RecordingStateMachine()
        callbacks = []
        thread._callback = lambda *args: callbacks.append(args)

        future = asyncio.new_event_loop().create_future()
        future.cancel()
        thread._do_command(future, "GetIMEI", ())

        assert thread._sm.calls == []
        assert callbacks == []

    def test_live_command_still_executes(self):
        """The guard must not swallow commands somebody is still waiting for."""
        thread = object.__new__(_ExceptionPreservingThread)
        thread._sm = _RecordingStateMachine()
        callbacks = []
        thread._callback = lambda *args: callbacks.append(args)

        future = asyncio.new_event_loop().create_future()
        thread._do_command(future, "GetIMEI", ())

        assert thread._sm.calls == ["GetIMEI"]
        assert callbacks == [(future, "IMEI", None, 100)]

    def test_repeated_stalls_trigger_recovery(self):
        """A worker that never returns cannot be cleared from inside the process."""
        created = []
        stalls = []
        proxy = GammuWorkerProxy(
            {},
            timeout=0.05,
            worker_factory=_stub_factory(created),
            stall_limit=2,
            on_stall=stalls.append,
        )
        created[0].delays["Slow"] = 0.3

        try:
            for _ in range(2):
                with pytest.raises(TimeoutError):
                    proxy.Slow()
            assert stalls == [2]
        finally:
            time.sleep(0.45)
            proxy.terminate()

    def test_a_success_clears_the_stall_count(self):
        created = []
        stalls = []
        proxy = GammuWorkerProxy(
            {},
            timeout=0.05,
            worker_factory=_stub_factory(created),
            stall_limit=2,
            on_stall=stalls.append,
        )
        worker = created[0]
        worker.delays["Slow"] = 0.3

        try:
            with pytest.raises(TimeoutError):
                proxy.Slow()
            time.sleep(0.45)

            assert proxy.Fast() == "Fast"
            assert proxy._timeouts == 0

            # A later isolated stall must start counting again rather than tripping
            # the limit on its own.
            with pytest.raises(TimeoutError):
                proxy.Slow()
            assert stalls == []
        finally:
            time.sleep(0.45)
            proxy.terminate()

    def test_a_modem_that_never_answers_trips_the_watchdog(self):
        """The failure libGammu cannot bound: a call that never returns.

        The prompt bug ends after 29s with TIMEOUT[14] and the queue drains. A modem
        that stops answering entirely leaves the worker inside libGammu forever, and
        every later command — including the soft reset that would recover it — waits
        behind a call that can never be interrupted from Python. Restarting is the
        only remaining move, so the watchdog has to reach it.
        """
        created = []
        stalls = []
        proxy = GammuWorkerProxy(
            {},
            timeout=0.05,
            worker_factory=_stub_factory(created),
            stall_limit=3,
            on_stall=stalls.append,
        )
        worker = created[0]
        worker.hangs.add("SendSMS")

        try:
            with pytest.raises(TimeoutError):
                proxy.SendSMS({})
            assert stalls == []

            # Recovery attempts queue behind the hung call and time out in turn.
            with pytest.raises(TimeoutError):
                proxy.GetSMSStatus()
            with pytest.raises(TimeoutError):
                proxy.Reset(False)

            # Third consecutive timeout: the process gives up so the Supervisor can
            # restart the add-on. In production on_stall is restart_process.
            assert stalls == [3]

            # Nothing else touched the modem while it was hung.
            assert worker.completed == []
        finally:
            worker.release.set()
            proxy.terminate()

    def test_late_result_for_an_abandoned_command_is_not_an_error(self):
        """The other half of a timeout: the command that was already running.

        It cannot be stopped, so it completes and reports a result for a future
        nobody holds. Setting it would raise InvalidStateError inside the event
        loop on every single timeout.
        """

        async def scenario():
            loop = asyncio.get_running_loop()
            failures = []
            loop.set_exception_handler(lambda _loop, context: failures.append(context))

            worker = _Worker()
            future = loop.create_future()
            future.cancel()

            worker.worker_callback(future, "late result", None, 100)
            await asyncio.sleep(0)

            assert failures == []
            assert future.cancelled()

        asyncio.run(scenario())

    def test_configuration_reaches_the_worker(self):
        created = []
        proxy = GammuWorkerProxy(
            {"Device": "/dev/null", "Connection": "at115200"},
            worker_factory=_stub_factory(created),
        )
        try:
            assert created[0].config == {"Device": "/dev/null", "Connection": "at115200"}
        finally:
            proxy.terminate()
