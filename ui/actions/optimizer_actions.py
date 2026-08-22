import threading
from tkinter import messagebox

from ai_settings import (
    PROVIDER_DISABLED,
    clear_provider_key,
    get_active_provider_settings,
    load_ai_settings,
    redact_api_key,
    save_ai_settings,
    validate_ai_settings,
)
from converter import rebuild_midi_stages
from ai_models import model_values_for_provider, selected_model_for_provider
from ai_providers import ProviderError, create_provider
from keyboard_profiles import get_keyboard_profile, processing_options_for_profile
from midi_ai_optimizer import post_process_37key_midi, test_ai_connection
from ui.presets import apply_processing_preset


class UiOptimizerActionsMixin:
    def current_ai_settings_from_ui(self):
        provider = self.ai_provider_var.get().strip().lower().replace("-", "_")
        if provider != PROVIDER_DISABLED:
            self.ai_draft_api_keys[provider] = self.ai_api_key_var.get()
            self.ai_draft_models[provider] = self.ai_model_var.get().strip()
        return {
            "provider": provider,
            "api_keys": dict(self.ai_draft_api_keys),
            "models": dict(self.ai_draft_models),
            "openai_compatible_base_url": self.ai_base_url_var.get().strip(),
            "timeout_seconds": int(self.ai_timeout_var.get()),
            "max_retries": int(self.ai_max_retries_var.get()),
        }

    def refresh_ai_settings_status(self):
        settings = self.current_ai_settings_from_ui()
        active = get_active_provider_settings(settings)
        provider_label = {
            "disabled": "Disabled",
            "openai": "OpenAI",
            "gemini": "Gemini",
            "openai_compatible": "OpenAI-compatible",
        }.get(settings["provider"], "Invalid")
        self.ai_provider_status_var.set(f"AI Provider: {provider_label}")
        self.ai_model_status_var.set(
            f"AI Model: {active['model'] or 'not configured'}"
        )
        self.ai_key_status_var.set(
            "API Key: Configured" if active["api_key"].strip() else "API Key: Missing"
        )
        valid, _errors = validate_ai_settings(settings)
        if settings["provider"] == PROVIDER_DISABLED:
            self.ai_status_var.set("AI disabled")
        elif valid:
            self.ai_status_var.set("Ready")
        elif not active["api_key"].strip():
            self.ai_status_var.set("Missing key")
        else:
            self.ai_status_var.set("Invalid response")

    def on_ai_settings_changed(self, event=None):
        previous = getattr(self, "ai_previous_provider", PROVIDER_DISABLED)
        if previous != PROVIDER_DISABLED:
            self.ai_draft_api_keys[previous] = self.ai_api_key_var.get()
            self.ai_draft_models[previous] = self.ai_model_var.get().strip()
        provider = self.ai_provider_var.get().replace("-", "_")
        self.ai_previous_provider = provider
        self.ai_api_key_var.set(self.ai_draft_api_keys.get(provider, ""))
        model = selected_model_for_provider(provider, self.ai_draft_models)
        self.ai_model_var.set(model)
        model_combo = getattr(self, "ai_model_combo", None)
        if model_combo is not None:
            model_combo.configure(values=model_values_for_provider(provider))
        fields = getattr(self, "ai_provider_fields_frame", None)
        compatible = getattr(self, "ai_compatible_fields_frame", None)
        if fields is not None:
            fields.grid_remove() if provider == PROVIDER_DISABLED else fields.grid()
        if compatible is not None:
            compatible.grid() if provider == "openai_compatible" else compatible.grid_remove()
        self.refresh_ai_settings_status()

    def toggle_ai_api_key(self):
        self.ai_show_key_var.set(not bool(self.ai_show_key_var.get()))
        entry = getattr(self, "ai_api_key_entry", None)
        if entry is not None:
            entry.configure(show="" if self.ai_show_key_var.get() else "*")

    def save_ai_settings_from_ui(self):
        try:
            settings = self.current_ai_settings_from_ui()
        except (TypeError, ValueError):
            self.ai_status_var.set("Invalid configuration")
            messagebox.showerror(
                "Invalid configuration",
                "Timeout and max retries must be whole numbers.",
            )
            return None
        valid, errors = validate_ai_settings(settings)
        if settings["provider"] != PROVIDER_DISABLED and not valid:
            self.ai_status_var.set("Invalid configuration")
            messagebox.showerror("Invalid configuration", "\n".join(errors))
            return None
        try:
            saved = save_ai_settings(settings)
        except Exception as exc:
            self.ai_status_var.set("Invalid configuration")
            messagebox.showerror(
                "Save failed",
                redact_api_key(exc, get_active_provider_settings(settings).get("api_key", "")),
            )
            return None
        self.ai_provider_var.set(saved["provider"])
        self.ai_draft_api_keys = dict(saved["api_keys"])
        self.ai_draft_models = dict(saved["models"])
        active = get_active_provider_settings(saved)
        self.ai_api_key_var.set(active["api_key"])
        self.ai_model_var.set(active["model"])
        self.ai_base_url_var.set(saved["openai_compatible_base_url"])
        self.ai_timeout_var.set(saved["timeout_seconds"])
        self.ai_max_retries_var.set(saved["max_retries"])
        self.refresh_ai_settings_status()
        self.log_message(
            "AI settings saved: "
            f"provider={saved['provider']}, "
            f"model={active['model'] or 'not configured'}, "
            f"api_key={'configured' if active['api_key'] else 'missing'}"
        )
        messagebox.showinfo("AI Settings", "AI settings saved.")
        return saved

    def clear_ai_key_from_ui(self):
        try:
            saved = clear_provider_key(self.ai_provider_var.get())
        except Exception as exc:
            messagebox.showerror("Clear key failed", redact_api_key(exc))
            return
        self.ai_api_key_var.set("")
        self.ai_draft_api_keys = dict(saved["api_keys"])
        self.refresh_ai_settings_status()
        self.log_message(
            "AI API key cleared; provider/model/base URL preserved."
        )

    def start_ai_connection_test(self):
        try:
            settings = self.current_ai_settings_from_ui()
        except (TypeError, ValueError):
            self.ai_status_var.set("Invalid configuration")
            messagebox.showerror(
                "Invalid configuration",
                "Timeout and max retries must be whole numbers.",
            )
            return
        self.ai_status_var.set("Testing")
        threading.Thread(
            target=self.ai_connection_test_worker,
            args=(settings,),
            daemon=True,
        ).start()

    def start_ai_model_refresh(self):
        try:
            settings = self.current_ai_settings_from_ui()
            active = get_active_provider_settings(settings)
            if active["provider"] == PROVIDER_DISABLED or not active["api_key"]:
                raise ValueError("Select a provider and configure its API key first.")
        except (TypeError, ValueError) as exc:
            messagebox.showwarning("Refresh Models", str(exc))
            return
        self.ai_status_var.set("Refreshing models")
        threading.Thread(target=self.ai_model_refresh_worker, args=(active,), daemon=True).start()

    def ai_model_refresh_worker(self, settings):
        try:
            models = create_provider(settings).list_models()
            self.queue.put(("ai_models_done", {"provider": settings["provider"], "models": models}))
        except Exception as exc:
            self.queue.put(("ai_models_error", {"provider": settings["provider"], "message": redact_api_key(exc, settings["api_key"])}))

    def ai_connection_test_worker(self, settings):
        ok, message = test_ai_connection(settings)
        status = "Connected" if ok else message
        self.queue.put(("ai_test_done", {"ok": ok, "message": message, "status": status}))

    def _prepare_ai_options_or_prompt(self, mode):
        if mode not in ("ai", "openai"):
            return {}
        settings = load_ai_settings()
        valid, errors = validate_ai_settings(settings)
        if settings["provider"] == PROVIDER_DISABLED:
            messagebox.showwarning(
                "AI disabled",
                "AI Optimizer is disabled. Open AI Settings to configure a provider, or use Rule mode.",
            )
            if getattr(self, "notebook", None) is not None and getattr(self, "ai_settings_tab", None) is not None:
                self.notebook.select(self.ai_settings_tab)
            return None
        if not valid:
            message = "\n".join(errors) or "Invalid configuration"
            messagebox.showwarning("AI API key is not configured", message)
            if getattr(self, "notebook", None) is not None and getattr(self, "ai_settings_tab", None) is not None:
                self.notebook.select(self.ai_settings_tab)
            return None
        return {"ai_settings": settings}

    def on_keyboard_profile_changed(self, event=None):
        profile = get_keyboard_profile(self.keyboard_profile_var.get())
        self.keyboard_profile_var.set(profile.name)
        if "Keyboard Profile" in self.analysis_vars:
            self.analysis_vars["Keyboard Profile"].set(
                f"{profile.name} ({profile.range_label})"
            )
        self.on_mapping_keyboard_profile_changed()

    def on_processing_preset_changed(self, event=None):
        preset = self.processing_preset_var.get()
        apply_processing_preset(self, preset)
        self.log_message(f"Processing preset applied: {preset}")

    def get_processing_options(self):
        mode = self.optimizer_mode_var.get().strip().lower()
        ai_options = self._prepare_ai_options_or_prompt(mode)
        if ai_options is None:
            raise ValueError("AI API key is not configured")
        return {
            "mode": mode,
            "arrangement_style": self.arrangement_style_var.get().strip().lower(),
            "max_notes_per_window": max(1, min(int(self.melody_max_notes_var.get()), 3)),
            "arrangement_window_ms": int(self.melody_window_var.get()),
            "min_note_duration_ms": int(self.min_note_duration_var.get()),
            "velocity_threshold": int(self.velocity_threshold_var.get()),
            "max_simultaneous_notes": int(self.max_simultaneous_var.get()),
            "out_of_range_mode": self.octave_fit_var.get(),
            "prefer_melody": True,
            **ai_options,
            **processing_options_for_profile(self.keyboard_profile_var.get()),
        }

    def _raw_midi_for_rebuild(self):
        if self.results:
            raw_key = self.midi_choice_var.get()
            raw_midi = self.results.get(raw_key)
            if raw_midi:
                return raw_midi
        selected = self.get_selected_midi()
        if selected and selected.name.lower() not in {
            "edited_37key.mid", "clean_37key.mid", "piano_arranged_37key.mid",
            "piano_cover_37key.mid", "ai_optimized_37key.mid",
            "pitch_corrected_37key.mid", "final_37key.mid",
        }:
            return selected
        messagebox.showwarning("Raw MIDI unavailable", "Load a conversion with its Raw MIDI before rebuilding stages.")
        return None

    def start_rebuild_stage(self, stage):
        raw_midi = self._raw_midi_for_rebuild()
        if not raw_midi:
            return
        try:
            options = self.get_processing_options()
        except (TypeError, ValueError) as exc:
            if str(exc) == "AI API key is not configured":
                return
            messagebox.showerror("Invalid setting", "Processing settings must be numbers.")
            return
        label = stage.replace("_", " ").title()
        self.status_var.set(f"Rebuilding {label}")
        self.log_message(f"Rebuild requested from {label} stage: {raw_midi}")
        self.log_message(f"Keyboard profile: {options['keyboard_profile']}")
        threading.Thread(
            target=self.rebuild_stage_worker,
            args=(raw_midi, stage, options),
            daemon=True,
        ).start()

    def rebuild_stage_worker(self, raw_midi, stage, options):
        try:
            result = rebuild_midi_stages(raw_midi, stage, options=options)
            self.queue.put(("rebuild_done", result))
        except Exception as exc:
            payload = {"message": str(exc)}
            if isinstance(exc, ProviderError):
                payload.update({"provider_status": exc.status, "details": exc.details})
            self.queue.put(("rebuild_error", payload))

    def start_optimize_midi(self):
        midi_path = self.get_selected_midi()
        if not midi_path:
            return

        mode = self.optimizer_mode_var.get().strip().lower()
        arrangement_style = self.arrangement_style_var.get().strip().lower()
        if mode == "none" and arrangement_style == "original":
            messagebox.showwarning(
                "Optimizer disabled",
                "Choose Rule/OpenAI or select a simplified arrangement style first.",
            )
            return

        try:
            ai_options = self._prepare_ai_options_or_prompt(mode)
            if ai_options is None:
                return
            options = {
                "mode": mode,
                "arrangement_style": arrangement_style,
                "max_notes_per_window": max(
                    1, min(int(self.melody_max_notes_var.get()), 3)
                ),
                "min_note_duration_ms": int(self.min_note_duration_var.get()),
                **ai_options,
                **processing_options_for_profile(self.keyboard_profile_var.get()),
            }
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Optimizer settings must be numbers.")
            return

        is_ai_mode = mode in ("ai", "openai")
        status_message = (
            "AI Optimizer is processing MIDI..."
            if is_ai_mode
            else "Optimizing MIDI..."
        )
        self.status_var.set(status_message)
        self.log_message(
            "Optimizing MIDI with "
            f"{self.arrangement_style_var.get()} arrangement / "
            f"{self.optimizer_mode_var.get()} mode: {midi_path}"
        )
        self.log_message(f"Keyboard profile: {options['keyboard_profile']}")
        if is_ai_mode:
            self.log_message(
                "AI Optimizer request started. Processing may take a while; "
                "the result will appear when it finishes."
            )
        self.root.update_idletasks()
        thread = threading.Thread(
            target=self.optimize_worker,
            args=(midi_path, options),
            daemon=True,
        )
        thread.start()
        if is_ai_mode:
            messagebox.showinfo(
                "AI Optimizer",
                "AI Optimizer is processing the MIDI now.\n\n"
                "This may take a while. You can close this message; "
                "processing will continue in the background.",
            )

    def optimize_worker(self, midi_path, options):
        try:
            result = post_process_37key_midi(midi_path, options=options)
            self.queue.put(("optimize_done", result))
        except Exception as exc:
            payload = {"message": str(exc)}
            if isinstance(exc, ProviderError):
                payload.update({"provider_status": exc.status, "details": exc.details})
            self.queue.put(("optimize_error", payload))
