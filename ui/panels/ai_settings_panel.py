from tkinter import ttk

from ai_models import model_values_for_provider


def build_ai_settings_panel(app, parent, start_row=0):
    status = ttk.LabelFrame(parent, text="AI Optimizer Status", padding=12)
    status.grid(row=start_row, column=0, sticky="new", padx=12, pady=(12, 8))
    status.columnconfigure(0, weight=1)
    ttk.Label(status, textvariable=app.ai_provider_status_var).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(status, textvariable=app.ai_model_status_var).grid(
        row=1, column=0, sticky="w", pady=(4, 0)
    )
    ttk.Label(status, textvariable=app.ai_key_status_var).grid(
        row=2, column=0, sticky="w", pady=(4, 0)
    )
    ttk.Label(status, textvariable=app.ai_status_var).grid(
        row=3, column=0, sticky="w", pady=(8, 0)
    )

    panel = ttk.LabelFrame(parent, text="AI Settings", padding=12)
    panel.grid(row=start_row + 1, column=0, sticky="new", padx=12, pady=(0, 12))
    panel.columnconfigure(1, weight=1)

    ttk.Label(panel, text="Provider").grid(row=0, column=0, sticky="w", pady=(0, 8))
    provider = ttk.Combobox(
        panel,
        textvariable=app.ai_provider_var,
        values=("disabled", "openai", "gemini", "openai_compatible"),
        state="readonly",
        width=22,
    )
    provider.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))
    provider.bind("<<ComboboxSelected>>", app.on_ai_settings_changed)

    provider_fields = ttk.Frame(panel)
    provider_fields.grid(row=1, column=0, columnspan=3, sticky="ew")
    provider_fields.columnconfigure(1, weight=1)
    app.ai_provider_fields_frame = provider_fields
    ttk.Label(provider_fields, text="API Key").grid(row=0, column=0, sticky="w", pady=(0, 8))
    key_entry = ttk.Entry(
        provider_fields,
        textvariable=app.ai_api_key_var,
        show="*",
    )
    key_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8), pady=(0, 8))
    app.ai_api_key_entry = key_entry
    ttk.Button(provider_fields, text="Show / Hide Key", command=app.toggle_ai_api_key).grid(
        row=0, column=2, sticky="w", pady=(0, 8)
    )

    ttk.Label(provider_fields, text="Model").grid(row=1, column=0, sticky="w", pady=(0, 8))
    model_combo = ttk.Combobox(
        provider_fields,
        textvariable=app.ai_model_var,
        values=model_values_for_provider(app.ai_provider_var.get()),
        state="normal",
        width=22,
    )
    model_combo.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(0, 8))
    app.ai_model_combo = model_combo
    ttk.Button(provider_fields, text="Refresh Models", command=app.start_ai_model_refresh).grid(
        row=1, column=2, sticky="w", pady=(0, 8)
    )

    compatible_fields = ttk.Frame(provider_fields)
    compatible_fields.grid(row=2, column=0, columnspan=3, sticky="ew")
    compatible_fields.columnconfigure(1, weight=1)
    app.ai_compatible_fields_frame = compatible_fields
    ttk.Label(compatible_fields, text="Base URL").grid(row=0, column=0, sticky="w", pady=(0, 8))
    ttk.Entry(compatible_fields, textvariable=app.ai_base_url_var).grid(
        row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 8)
    )

    ttk.Label(panel, text="Timeout seconds").grid(row=2, column=0, sticky="w", pady=(0, 8))
    ttk.Spinbox(
        panel, from_=1, to=600, increment=1,
        textvariable=app.ai_timeout_var, width=8,
    ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(0, 8))

    ttk.Label(panel, text="Max retries").grid(row=3, column=0, sticky="w", pady=(0, 8))
    ttk.Spinbox(
        panel, from_=0, to=10, increment=1,
        textvariable=app.ai_max_retries_var, width=8,
    ).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(0, 8))

    actions = ttk.Frame(panel)
    actions.grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))
    ttk.Button(actions, text="Test Connection", command=app.start_ai_connection_test).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Button(actions, text="Save Settings", command=app.save_ai_settings_from_ui).grid(
        row=0, column=1, sticky="w", padx=(8, 0)
    )
    ttk.Button(actions, text="Clear Current Provider Key", command=app.clear_ai_key_from_ui).grid(
        row=0, column=2, sticky="w", padx=(8, 0)
    )
    app.on_ai_settings_changed()
    return start_row + 2
