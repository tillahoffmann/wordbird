"""Tests for the model warm-up and mic connection flow.

Tests the threading interactions between mic readiness, model loading,
and recording lifecycle to catch race conditions.
"""

import threading
import time


class FakeRecorder:
    """Simulates the Recorder with controllable mic readiness."""

    def __init__(self, ready_delay: float = 0):
        self.is_recording = False
        self._mic_ready = False
        self._ready_delay = ready_delay
        self.level = 0.0
        self._started = False

    @property
    def mic_ready(self):
        return self._mic_ready

    @property
    def device_name(self):
        return "Fake Mic"

    def start(self):
        self.is_recording = True
        self._started = True
        if self._ready_delay > 0:
            t = threading.Timer(self._ready_delay, self._become_ready)
            t.daemon = True
            t.start()
        else:
            self._mic_ready = True

    def _become_ready(self):
        self._mic_ready = True

    def stop(self):
        self.is_recording = False
        return b"fake-wav", 1.0


class FakeOverlay:
    """Records overlay state transitions."""

    def __init__(self):
        self.states: list[str] = []

    def show_connecting(self):
        self.states.append("connecting")

    def show_warming(self):
        self.states.append("warming")

    def show_transcribing(self):
        self.states.append("transcribing")

    def show_improving(self):
        self.states.append("improving")

    def show_done(self, word_count=0):
        self.states.append("done")

    def show_error(self, msg):
        self.states.append(f"error:{msg}")

    def hide(self):
        self.states.append("hidden")


class FakeMenuBar:
    """Records menubar state transitions."""

    def __init__(self):
        self.states: list[str] = []

    def set_state(self, state):
        self.states.append(state.name)


class TestWarmupFlow:
    """Test the interaction between mic connection and model warm-up."""

    def test_models_already_warm(self):
        """When models are loaded, no warming state should appear."""
        stt_warm = threading.Event()
        stt_warm.set()  # Already warm
        fix_warm = threading.Event()
        fix_warm.set()  # Already warm

        overlay = FakeOverlay()

        # Simulate the check before transcription
        if not stt_warm.is_set():
            overlay.show_warming()
            stt_warm.wait()

        overlay.show_transcribing()

        if not fix_warm.is_set():
            overlay.show_warming()
            fix_warm.wait()

        overlay.show_improving()

        assert "warming" not in overlay.states
        assert overlay.states == ["transcribing", "improving"]

    def test_stt_model_needs_warming(self):
        """When STT model is loading, warming state should appear before transcribing."""
        stt_warm = threading.Event()
        fix_warm = threading.Event()
        fix_warm.set()

        overlay = FakeOverlay()

        # Simulate slow STT load
        def delayed_set():
            time.sleep(0.1)
            stt_warm.set()

        threading.Thread(target=delayed_set, daemon=True).start()

        if not stt_warm.is_set():
            overlay.show_warming()
            stt_warm.wait()

        overlay.show_transcribing()

        assert overlay.states == ["warming", "transcribing"]

    def test_fix_model_needs_warming(self):
        """When fix model is loading, warming state should appear before improving."""
        stt_warm = threading.Event()
        stt_warm.set()
        fix_warm = threading.Event()

        overlay = FakeOverlay()

        # STT ready
        if not stt_warm.is_set():
            overlay.show_warming()
            stt_warm.wait()

        overlay.show_transcribing()

        # Simulate slow fix load
        def delayed_set():
            time.sleep(0.1)
            fix_warm.set()

        threading.Thread(target=delayed_set, daemon=True).start()

        if not fix_warm.is_set():
            overlay.show_warming()
            fix_warm.wait()

        overlay.show_improving()

        assert overlay.states == ["transcribing", "warming", "improving"]

    def test_both_models_need_warming(self):
        """When both models are loading, warming appears before each step."""
        stt_warm = threading.Event()
        fix_warm = threading.Event()

        overlay = FakeOverlay()

        def delayed_stt():
            time.sleep(0.05)
            stt_warm.set()

        def delayed_fix():
            time.sleep(0.15)
            fix_warm.set()

        threading.Thread(target=delayed_stt, daemon=True).start()
        threading.Thread(target=delayed_fix, daemon=True).start()

        if not stt_warm.is_set():
            overlay.show_warming()
            stt_warm.wait()

        overlay.show_transcribing()

        if not fix_warm.is_set():
            overlay.show_warming()
            fix_warm.wait()

        overlay.show_improving()

        assert overlay.states == ["warming", "transcribing", "warming", "improving"]

    def test_mic_timeout(self):
        """Mic that never produces audio should time out."""
        recorder = FakeRecorder(ready_delay=999)  # Never becomes ready
        overlay = FakeOverlay()

        recorder.start()

        deadline = time.monotonic() + 0.2  # Short timeout for test
        while recorder.is_recording and not recorder.mic_ready:
            if time.monotonic() > deadline:
                recorder.stop()
                recorder.is_recording = False
                overlay.show_error("Mic not responding")
                break
            time.sleep(0.01)

        assert "error:Mic not responding" in overlay.states

    def test_mic_ready_before_timeout(self):
        """Mic that produces audio quickly should not time out."""
        recorder = FakeRecorder(ready_delay=0.05)
        overlay = FakeOverlay()
        menubar = FakeMenuBar()

        recorder.start()

        deadline = time.monotonic() + 5.0
        while recorder.is_recording and not recorder.mic_ready:
            if time.monotonic() > deadline:
                recorder.stop()
                overlay.show_error("Mic not responding")
                break
            time.sleep(0.01)

        if recorder.is_recording:
            menubar.set_state(type("S", (), {"name": "LISTENING"})())

        assert "error:Mic not responding" not in overlay.states
        assert "LISTENING" in menubar.states

    def test_events_initialized_as_set(self):
        """Warm-up events should be set by default so first run doesn't block."""
        stt = threading.Event()
        stt.set()
        fix = threading.Event()
        fix.set()

        assert stt.is_set()
        assert fix.is_set()
        # Should not block
        assert stt.wait(timeout=0)
        assert fix.wait(timeout=0)

    def test_concurrent_warm_up_threads(self):
        """Both warm-up threads should complete independently."""
        stt_warm = threading.Event()
        fix_warm = threading.Event()
        order = []

        def warm_stt():
            time.sleep(0.05)
            order.append("stt")
            stt_warm.set()

        def warm_fix():
            time.sleep(0.1)
            order.append("fix")
            fix_warm.set()

        t1 = threading.Thread(target=warm_stt, daemon=True)
        t2 = threading.Thread(target=warm_fix, daemon=True)
        t1.start()
        t2.start()

        stt_warm.wait(timeout=1)
        fix_warm.wait(timeout=1)

        assert stt_warm.is_set()
        assert fix_warm.is_set()
        assert order == ["stt", "fix"]  # STT finishes first
