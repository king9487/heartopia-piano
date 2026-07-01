import queue
import threading
import tkinter as tk

from tools import default_demucs_device


def initialize_app_state(app):
    """Create Tk variables and mutable UI state for YoutubeMidiApp."""
    app.queue = queue.Queue()
    app.results = None
    app.converting = False
    app.convert_cancel_token = None
    app.playing = False
    app.stop_event = threading.Event()
    app.stop_hotkey = None

    app.url_var = tk.StringVar()
    app.always_top_var = tk.BooleanVar(value=True)
    app.midi_choice_var = tk.StringVar(value="accompaniment_midi")
    app.midi_source_var = tk.StringVar()
    app.available_midi_sources = {}
    app.convert_vocals_midi_var = tk.BooleanVar(value=False)
    app.selected_midi_var = tk.StringVar()
    app.cached_choice_var = tk.StringVar()
    app.cached_outputs = []
    app.demucs_device_var = tk.StringVar(value=default_demucs_device() or "auto")
    app.speed_var = tk.DoubleVar(value=1.0)
    app.countdown_var = tk.IntVar(value=3)
    app.transpose_var = tk.IntVar(value=0)
    app.chord_delay_var = tk.IntVar(value=18)
    app.min_hold_var = tk.IntVar(value=75)
    app.min_note_duration_var = tk.IntVar(value=35)
    app.velocity_threshold_var = tk.IntVar(value=12)
    app.max_simultaneous_var = tk.IntVar(value=0)
    app.octave_fit_var = tk.StringVar(value="smart")
    app.melody_only_var = tk.BooleanVar(value=False)
    app.melody_max_notes_var = tk.IntVar(value=3)
    app.melody_window_var = tk.IntVar(value=80)
    app.optimizer_mode_var = tk.StringVar(value="Piano Cover")
    app.original_key_var = tk.StringVar(value="Auto Detect")
    app.target_key_var = tk.StringVar(value="Original")
    app.detected_key_var = tk.StringVar(value="Detected Key: --")
    app.key_transpose_status_var = tk.StringVar(value="Transpose: 0 semitones")
    app.range_start_var = tk.DoubleVar(value=0.0)
    app.range_end_var = tk.DoubleVar(value=30.0)
    app.status_var = tk.StringVar(value="Ready")
    app.studio_position_var = tk.DoubleVar(value=0.0)
    app.studio_current_time_var = tk.StringVar(value="00:00.000")
    app.studio_total_time_var = tk.StringVar(value="00:00.000")
    app.studio_status_var = tk.StringVar(value="No MIDI loaded")

    app.studio_loaded_path = None
    app.studio_events = []
    app.studio_event_times = []
    app.studio_event_index = 0
    app.studio_total_duration = 0.0
    app.studio_position = 0.0
    app.studio_started_at = 0.0
    app.studio_state = "stopped"
    app.studio_output = None
    app.studio_after_id = None
    app.studio_updating_slider = False
    app.editor_source_path = None
    app.editor_notes = []
    app.editor_suspicious_reasons = {}

    # Widgets are populated by the panel builders.
    app.notebook = None
    app.main_tab = None
    app.playback_tab = None
    app.cleanup_tab = None
    app.studio_tab = None
    app.log = None
    app.convert_button = None
    app.local_audio_button = None
    app.stop_button = None
    app.play_button = None
    app.midi_source_combo = None
    app.cached_combo = None
    app.studio_seek = None
    app.studio_play_button = None
    app.studio_pause_button = None
    app.studio_stop_button = None
    app.editor_tree = None
    app.studio_canvas = None
