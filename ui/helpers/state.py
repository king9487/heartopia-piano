import queue
import threading
import tkinter as tk

from midi_analysis import ANALYSIS_FIELDS
from keyboard_profiles import DEFAULT_KEYBOARD_PROFILE
from keyboard_mapping import DEFAULT_MAPPING_PROFILE, load_mapping_profiles
from tools import default_demucs_device
from converter import DEFAULT_SEPARATION_MODE, DEFAULT_SEPARATION_STEM


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
    app.workflow_var = tk.StringVar(value="studio_mode")
    app.input_source_var = tk.StringVar(value="youtube")
    app.external_midi_path_var = tk.StringVar()
    app.skip_cleanup_var = tk.BooleanVar(value=False)
    app.skip_piano_arranger_var = tk.BooleanVar(value=False)
    app.skip_ai_optimizer_var = tk.BooleanVar(value=False)
    app.skip_pitch_correction_var = tk.BooleanVar(value=False)
    app.direct_preview_var = tk.BooleanVar(value=False)
    app.external_part_range_mode_var = tk.StringVar(value="keep")
    app.external_part_warning_var = tk.StringVar(value="")
    app.external_part_selections = {}
    app.external_part_tree_items = {}
    app.selected_direct_temp_dir = None
    app.selected_direct_midi_path = None
    app.selected_direct_midi_stats = None
    app.external_midi_info_vars = {
        key: tk.StringVar(value="--")
        for key in (
            "file_name", "duration", "bpm", "key", "ppq", "tracks",
            "total_notes", "notes_inside_map", "notes_outside_map",
            "playable_percentage", "recommended",
        )
    }
    app.always_top_var = tk.BooleanVar(value=True)
    app.midi_choice_var = tk.StringVar(value="accompaniment_midi")
    app.midi_source_var = tk.StringVar()
    app.available_midi_sources = {}
    app.compare_a_source_var = tk.StringVar()
    app.compare_b_source_var = tk.StringVar()
    app.available_compare_sources = {}
    app.convert_vocals_midi_var = tk.BooleanVar(value=False)
    app.selected_midi_var = tk.StringVar()
    app.cached_choice_var = tk.StringVar()
    app.cached_outputs = []
    app.demucs_device_var = tk.StringVar(value=default_demucs_device() or "auto")
    app.separation_mode_var = tk.StringVar(value=DEFAULT_SEPARATION_MODE)
    app.stem_to_convert_var = tk.StringVar(value=DEFAULT_SEPARATION_STEM)
    app.speed_var = tk.DoubleVar(value=1.0)
    app.countdown_var = tk.IntVar(value=3)
    app.transpose_var = tk.IntVar(value=0)
    app.chord_delay_var = tk.IntVar(value=18)
    app.min_hold_var = tk.IntVar(value=75)
    app.keyboard_profile_var = tk.StringVar(value=DEFAULT_KEYBOARD_PROFILE)
    app.mapping_profile_var = tk.StringVar(value=DEFAULT_MAPPING_PROFILE)
    app.active_mapping_profile_var = tk.StringVar(value=DEFAULT_MAPPING_PROFILE)
    app.keyboard_mapping_profiles = load_mapping_profiles()
    app.processing_preset_var = tk.StringVar(value="Balanced")
    app.min_note_duration_var = tk.IntVar(value=35)
    app.velocity_threshold_var = tk.IntVar(value=12)
    app.max_simultaneous_var = tk.IntVar(value=0)
    app.octave_fit_var = tk.StringVar(value="smart")
    app.melody_only_var = tk.BooleanVar(value=False)
    app.melody_max_notes_var = tk.IntVar(value=3)
    app.melody_window_var = tk.IntVar(value=80)
    app.arrangement_style_var = tk.StringVar(value="piano_cover")
    app.optimizer_mode_var = tk.StringVar(value="Rule")
    app.original_key_var = tk.StringVar(value="Auto Detect")
    app.target_key_var = tk.StringVar(value="Original")
    app.detected_key_var = tk.StringVar(value="Detected Key: --")
    app.key_transpose_status_var = tk.StringVar(value="Transpose: 0 semitones")
    app.range_start_var = tk.DoubleVar(value=0.0)
    app.range_end_var = tk.DoubleVar(value=30.0)
    app.status_var = tk.StringVar(value="Ready")
    app.analysis_vars = {
        field: tk.StringVar(value="--") for field in ANALYSIS_FIELDS
    }
    app.analysis_vars["Keyboard Profile"].set("Heartopia (C3-C6)")
    app.analysis_vars["Mapping Profile"].set(DEFAULT_MAPPING_PROFILE)
    app.studio_position_var = tk.DoubleVar(value=0.0)
    app.studio_current_time_var = tk.StringVar(value="00:00.000")
    app.studio_total_time_var = tk.StringVar(value="00:00.000")
    app.studio_status_var = tk.StringVar(value="No MIDI loaded")
    app.studio_view_mode_var = tk.StringVar(value="Piano Roll")
    app.staff_selected_note_var = tk.StringVar(value="No staff note selected")

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
    app.import_tab = None
    app.optimization_tab = None
    app.playback_tab = None
    app.cleanup_tab = None
    app.studio_tab = None
    app.analysis_tab = None
    app.keyboard_mapping_tab = None
    app.log = None
    app.convert_button = None
    app.local_audio_button = None
    app.external_midi_button = None
    app.process_external_midi_button = None
    app.preview_original_midi_button = None
    app.play_original_midi_button = None
    app.open_original_midi_button = None
    app.external_midi_track_tree = None
    app.external_midi_channel_tree = None
    app.youtube_input_frame = None
    app.local_audio_input_frame = None
    app.external_midi_input_frame = None
    app.stop_button = None
    app.play_button = None
    app.midi_source_combo = None
    app.mapping_profile_combo = None
    app.playback_mapping_profile_combo = None
    app.keyboard_mapping_tree = None
    app.compare_a_combo = None
    app.compare_b_combo = None
    app.cached_combo = None
    app.studio_seek = None
    app.studio_play_button = None
    app.studio_pause_button = None
    app.studio_stop_button = None
    app.editor_tree = None
    app.studio_canvas = None
    app.timeline_renderer = None
    app.piano_roll_frame = None
    app.staff_view_frame = None
    app.staff_view = None
    app.input_source_choices = None
    app.conversion_options_frame = None
    app.open_midi_button = None
    app.open_converted_button = None
    app.preview_button = None
    app.main_log_frame = None
    app.main_log_source_frame = None
    app.main_status_frame = None
    app.import_actions_frame = None
    app.import_analysis_frame = None
    app.import_selection_frame = None
    app.import_optimizer_frame = None
    app.playback_sources_frame = None
    app.playback_compare_frame = None
    app.playback_advanced_settings = ()
    app.workflow_manager = None
