import threading
import unittest
from unittest.mock import patch

from midi_to_keyboard import _PlaybackClock
from ui.actions.playback_actions import (
    NUMPAD_MINUS_SCAN_CODE,
    NUMPAD_PLUS_SCAN_CODE,
    UiPlaybackActionsMixin,
)


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.on_sleep = None

    def perf_counter(self):
        return self.now

    def sleep(self, duration):
        self.now += duration
        if self.on_sleep is not None:
            self.on_sleep()


class PlaybackClockTests(unittest.TestCase):
    def test_speed_change_applies_during_current_wait(self):
        fake_time = FakeTime()
        speed = lambda: 1.0 if fake_time.now <= 0.1 else 3.0
        with patch("midi_to_keyboard.time.perf_counter", fake_time.perf_counter), patch(
            "midi_to_keyboard.time.sleep", fake_time.sleep
        ):
            clock = _PlaybackClock(speed)
            self.assertTrue(clock.wait_until(0.3))

        self.assertAlmostEqual(fake_time.now, 1 / 6, places=6)

    def test_pause_does_not_advance_schedule_time(self):
        fake_time = FakeTime()
        pause_event = threading.Event()
        pause_event.set()
        fake_time.on_sleep = lambda: pause_event.clear() if fake_time.now >= 0.2 else None
        pauses = []
        with patch("midi_to_keyboard.time.perf_counter", fake_time.perf_counter), patch(
            "midi_to_keyboard.time.sleep", fake_time.sleep
        ):
            clock = _PlaybackClock()
            self.assertTrue(
                clock.wait_until(0.1, pause_event=pause_event, on_pause=lambda: pauses.append(1))
            )

        self.assertAlmostEqual(fake_time.now, 0.3, places=6)
        self.assertEqual(pauses, [1])


class PlaybackHotkeyTests(unittest.TestCase):
    def test_numpad_scan_codes_are_registered_separately(self):
        app = type("PlaybackApp", (UiPlaybackActionsMixin,), {})()
        app.stop_hotkey = None
        app.pause_hotkey = None
        app.speed_hotkeys = []
        app.stop_keyboard_playback = lambda: None
        app.toggle_keyboard_playback_pause = lambda: None
        app.adjust_playback_speed = lambda _delta: None

        with patch(
            "ui.actions.playback_actions.keyboard.add_hotkey",
            side_effect=["f8", "f6", "numpad+", "numpad-", "ctrl+", "ctrl-"],
        ) as add_hotkey:
            app.register_stop_hotkey()

        registered = [call.args[0] for call in add_hotkey.call_args_list]
        self.assertEqual(
            registered[2:4], [NUMPAD_PLUS_SCAN_CODE, NUMPAD_MINUS_SCAN_CODE]
        )


if __name__ == "__main__":
    unittest.main()
