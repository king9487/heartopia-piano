from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import keyboard

from converter import (
    audio_file_to_midi,
    list_converted_outputs,
    results_from_output_dir,
    youtube_to_midi,
)
from midi_to_keyboard import iter_note_events, midi_note_name, play_midi_as_keyboard
from tools import CancellationToken, CancelledError, check_cli_dependencies, default_demucs_device


class YoutubeMidiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube MIDI Keyboard")
        self.root.geometry("760x560")
        self.root.minsize(660, 480)
        self.root.attributes("-topmost", True)

        self.queue = queue.Queue()
        self.results = None
        self.converting = False
        self.convert_cancel_token = None
        self.playing = False
        self.stop_event = threading.Event()
        self.stop_hotkey = None

        self.url_var = tk.StringVar()
        self.always_top_var = tk.BooleanVar(value=True)
        self.midi_choice_var = tk.StringVar(value="vocal_midi")
        self.selected_midi_var = tk.StringVar()
        self.cached_choice_var = tk.StringVar()
        self.cached_outputs = []
        self.demucs_device_var = tk.StringVar(value=default_demucs_device() or "auto")
        self.speed_var = tk.DoubleVar(value=1.0)
        self.countdown_var = tk.IntVar(value=3)
        self.transpose_var = tk.IntVar(value=0)
        self.chord_delay_var = tk.IntVar(value=18)
        self.min_hold_var = tk.IntVar(value=75)
        self.min_note_duration_var = tk.IntVar(value=35)
        self.velocity_threshold_var = tk.IntVar(value=12)
        self.max_simultaneous_var = tk.IntVar(value=0)
        self.octave_fit_var = tk.StringVar(value="octave_shift")
        self.status_var = tk.StringVar(value="Ready")

        self.build_ui()
        self.refresh_converted_outputs()
        self.root.bind("<F8>", self.stop_keyboard_playback)
        self.poll_queue()

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(6, weight=1)

        top = ttk.Frame(self.root, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="YouTube URL").grid(row=0, column=0, sticky="w")
        url_entry = ttk.Entry(top, textvariable=self.url_var)
        url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        url_entry.focus_set()

        self.convert_button = ttk.Button(top, text="Convert URL", command=self.start_convert)
        self.convert_button.grid(row=0, column=2, sticky="e")
        self.local_audio_button = ttk.Button(
            top, text="Open Audio", command=self.start_local_audio_convert
        )
        self.local_audio_button.grid(row=0, column=3, sticky="e", padx=(8, 0))

        options = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        options.grid(row=1, column=0, sticky="ew")
        options.columnconfigure(4, weight=1)

        ttk.Checkbutton(
            options,
            text="Always on top",
            variable=self.always_top_var,
            command=self.apply_topmost,
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(options, text="Speed").grid(row=0, column=1, sticky="w", padx=(18, 4))
        ttk.Spinbox(
            options,
            from_=0.25,
            to=3.0,
            increment=0.25,
            textvariable=self.speed_var,
            width=6,
        ).grid(row=0, column=2, sticky="w")

        ttk.Label(options, text="Focus delay").grid(row=0, column=3, sticky="w", padx=(18, 4))
        ttk.Spinbox(
            options,
            from_=1,
            to=10,
            increment=1,
            textvariable=self.countdown_var,
            width=5,
        ).grid(row=0, column=4, sticky="w")

        ttk.Label(options, text="Demucs").grid(row=0, column=5, sticky="w", padx=(18, 4))
        ttk.Combobox(
            options,
            textvariable=self.demucs_device_var,
            values=("cuda:0", "auto", "cpu"),
            state="readonly",
            width=8,
        ).grid(row=0, column=6, sticky="w")

        timing = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        timing.grid(row=2, column=0, sticky="ew")
        timing.columnconfigure(6, weight=1)

        ttk.Label(timing, text="Transpose").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            timing,
            from_=-36,
            to=36,
            increment=1,
            textvariable=self.transpose_var,
            width=6,
        ).grid(row=0, column=1, sticky="w", padx=(4, 18))

        ttk.Label(timing, text="Chord gap ms").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(
            timing,
            from_=0,
            to=80,
            increment=2,
            textvariable=self.chord_delay_var,
            width=6,
        ).grid(row=0, column=3, sticky="w", padx=(4, 18))

        ttk.Label(timing, text="Min hold ms").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(
            timing,
            from_=20,
            to=250,
            increment=5,
            textvariable=self.min_hold_var,
            width=6,
        ).grid(row=0, column=5, sticky="w", padx=(4, 0))

        cleanup = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        cleanup.grid(row=3, column=0, sticky="ew")
        cleanup.columnconfigure(7, weight=1)

        ttk.Label(cleanup, text="Min note ms").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            cleanup,
            from_=0,
            to=500,
            increment=5,
            textvariable=self.min_note_duration_var,
            width=6,
        ).grid(row=0, column=1, sticky="w", padx=(4, 18))

        ttk.Label(cleanup, text="Velocity").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(
            cleanup,
            from_=0,
            to=127,
            increment=1,
            textvariable=self.velocity_threshold_var,
            width=6,
        ).grid(row=0, column=3, sticky="w", padx=(4, 18))

        ttk.Label(cleanup, text="Max notes").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(
            cleanup,
            from_=0,
            to=12,
            increment=1,
            textvariable=self.max_simultaneous_var,
            width=6,
        ).grid(row=0, column=5, sticky="w", padx=(4, 18))

        ttk.Label(cleanup, text="Octave fit").grid(row=0, column=6, sticky="w")
        ttk.Combobox(
            cleanup,
            textvariable=self.octave_fit_var,
            values=("off", "octave_shift", "drop"),
            state="readonly",
            width=12,
        ).grid(row=0, column=7, sticky="w", padx=(4, 0))

        midi_panel = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        midi_panel.grid(row=4, column=0, sticky="ew")
        midi_panel.columnconfigure(5, weight=1)

        ttk.Radiobutton(
            midi_panel,
            text="Vocals MIDI",
            value="vocal_midi",
            variable=self.midi_choice_var,
            command=self.update_selected_midi,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            midi_panel,
            text="Accompaniment MIDI",
            value="accompaniment_midi",
            variable=self.midi_choice_var,
            command=self.update_selected_midi,
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))

        ttk.Button(midi_panel, text="Open MIDI", command=self.open_midi).grid(
            row=0, column=2, padx=(12, 0)
        )
        ttk.Button(midi_panel, text="Open Converted", command=self.open_converted).grid(
            row=0, column=3, padx=(8, 0)
        )
        ttk.Button(midi_panel, text="Preview", command=self.preview_selected_midi).grid(
            row=0, column=4, padx=(8, 0)
        )
        self.play_button = ttk.Button(
            midi_panel, text="Play to Game", command=self.start_keyboard_playback
        )
        self.play_button.grid(row=0, column=5, sticky="e")
        self.stop_button = ttk.Button(
            midi_panel, text="Stop", command=self.stop_current_task, state="disabled"
        )
        self.stop_button.grid(row=0, column=6, sticky="e", padx=(8, 0))

        ttk.Label(midi_panel, text="Converted").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.cached_combo = ttk.Combobox(
            midi_panel, textvariable=self.cached_choice_var, state="readonly"
        )
        self.cached_combo.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(midi_panel, text="Refresh", command=self.refresh_converted_outputs).grid(
            row=1, column=4, sticky="w", padx=(8, 0), pady=(8, 0)
        )
        ttk.Button(midi_panel, text="Load", command=self.load_selected_converted).grid(
            row=1, column=5, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        selected = ttk.Label(
            self.root,
            textvariable=self.selected_midi_var,
            padding=(12, 0, 12, 8),
            foreground="#444",
        )
        selected.grid(row=5, column=0, sticky="new")

        log_frame = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        log_frame.grid(row=6, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(log_frame, height=16, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        status = ttk.Label(self.root, textvariable=self.status_var, padding=(12, 0, 12, 12))
        status.grid(row=7, column=0, sticky="ew")

    def apply_topmost(self):
        self.root.attributes("-topmost", self.always_top_var.get())

    def log_message(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll_queue(self):
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self.log_message(payload)
            elif kind == "status":
                self.status_var.set(payload)
            elif kind == "converted":
                self.results = payload
                self.converting = False
                self.convert_cancel_token = None
                self.update_selected_midi()
                self.refresh_converted_outputs()
                self.convert_button.configure(state="normal")
                self.local_audio_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_var.set("Conversion finished")
            elif kind == "convert_error":
                self.converting = False
                self.convert_cancel_token = None
                self.convert_button.configure(state="normal")
                self.local_audio_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_var.set("Conversion failed")
                messagebox.showerror("Conversion failed", payload)
            elif kind == "convert_cancelled":
                self.converting = False
                self.convert_cancel_token = None
                self.convert_button.configure(state="normal")
                self.local_audio_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_var.set("Conversion cancelled")
                self.log_message("Conversion cancelled.")
            elif kind == "play_done":
                self.playing = False
                self.unregister_stop_hotkey()
                self.play_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.root.deiconify()
                self.apply_topmost()
                self.status_var.set("Keyboard playback finished")
            elif kind == "play_error":
                self.playing = False
                self.unregister_stop_hotkey()
                self.play_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.root.deiconify()
                self.apply_topmost()
                self.status_var.set("Keyboard playback failed")
                messagebox.showerror("Keyboard playback failed", payload)

        self.root.after(100, self.poll_queue)

    def start_convert(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a YouTube URL first.")
            return

        self.convert_button.configure(state="disabled")
        self.local_audio_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.results = None
        self.selected_midi_var.set("")
        self.converting = True
        self.convert_cancel_token = CancellationToken()
        self.status_var.set("Checking dependencies")
        self.log_message("Starting conversion...")

        thread = threading.Thread(target=self.convert_worker, args=(url,), daemon=True)
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

        self.convert_button.configure(state="disabled")
        self.local_audio_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.results = None
        self.selected_midi_var.set("")
        self.converting = True
        self.convert_cancel_token = CancellationToken()
        self.status_var.set("Checking dependencies")
        self.log_message(f"Starting local audio conversion: {filename}")

        thread = threading.Thread(
            target=self.local_audio_convert_worker, args=(filename,), daemon=True
        )
        thread.start()

    def convert_worker(self, url):
        try:
            check_cli_dependencies()
            self.queue.put(("status", "Downloading and converting"))
            demucs_device = self.demucs_device_var.get()
            if demucs_device == "auto":
                demucs_device = None
            results = youtube_to_midi(
                url,
                cancel_token=self.convert_cancel_token,
                demucs_device=demucs_device,
            )

            self.queue.put(("log", f"Output folder: {results['base_dir']}"))
            if results.get("cached"):
                self.queue.put(("log", "Loaded cached conversion."))
            self.queue.put(("log", f"Original WAV: {results['wav_file']}"))
            self.queue.put(("log", f"Vocals MIDI: {results['vocal_midi']}"))
            self.queue.put(("log", f"Accompaniment MIDI: {results['accompaniment_midi']}"))
            self.queue.put(("converted", results))
        except CancelledError:
            self.queue.put(("convert_cancelled", None))
        except Exception as exc:
            self.queue.put(("convert_error", str(exc)))

    def local_audio_convert_worker(self, filename):
        try:
            check_cli_dependencies()
            self.queue.put(("status", "Converting local audio"))
            demucs_device = self.demucs_device_var.get()
            if demucs_device == "auto":
                demucs_device = None
            results = audio_file_to_midi(
                filename,
                cancel_token=self.convert_cancel_token,
                demucs_device=demucs_device,
            )

            self.queue.put(("log", f"Output folder: {results['base_dir']}"))
            if results.get("cached"):
                self.queue.put(("log", "Loaded cached conversion."))
            self.queue.put(("log", f"Original WAV: {results['wav_file']}"))
            self.queue.put(("log", f"Vocals MIDI: {results['vocal_midi']}"))
            self.queue.put(("log", f"Accompaniment MIDI: {results['accompaniment_midi']}"))
            self.queue.put(("converted", results))
        except CancelledError:
            self.queue.put(("convert_cancelled", None))
        except Exception as exc:
            self.queue.put(("convert_error", str(exc)))

    def update_selected_midi(self):
        if not self.results:
            return

        midi_file = self.results.get(self.midi_choice_var.get())
        if midi_file:
            self.selected_midi_var.set(str(midi_file))

    def open_midi(self):
        filename = filedialog.askopenfilename(
            title="Open MIDI file",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if filename:
            self.selected_midi_var.set(filename)
            self.results = None

    def open_converted(self):
        output_root = Path("output")
        initial_dir = output_root if output_root.exists() else Path.cwd()
        dirname = filedialog.askdirectory(
            title="Open converted output folder",
            initialdir=initial_dir,
        )
        if not dirname:
            return

        results = results_from_output_dir(dirname)
        if not results:
            messagebox.showerror(
                "Converted folder not found",
                "This folder does not contain both vocals and accompaniment MIDI files.",
            )
            return

        self.results = results
        self.update_selected_midi()
        self.log_message(f"Loaded converted folder: {results['base_dir']}")
        self.log_message(f"Vocals MIDI: {results['vocal_midi']}")
        self.log_message(f"Accompaniment MIDI: {results['accompaniment_midi']}")
        self.status_var.set("Converted folder loaded")

    def refresh_converted_outputs(self):
        self.cached_outputs = list_converted_outputs()
        names = [path.name for path in self.cached_outputs]
        self.cached_combo.configure(values=names)
        if names and self.cached_choice_var.get() not in names:
            self.cached_choice_var.set(names[0])
        elif not names:
            self.cached_choice_var.set("")

    def load_selected_converted(self):
        name = self.cached_choice_var.get()
        if not name:
            messagebox.showwarning("No converted output", "No completed conversions were found.")
            return

        for path in self.cached_outputs:
            if path.name == name:
                results = results_from_output_dir(path)
                if results:
                    self.results = results
                    self.update_selected_midi()
                    self.log_message(f"Loaded converted folder: {results['base_dir']}")
                    self.status_var.set("Converted folder loaded")
                return

    def get_selected_midi(self):
        value = self.selected_midi_var.get().strip()
        if not value:
            messagebox.showwarning("No MIDI selected", "Convert or open a MIDI file first.")
            return None

        midi_path = Path(value)
        if not midi_path.exists():
            messagebox.showerror("MIDI not found", str(midi_path))
            return None

        return midi_path

    def get_cleanup_settings(self):
        try:
            return {
                "transpose": int(self.transpose_var.get()),
                "min_note_duration": int(self.min_note_duration_var.get()) / 1000,
                "velocity_threshold": int(self.velocity_threshold_var.get()),
                "max_simultaneous_notes": int(self.max_simultaneous_var.get()),
                "octave_fit_mode": self.octave_fit_var.get(),
            }
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Cleanup settings must be numbers.")
            return None

    def preview_selected_midi(self):
        midi_path = self.get_selected_midi()
        if not midi_path:
            return

        self.log_message(f"Preview: {midi_path}")
        count = 0
        cleanup_settings = self.get_cleanup_settings()
        if cleanup_settings is None:
            return

        for timestamp, action, note, key in iter_note_events(midi_path, **cleanup_settings):
            note_name = midi_note_name(note)
            self.log_message(
                f"{timestamp:8.3f}s  note {note:3d} {note_name:3s}  {action:4s}  key {key}"
            )
            count += 1
            if count >= 80:
                self.log_message("... preview stopped after 80 events")
                break
        if count == 0:
            self.log_message("No mapped note events found in this MIDI file.")

    def start_keyboard_playback(self):
        midi_path = self.get_selected_midi()
        if not midi_path or self.playing:
            return

        try:
            speed = float(self.speed_var.get())
            countdown = int(self.countdown_var.get())
            chord_delay = int(self.chord_delay_var.get()) / 1000
            min_hold = int(self.min_hold_var.get()) / 1000
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Playback settings must be numbers.")
            return

        cleanup_settings = self.get_cleanup_settings()
        if cleanup_settings is None:
            return

        if speed <= 0 or countdown < 1 or chord_delay < 0 or min_hold < 0:
            messagebox.showerror("Invalid setting", "Playback settings are out of range.")
            return

        self.playing = True
        self.stop_event.clear()
        self.register_stop_hotkey()
        self.play_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set(f"Hiding window. Focus the game within {countdown} seconds.")
        self.log_message(f"Keyboard playback will start in {countdown} seconds. Press F8 to stop.")
        self.root.withdraw()

        thread = threading.Thread(
            target=self.play_worker,
            args=(midi_path, speed, countdown, chord_delay, min_hold, cleanup_settings),
            daemon=True,
        )
        thread.start()

    def play_worker(self, midi_path, speed, countdown, chord_delay, min_hold, cleanup_settings):
        try:
            if self.stop_event.wait(countdown):
                self.queue.put(("play_done", None))
                return
            play_midi_as_keyboard(
                midi_path,
                speed=speed,
                stop_event=self.stop_event,
                chord_delay=chord_delay,
                min_hold=min_hold,
                **cleanup_settings,
            )
            self.queue.put(("play_done", None))
        except Exception as exc:
            self.queue.put(("play_error", str(exc)))

    def stop_keyboard_playback(self, event=None):
        if self.playing:
            self.stop_event.set()
            self.status_var.set("Stopping keyboard playback")
            self.log_message("Stop requested.")

    def stop_current_task(self):
        if self.converting and self.convert_cancel_token:
            self.status_var.set("Cancelling conversion")
            self.log_message("Cancelling conversion...")
            self.convert_cancel_token.cancel()
            return

        self.stop_keyboard_playback()

    def register_stop_hotkey(self):
        self.unregister_stop_hotkey()
        self.stop_hotkey = keyboard.add_hotkey("f8", self.stop_keyboard_playback)

    def unregister_stop_hotkey(self):
        if self.stop_hotkey is not None:
            keyboard.remove_hotkey(self.stop_hotkey)
            self.stop_hotkey = None


def main():
    root = tk.Tk()
    YoutubeMidiApp(root)
    root.mainloop()
