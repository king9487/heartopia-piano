import os
import tempfile
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

from converter import (
    audio_file_to_midi,
    import_external_midi,
    write_selected_parts_midi,
    youtube_to_midi,
)
from keyboard_profiles import processing_options_for_profile
from midi_analysis import inspect_midi_file
from tools import (
    CancellationToken,
    CancelledError,
    check_cli_dependencies,
    format_command_error,
)


class UiConvertActionsMixin:
    """UI callbacks and background work for URL/local-audio conversion."""

    def on_input_source_changed(self):
        frames = {
            "youtube": self.youtube_input_frame,
            "local_audio": self.local_audio_input_frame,
            "external_midi": self.external_midi_input_frame,
        }
        selected = self.input_source_var.get()
        if (
            getattr(self, "workflow_var", None) is not None
            and self.workflow_var.get() == "quick_play"
        ):
            selected = "external_midi"
        for name, frame in frames.items():
            if frame is not None:
                (frame.grid if name == selected else frame.grid_remove)()

    def _begin_conversion(self, status, log_message, preserve_sources=False):
        assert self.convert_button is not None
        self.convert_button.configure(state="disabled")
        assert self.local_audio_button is not None
        self.local_audio_button.configure(state="disabled")
        if self.external_midi_button is not None:
            self.external_midi_button.configure(state="disabled")
        if self.process_external_midi_button is not None:
            self.process_external_midi_button.configure(state="disabled")
        assert self.stop_button is not None
        self.stop_button.configure(state="normal")
        if not preserve_sources:
            self.results = None
            self.clear_midi_source_options()
        self.converting = True
        self.convert_cancel_token = CancellationToken()
        self.status_var.set(status)
        self.log_message(log_message)

    def start_convert(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a YouTube URL first.")
            return

        options = processing_options_for_profile(self.keyboard_profile_var.get())
        self._begin_conversion("Checking dependencies", "Starting conversion...")
        self.log_message(f"Keyboard profile: {options['keyboard_profile']}")
        separation_mode = self.separation_mode_var.get()
        stem_to_convert = self.stem_to_convert_var.get()
        self.log_message(f"Separation mode: {separation_mode}")
        self.log_message(f"Stem to convert: {stem_to_convert}")

        thread = threading.Thread(
            target=self.convert_worker,
            args=(url, options, separation_mode, stem_to_convert),
            daemon=True,
        )
        thread.start()

    def start_local_audio_convert(self):
        filename = filedialog.askopenfilename(
            title="Open local audio file",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg *.webm *.aac"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        options = processing_options_for_profile(self.keyboard_profile_var.get())
        self._begin_conversion(
            "Checking dependencies", f"Starting local audio conversion: {filename}"
        )
        self.log_message(f"Keyboard profile: {options['keyboard_profile']}")
        separation_mode = self.separation_mode_var.get()
        stem_to_convert = self.stem_to_convert_var.get()
        self.log_message(f"Separation mode: {separation_mode}")
        self.log_message(f"Stem to convert: {stem_to_convert}")

        thread = threading.Thread(
            target=self.local_audio_convert_worker,
            args=(filename, options, separation_mode, stem_to_convert),
            daemon=True,
        )
        thread.start()

    def browse_external_midi(self):
        filename = filedialog.askopenfilename(
            title="Import external MIDI",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if not filename:
            return
        for variable in self.external_midi_info_vars.values():
            variable.set("--")
        self.clear_external_midi_analysis()
        try:
            metadata = inspect_midi_file(filename)
        except Exception as exc:
            self.external_midi_path_var.set("")
            self.results = None
            self.clear_midi_source_options()
            for button in (
                self.process_external_midi_button,
                self.preview_original_midi_button,
                self.play_original_midi_button,
                self.open_original_midi_button,
            ):
                if button is not None:
                    button.configure(state="disabled")
            messagebox.showerror("Invalid MIDI", str(exc))
            return
        self.results = None
        self.clear_midi_source_options()
        self.external_part_selections = {}
        self.external_midi_path_var.set(filename)
        self.show_external_midi_metadata(metadata)
        self.results = {
            "input_source": "external_midi",
            "source_midi": Path(filename),
            "imported_midi": Path(filename),
        }
        self.create_selected_direct_midi()
        self.update_selected_midi()
        for button in (
            self.process_external_midi_button,
            self.preview_original_midi_button,
            self.play_original_midi_button,
            self.open_original_midi_button,
        ):
            if button is not None:
                button.configure(state="normal")
        self.status_var.set("Imported MIDI selected")
        self.log_message(f"Imported MIDI ready for direct playback: {filename}")

    def show_external_midi_metadata(self, metadata):
        self.external_midi_metadata = metadata
        parts = metadata.get("musical_parts", ())
        part_keys = {
            (part["track_index"], part["channel"]) for part in parts
        }
        selections = getattr(self, "external_part_selections", {})
        if set(selections) != part_keys:
            selections = {}
            for part in parts:
                key = (part["track_index"], part["channel"])
                recommended = (
                    part["notes"] > 0 and part["playable_percentage"] >= 80.0
                )
                selections[key] = {
                    "direct": recommended,
                    "optimize": recommended,
                }
            self.external_part_selections = selections
        risky_parts = [
            part for part in parts
            if part["notes"]
            and part["out_of_range_notes"] / part["notes"] >= 0.20
        ]
        warning_var = getattr(self, "external_part_warning_var", None)
        if warning_var is not None:
            if risky_parts:
                labels = ", ".join(
                    f"T{part['track_index']}/Ch{part['channel']} "
                    f"({part['out_of_range_notes']}/{part['notes']} out of range)"
                    for part in risky_parts
                )
                warning_var.set(f"Warning: many out-of-range notes in {labels}")
            else:
                warning_var.set("")
        source_path = metadata.get("source_path")
        if source_path:
            self.log_message(f"Original MIDI source: {source_path}")
        source_tracks = metadata.get("notes_per_track", ())
        self.log_message(f"Original MIDI track count: {len(source_tracks)}")
        for track in source_tracks:
            track_index = track.get("track_index", track["track_number"] - 1)
            self.log_message(
                f"Track {track_index} note count: {track['notes']}"
            )
            self.log_message(
                f"Track {track_index} name: {track.get('name') or '(unnamed)'}"
            )
            for part in track.get("channel_programs", ()):
                note_range = (
                    f"{part['min_note']}..{part['max_note']}"
                    if part["min_note"] is not None else "--"
                )
                default_label = "" if part.get("program_explicit") else " (default)"
                self.log_message(
                    f"Track {track_index} channel {part['channel']} "
                    f"(MIDI {part['display_channel']}), program {part['program']} "
                    f"{part['instrument']}{default_label}: notes {part['notes']}, "
                    f"playable {part['playable_notes']}, "
                    f"out of range {part['out_of_range_notes']}, range {note_range}"
                )
            for event in track.get("program_change_events", ()):
                self.log_message(
                    f"Track {track_index} program_change at tick {event['tick']}: "
                    f"channel {event['channel']} (MIDI {event['display_channel']}), "
                    f"program {event['program']} {event['instrument']}"
                )

        total_notes = metadata["total_notes"]
        playable_notes = metadata["notes_inside_map"]
        playable_percentage = (
            (playable_notes / total_notes) * 100 if total_notes else 0.0
        )
        if playable_percentage > 90:
            recommended = "Direct Play"
        elif playable_percentage < 80:
            recommended = "Optimize for Heartopia"
        else:
            recommended = "Either workflow"
        display = {
            "file_name": metadata["file_name"],
            "duration": f"{metadata['duration']:.3f} s",
            "bpm": (
                f"{metadata['bpm']:g} BPM"
                if metadata["bpm"] is not None
                else "Not available"
            ),
            "key": metadata["key"] or "Unknown",
            "ppq": metadata["ppq"],
            "tracks": metadata["tracks"],
            "total_notes": metadata["total_notes"],
            "notes_inside_map": (
                f"{playable_notes} / {total_notes} ({playable_percentage:.1f}%)"
            ),
            "notes_outside_map": metadata["notes_outside_map"],
            "playable_percentage": f"{playable_percentage:.1f}%",
            "recommended": recommended,
        }
        for key, value in display.items():
            self.external_midi_info_vars[key].set(str(value))
        track_tree = getattr(self, "external_midi_track_tree", None)
        if track_tree is not None:
            self.external_part_tree_items = {}
            for item in track_tree.get_children():
                track_tree.delete(item)
            for track in source_tracks:
                track_index = track.get("track_index", track["track_number"] - 1)
                event_flags = []
                if track.get("has_tempo_or_meta_events"):
                    event_flags.append("Tempo/Meta")
                if track.get("has_control_changes"):
                    event_flags.append("Control")
                if track.get("has_program_changes"):
                    event_flags.append("Program")
                parent = track_tree.insert(
                    "",
                    "end",
                    text=(
                        f"Track {track_index}"
                        + (f" — {track['name']}" if track.get("name") else "")
                    ),
                    open=True,
                    values=(
                        "",
                        "",
                        f"{track.get('channel_count', 0)} channel(s)",
                        track["notes"],
                        track["playable_notes"],
                        track["out_of_range_notes"],
                        track.get("min_note") if track.get("min_note") is not None else "--",
                        track.get("max_note") if track.get("max_note") is not None else "--",
                        ", ".join(event_flags) or "--",
                    ),
                )
                for part in track.get("channel_parts", ()):
                    key = (track_index, part["channel"])
                    selection = selections.get(
                        key, {"direct": False, "optimize": False}
                    )
                    item = track_tree.insert(
                        parent,
                        "end",
                        text=(
                            f"Channel {part['channel']} "
                            f"(MIDI {part['display_channel']})"
                        ),
                        values=(
                            "☑" if selection["direct"] else "☐",
                            "☑" if selection["optimize"] else "☐",
                            part["instrument"] or "--",
                            part["notes"],
                            part["playable_notes"],
                            part["out_of_range_notes"],
                            part["min_note"] if part["min_note"] is not None else "--",
                            part["max_note"] if part["max_note"] is not None else "--",
                            "--",
                        ),
                    )
                    self.external_part_tree_items[str(item)] = key
        channel_tree = getattr(self, "external_midi_channel_tree", None)
        if channel_tree is not None:
            for item in channel_tree.get_children():
                channel_tree.delete(item)
            for channel in metadata.get("notes_per_channel", ()):
                channel_tree.insert(
                    "",
                    "end",
                    values=(
                        f"MIDI {channel['channel']} (file {channel['channel'] - 1})",
                        channel["notes"],
                    ),
                )

    def on_external_part_tree_click(self, event):
        tree = getattr(self, "external_midi_track_tree", None)
        if tree is None or tree.identify("region", event.x, event.y) != "cell":
            return None
        column = tree.identify_column(event.x)
        if column not in ("#1", "#2"):
            return None
        item = tree.identify_row(event.y)
        key = getattr(self, "external_part_tree_items", {}).get(str(item))
        if key is None:
            return None
        purpose = "direct" if column == "#1" else "optimize"
        selected = not self.external_part_selections[key][purpose]
        self.external_part_selections[key][purpose] = selected
        if purpose == "direct":
            self.on_external_direct_selection_changed()
        tree.set(item, purpose, "☑" if selected else "☐")
        return "break"

    def on_external_direct_selection_changed(self):
        """Rebuild the temporary direct-play MIDI after a selection change."""
        self.create_selected_direct_midi()
        if self.results is not None:
            self.update_selected_midi()

    def create_selected_direct_midi(self):
        source = self.get_imported_original_midi(show_error=False)
        selected_parts = self.get_selected_external_parts("direct")
        if not source or not selected_parts:
            self.selected_direct_midi_path = None
            self.selected_direct_midi_stats = None
            if self.results:
                self.results["selected_direct_midi"] = None
                self.results["selected_direct_midi_stats"] = None
            return None

        temp_dir = getattr(self, "selected_direct_temp_dir", None)
        if temp_dir is None:
            temp_dir = tempfile.TemporaryDirectory(
                prefix="heartopia_selected_direct_"
            )
            self.selected_direct_temp_dir = temp_dir
        output_path = Path(temp_dir.name) / "selected_direct.mid"
        write_selected_parts_midi(
            source,
            output_path,
            selected_parts=selected_parts,
            range_mode=self.external_part_range_mode_var.get(),
        )
        metadata = inspect_midi_file(output_path)
        stats = {
            "tracks": len({track for track, _channel in selected_parts}),
            "channels": len({channel for _track, channel in selected_parts}),
            "notes": metadata["total_notes"],
        }
        self.selected_direct_midi_path = output_path
        self.selected_direct_midi_stats = stats
        if self.results is not None:
            self.results["selected_direct_midi"] = output_path
            self.results["selected_direct_midi_stats"] = stats
        self.log_message("Selected Direct MIDI created")
        self.log_message(f"Tracks kept: {stats['tracks']}")
        self.log_message(f"Channels kept: {stats['channels']}")
        self.log_message(f"Notes kept: {stats['notes']}")
        return output_path

    def get_selected_external_parts(self, purpose):
        return {
            key for key, selection in self.external_part_selections.items()
            if selection.get(purpose)
        }

    def clear_external_midi_analysis(self):
        for attribute in ("external_midi_track_tree", "external_midi_channel_tree"):
            tree = getattr(self, attribute, None)
            if tree is not None:
                for item in tree.get_children():
                    tree.delete(item)

    def get_imported_original_midi(self, show_error=True):
        filename = self.external_midi_path_var.get().strip()
        midi_path = Path(filename) if filename else None
        if not midi_path or not midi_path.is_file():
            if show_error:
                messagebox.showerror(
                    "Imported MIDI not found", filename or "No MIDI selected"
                )
            return None
        return midi_path

    def preview_original_midi(self):
        midi_path = self.get_imported_original_midi()
        if midi_path:
            self.preview_selected_midi(midi_path=midi_path)

    def play_original_midi(self):
        midi_path = self.get_imported_original_midi()
        if not midi_path:
            return
        self.start_playback(midi_path=midi_path, original_events=True)

    def open_original_midi(self):
        midi_path = self.get_imported_original_midi()
        if not midi_path:
            return
        try:
            os.startfile(midi_path)
        except OSError as exc:
            messagebox.showerror("Unable to open MIDI", str(exc))

    def start_external_midi_import(self):
        filename = self.external_midi_path_var.get().strip()
        if not filename:
            messagebox.showwarning("No MIDI selected", "Browse for a MIDI file first.")
            return
        try:
            options = self.get_processing_options()
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Processing settings must be numbers.")
            return
        skips = {
            "cleanup": bool(self.skip_cleanup_var.get()),
            "piano_arranger": bool(self.skip_piano_arranger_var.get()),
            "ai_optimizer": bool(self.skip_ai_optimizer_var.get()),
            "pitch_correction": bool(self.skip_pitch_correction_var.get()),
        }
        selected_parts = self.get_selected_external_parts("optimize")
        if not selected_parts:
            messagebox.showwarning(
                "No optimization parts",
                "Select at least one Track/Channel part for Optimization.",
            )
            return
        part_range_mode = self.external_part_range_mode_var.get()
        self._begin_conversion(
            "Processing imported MIDI...",
            f"Processing imported MIDI: {filename}",
            preserve_sources=True,
        )
        self.log_message(f"Keyboard profile: {options['keyboard_profile']}")
        threading.Thread(
            target=self.external_midi_import_worker,
            args=(filename, options, skips, selected_parts, part_range_mode),
            daemon=True,
        ).start()

    def external_midi_import_worker(
        self, filename, options, skips, selected_parts, part_range_mode
    ):
        try:
            result = import_external_midi(
                filename,
                options=options,
                skips=skips,
                selected_parts=selected_parts,
                part_range_mode=part_range_mode,
                progress_callback=lambda message: self.queue.put(("log", message)),
            )
            result["selected_direct_midi"] = getattr(
                self, "selected_direct_midi_path", None
            )
            result["selected_direct_midi_stats"] = getattr(
                self, "selected_direct_midi_stats", None
            )
            self.queue.put(("external_midi_done", result))
        except Exception as exc:
            self.queue.put(("convert_error", format_command_error(exc)))

    def convert_worker(
        self, url, options=None, separation_mode=None, stem_to_convert=None
    ):
        try:
            check_cli_dependencies()
            self.queue.put(("status", "Downloading and converting"))
            demucs_device = self.demucs_device_var.get()
            if demucs_device == "auto":
                demucs_device = None
            separation_mode = separation_mode or self.separation_mode_var.get()
            stem_to_convert = stem_to_convert or self.stem_to_convert_var.get()
            results = youtube_to_midi(
                url,
                cancel_token=self.convert_cancel_token,
                demucs_device=demucs_device,
                convert_vocals_midi=bool(self.convert_vocals_midi_var.get()),
                progress_callback=lambda message: self.queue.put(("log", message)),
                options=options,
                separation_mode=separation_mode,
                stem_to_convert=stem_to_convert,
            )
            self._queue_conversion_result(results)
        except CancelledError:
            self.queue.put(("convert_cancelled", None))
        except Exception as exc:
            self.queue.put(("convert_error", format_command_error(exc)))

    def local_audio_convert_worker(
        self, filename, options=None, separation_mode=None, stem_to_convert=None
    ):
        try:
            check_cli_dependencies()
            self.queue.put(("status", "Converting local audio"))
            demucs_device = self.demucs_device_var.get()
            if demucs_device == "auto":
                demucs_device = None
            separation_mode = separation_mode or self.separation_mode_var.get()
            stem_to_convert = stem_to_convert or self.stem_to_convert_var.get()
            results = audio_file_to_midi(
                filename,
                cancel_token=self.convert_cancel_token,
                demucs_device=demucs_device,
                convert_vocals_midi=bool(self.convert_vocals_midi_var.get()),
                progress_callback=lambda message: self.queue.put(("log", message)),
                options=options,
                separation_mode=separation_mode,
                stem_to_convert=stem_to_convert,
            )
            self._queue_conversion_result(results)
        except CancelledError:
            self.queue.put(("convert_cancelled", None))
        except Exception as exc:
            self.queue.put(("convert_error", format_command_error(exc)))

    def _queue_conversion_result(self, results):
        self.queue.put(("log", f"Output folder: {results['base_dir']}"))
        if results.get("cached"):
            self.queue.put(("log", "Loaded cached conversion."))
        self.queue.put(("log", f"Original WAV: {results['wav_file']}"))
        self.queue.put(("log", f"Selected audio: {results.get('selected_audio')}"))
        self.queue.put(("log", f"Vocals MIDI: {results.get('vocal_midi')}"))
        self.queue.put(("log", f"Accompaniment MIDI: {results['accompaniment_midi']}"))
        self.queue.put(("log", f"Vocals Clean 37-Key MIDI: {results.get('vocal_clean_midi')}"))
        self.queue.put(
            ("log", f"Vocals AI Optimized MIDI: {results.get('vocal_ai_optimized_midi')}")
        )
        self.queue.put(
            (
                "log",
                f"Vocals Pitch Corrected MIDI: {results.get('vocal_pitch_corrected_midi')}",
            )
        )
        self.queue.put(("log", f"Vocals Final 37-Key MIDI: {results.get('vocal_final_midi')}"))
        self.queue.put(("log", f"Vocals detected key: {results.get('vocal_detected_key')}"))
        self.queue.put(
            (
                "log",
                f"Accompaniment Clean 37-Key MIDI: {results['accompaniment_clean_midi']}",
            )
        )
        self.queue.put(
            (
                "log",
                f"Accompaniment AI Optimized MIDI: {results['accompaniment_ai_optimized_midi']}",
            )
        )
        self.queue.put(
            (
                "log",
                "Accompaniment Pitch Corrected MIDI: "
                f"{results['accompaniment_pitch_corrected_midi']}",
            )
        )
        self.queue.put(
            ("log", f"Accompaniment Final 37-Key MIDI: {results['accompaniment_final_midi']}")
        )
        self.queue.put(
            ("log", f"Accompaniment detected key: {results.get('accompaniment_detected_key')}")
        )
        if results.get("accompaniment_report_path"):
            self.queue.put(
                ("log", f"MIDI analysis report: {results['accompaniment_report_path']}")
            )
        self.queue.put(("converted", results))
