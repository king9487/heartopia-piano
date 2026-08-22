# Full Project Audit

Date: 2026-07-03  
Scope: all repository Python, UI, launcher, test, dependency, and project-documentation files; `.venv`, `.git`, generated `output/`, and caches excluded.  
Method: AST import/reference scan, call-site search, circular-import analysis, pylint checks, targeted review of timing/thread/resource paths, and the full unit-test suite.

## Executive summary

- Critical: **0**
- High: **5**
- Medium: **19** (16 numbered issues plus 3 large-file structural findings)
- Low: **8**
- TODO/FIXME/HACK/XXX comments: **none found**
- Test status during audit: **38 tests passed**
- Important limitation: GUI launch, real MIDI ports, keyboard injection, YouTube/network tools, Demucs, and Basic Pitch were not exercised end-to-end in this environment.

The highest risks are not syntax or test failures. They are output-source misclassification, deterministic folder collisions, Tk access from worker threads, concurrent writers targeting the same files, and incomplete cancellation/shutdown behavior.

No unused production classes were identified. The app class, action/helper mixins, `RuleNote`, `CleanNoteEvent`, `ArrangedEvent`, cancellation classes, and `StaffViewCanvas` all have live call sites. Unused methods/functions are listed under L3.

## High-severity findings

### H1. Generated MIDI can be mistaken for raw transcription

- **Severity:** High
- **Location:** `converter.py:36-44`, `converter.py:231-238`, `converter.py:433-439`
- **Reason:** `latest_midi_file()` must exclude generated variants such as `06_edited_37key.mid`, `06_transposed_37key.mid`, or `chorus_37key.mid`; otherwise a later rebuild could treat one as the original transcription.
- **Suggested fix:** Centralize every derived filename and exclude all derived artifacts when resolving raw MIDI. Prefer recording the raw source path in a manifest rather than inferring it from modification time.
- **Estimated effort:** Small, 1-3 hours including regression tests.

### H2. Same-stem imports/audio files share output folders and can expose stale artifacts

- **Severity:** High
- **Location:** `converter.py:89-97`, `converter.py:100-228`
- **Reason:** Local audio and MIDI folder names are based only on the source stem (`name_local`, `name_midi`). Two unrelated files named `song.mid` or `song.wav` collide. A later run overwrites the working copy and standard stages while older optional artifacts such as `06_edited_37key.mid` can remain and appear selectable for the new source.
- **Suggested fix:** Include a stable hash of the resolved source path and/or file content in the folder name. Store a source manifest and reject/reinitialize a folder whose identity does not match.
- **Estimated effort:** Medium, 0.5-1 day with migration/compatibility handling.

### H3. Tk variables are read from conversion worker threads

- **Severity:** High
- **Location:** `ui/actions/convert_actions.py:226-258`
- **Reason:** `convert_worker()` and `local_audio_convert_worker()` call `.get()` on `demucs_device_var` and `convert_vocals_midi_var` after the background thread starts. Tkinter is not thread-safe; even reads can raise Tcl errors or behave unpredictably during shutdown.
- **Suggested fix:** Capture all Tk values on the main thread before creating the worker and pass plain Python values as thread arguments. Keep all widget/variable access inside main-thread callbacks and queue handlers.
- **Estimated effort:** Small, 2-4 hours including thread-boundary tests.

### H4. Optimization/rebuild jobs can overwrite the same stage files concurrently

- **Severity:** High
- **Location:** `ui/actions/optimizer_actions.py:44-118`, stage writers in `converter.py` and `midi_ai_optimizer.py`
- **Reason:** Optimize and rebuild actions do not share a busy/job lock and do not disable all conflicting controls. Multiple daemon threads can write `01_clean_37key.mid`, `02_piano_arranged_37key.mid`, `03_ai_optimized_37key.mid`, `04_pitch_corrected_37key.mid`, and `05_final_37key.mid` simultaneously. This can produce partially written or internally inconsistent stage chains.
- **Suggested fix:** Add a single per-output-directory job coordinator. Disable conflicting actions while active, write each stage to a temporary sibling, then atomically replace the destination.
- **Estimated effort:** Medium, 1-2 days with concurrency tests.

### H5. Closing/cancelling does not reliably stop all background work

- **Severity:** High
- **Location:** `ui/app.py:166-170`, `ui/actions/convert_actions.py:214-223`, `ui/actions/playback_actions.py:165-172`
- **Reason:** `on_close()` sets the playback stop event but does not cancel `convert_cancel_token`. External MIDI processing creates a cancellation token for UI state but does not pass it into `import_external_midi()`. Pressing Stop during external processing therefore reports cancellation intent while CPU/file work continues. Daemon workers and their child processes may outlive the destroyed Tk root until process exit.
- **Suggested fix:** Cancel the active conversion token during close, make the MIDI pipeline check cancellation between stages, track all worker lifecycles, and wait briefly for termination before destroying the root.
- **Estimated effort:** Medium, 1-2 days.

## Medium-severity findings

### M1. Cached cleanup ignores changed processing options

- **Severity:** Medium
- **Location:** `converter.py:265-279`
- **Reason:** `ensure_clean_37key_midi()` reuses an output solely from modification times, even when non-default `options` are supplied. A changed velocity threshold, range mode, or note limit can silently reuse an artifact created with different settings.
- **Suggested fix:** Persist normalized options in a sidecar manifest and include them in cache validation, or always rebuild when explicit options are provided.
- **Estimated effort:** Medium, 0.5-1 day.

### M2. Circular dependency between rule engine and keyboard module

- **Severity:** Medium
- **Location:** top-level imports in `midi_rule_engine.py`; lazy import in `midi_to_keyboard.py:393-396`
- **Reason:** `midi_rule_engine` imports note-map/range constants from `midi_to_keyboard`, while `midi_to_keyboard.convert_to_37key_midi()` imports the rule engine. The lazy import avoids the current startup crash, but ownership is inverted and fragile.
- **Suggested fix:** Move `DEFAULT_NOTE_MAP`, octave-fit constants, and neutral range helpers into an existing neutral module such as a repurposed `playable_range.py`; have both modules import from it.
- **Estimated effort:** Medium, 0.5-1 day with import tests.

### M3. Two divergent MIDI cleanup/writer implementations exist

- **Severity:** Medium
- **Location:** `midi_rule_engine.py:18-410`, `midi_to_keyboard.py:18-396`
- **Reason:** Both modules define cleanup defaults, range helpers, `quantize_seconds()`, `write_clean_midi()`, and `convert_to_37key_midi()`. The rule-engine writer preserves PPQ/tempo/ticks; the keyboard writer uses a fixed 480 PPQ/120 BPM representation. Future callers can accidentally select different semantics.
- **Suggested fix:** Keep one canonical parser/cleaner/writer in `midi_rule_engine`; remove the duplicate writer and wrapper from `midi_to_keyboard`, leaving that module responsible only for scheduling/keyboard output.
- **Estimated effort:** Medium, 1 day including call-site and timing tests.

### M4. YouTube and local-audio pipelines duplicate roughly 200 lines

- **Severity:** Medium
- **Location:** `converter.py:705-808`, `converter.py:811-914`
- **Reason:** The functions differ mainly in source preparation but duplicate separation, transcription, post-processing, result assembly, and cache handling. Fixes can easily land in only one workflow.
- **Suggested fix:** Extract a shared `_audio_source_to_midi()` orchestration function receiving a source-preparation callback and source label. Extract result assembly into a second helper.
- **Estimated effort:** Medium, 1-2 days with both workflow tests.

### M5. OpenAI failures silently fall back to rule mode

- **Severity:** Medium
- **Location:** `midi_ai_optimizer.py:575-603`
- **Reason:** `optimize_chunk()` catches every exception from the OpenAI path and silently returns rule output. Authentication errors, malformed responses, network failures, and programming errors become indistinguishable from successful AI optimization.
- **Suggested fix:** Catch expected network/validation exceptions separately, log/report the fallback reason, and optionally expose strict vs fallback mode.
- **Estimated effort:** Small, 2-4 hours.

### M6. Empty note outputs lose source PPQ and tempo map

- **Severity:** Medium
- **Location:** `midi_rule_engine.py:329-383`
- **Reason:** Writer context is taken from `notes[0]`. If cleanup intentionally removes every note, the output falls back to 480 PPQ and 120 BPM because no timing context remains.
- **Suggested fix:** Add an optional timing-context parameter or a small MIDI document/context object that survives independently of note count while retaining the existing public wrapper.
- **Estimated effort:** Medium, 0.5-1 day plus empty-file tests.

### M7. Generic parser paths do not support SMF type 2 consistently

- **Severity:** Medium
- **Location:** `midi_rule_engine.py:160-204`, Studio load at `ui/actions/studio_actions.py:27-70`
- **Reason:** External import normalizes type-2 files in its working copy, but generic Open MIDI/Studio/editor paths can still pass type-2 MIDI into merged/iterated readers that reject asynchronous tracks or impose an undefined merge.
- **Suggested fix:** Centralize type-2 policy in the MIDI loader: reject with a clear message or normalize to an explicit working representation before any consumer reads it.
- **Estimated effort:** Medium, 0.5-1 day.

### M8. Processed MIDI discards channels, tracks, controllers, programs, and pedal semantics

- **Severity:** Medium
- **Location:** `midi_rule_engine.py:160-204`, `midi_rule_engine.py:329-383`
- **Reason:** The parser reduces MIDI to note pairs and the writer emits one note track on channel 0 plus tempo events. Sustain pedal, program changes, channel identity, track names, and other performance metadata are lost. Start ticks are now preserved, but note-off musical meaning can still differ when sustain is present.
- **Suggested fix:** Document this as the 37-key transformation contract. If preservation is desired, introduce a MIDI document model carrying non-note events and channel/track identity separately from `RuleNote`.
- **Estimated effort:** Large, 3-7 days.

### M9. MIDI Studio scheduling has up to roughly one polling interval of jitter

- **Severity:** Medium
- **Location:** `ui/actions/studio_actions.py:224-258`
- **Reason:** Studio checks due events every 50 ms and sends all overdue messages in a burst. This can audibly smear dense passages and differs from the more precise keyboard scheduler.
- **Suggested fix:** Schedule the next callback from the next event deadline, using a short bounded interval only as a safety check. Keep UI refresh cadence separate from MIDI dispatch cadence.
- **Estimated effort:** Medium, 1 day with a fake-clock test.

### M10. Staff View eagerly parses/renders even while Piano Roll is active

- **Severity:** Medium
- **Location:** `ui/actions/studio_actions.py:27-70`, `ui/panels/staff_view.py:42-76`
- **Reason:** Every Studio load calls `staff_view.load_midi()` although Piano Roll is the default. Staff View draws two canvas items per note plus staff lines across the full song width. Large commercial MIDI files can cause slow tab opening and high Tk item/memory usage before Staff View is requested.
- **Suggested fix:** Lazy-load Staff View on first selection, cache the parsed notes, and virtualize rendering to the visible horizontal range for large files.
- **Estimated effort:** Medium, 1-2 days.

### M11. Staff note hit-testing is linear in total note count

- **Severity:** Medium
- **Location:** `ui/panels/staff_view.py:88-108`
- **Reason:** Every click scans all note positions in Python. Thousands of notes are acceptable, but large multitrack MIDI can make interaction lag.
- **Suggested fix:** Use Canvas item tags/current item IDs or a time-bucket/spatial index to resolve a clicked note directly.
- **Estimated effort:** Small, 2-4 hours.

### M12. Analysis repeatedly reparses the same MIDI files

- **Severity:** Medium
- **Location:** `midi_analysis.py:36-54`, `midi_analysis.py:127-169`; repeated `inspect_midi_file()` calls in `converter.py:100-228`
- **Reason:** Reports open and parse raw/clean/arranged/final files independently for each metric. External processing also calls full metadata inspection repeatedly merely to check whether pitches are outside the map. This creates avoidable O(stages × file size) work.
- **Suggested fix:** Parse once per file into a lightweight analysis result, cache by path/mtime, and use a dedicated cheap range-check helper during processing.
- **Estimated effort:** Medium, 1 day.

### M13. Broad exception handling obscures actionable failures

- **Severity:** Medium
- **Location:** multiple UI action modules; pylint reported broad catches in conversion, editor, optimizer, playback, Studio, CLI, and `ui/app.py`
- **Reason:** UI boundaries reasonably need a final catch, but many catches reduce errors to `str(exc)` without traceback/log context. Several Studio cleanup catches silently `pass`. Diagnosis of MIDI backend, Tcl, file, or device failures becomes difficult.
- **Suggested fix:** Catch expected exceptions locally, reserve one broad boundary catch per worker, and log traceback/context before presenting a concise user message. Keep silent cleanup catches narrowly scoped and documented.
- **Estimated effort:** Medium, 1-2 days.

### M14. Subprocess ownership is not exception-safe for unexpected parent exceptions

- **Severity:** Medium
- **Location:** `tools.py:151-190`, `tools.py:208-260`
- **Reason:** Cancellation and timeout paths terminate child processes, but an unexpected exception or application shutdown between `Popen` and normal completion can leave a child alive. Pylint also flags the process allocations as resource ownership concerns.
- **Suggested fix:** In `finally`, if the child is still running and the operation is abandoning it, terminate/wait. Encapsulate process lifecycle in one helper/context manager.
- **Estimated effort:** Medium, 0.5-1 day.

### M15. Dependency installation is not reproducible across common environments

- **Severity:** Medium
- **Location:** `requirements.txt`
- **Reason:** Most dependencies are unpinned, while Torch is pinned specifically to CUDA 12.1 and an extra index. CPU-only and non-compatible GPU systems are poorly served, and future unpinned releases can break the application.
- **Suggested fix:** Separate base, CPU, and CUDA requirement sets; pin tested direct dependencies; document supported Python/platform combinations; add a lock/constraints file.
- **Estimated effort:** Medium, 1 day plus clean-environment verification.

### M16. Important integration paths lack automated coverage

- **Severity:** Medium
- **Location:** test suite overall
- **Reason:** Unit tests cover MIDI transformations well, but there is no real Tk construction test, no mocked end-to-end YouTube/local-audio orchestration test, no cancellation/shutdown test, no concurrent-writer test, and no Studio scheduler timing test. The environment's Tcl issue also means UI launch has not been verified here.
- **Suggested fix:** Add headless/fake-Tk panel composition tests, mocked external-tool workflow tests, fake-clock scheduler tests, and cancellation/concurrency tests.
- **Estimated effort:** Large, 3-5 days.

## Low-severity findings

### L1. Unused imports

- **Severity:** Low
- **Location:** `playable_range.py:1-2`, `ui/panels/midi_editor_panel.py:1`, `ui/panels/optimizer_panel.py:1`
- **Reason:** `math`, `typing.Optional`, and two `tkinter as tk` imports are unused. Confirmed by AST scan and pylint.
- **Suggested fix:** Remove them if the files remain.
- **Estimated effort:** Trivial, under 15 minutes.

### L2. Obsolete UI compatibility modules remain after the tab refactor

- **Severity:** Low
- **Location:** `ui/panels/converter_tab.py`, `ui/panels/midi_studio_tab.py`, `ui/panels/optimizer_panel.py`
- **Reason:** No repository call sites import these builders. The current app composes tabs through `ui/panels/main_panel.py`. `optimizer_panel.py` also duplicates cleanup/key-transpose UI.
- **Suggested fix:** Delete after confirming no external consumers rely on undocumented imports. If compatibility is intentional, add deprecation comments/tests and a removal date.
- **Estimated effort:** Small, 1-2 hours including import/search verification.

### L3. Dead compatibility functions and unused helpers

- **Severity:** Low
- **Location:** `ui/panels/midi_panel.py:107`, `midi_ai_optimizer.py:486`, `midi_to_keyboard.py:293`, `midi_to_keyboard.py:321`, `midi_to_keyboard.py:357`
- **Reason:** `build_midi_panel`, `arrange_piano_cover_midi`, `fit_note_for_37key_midi`, `group_37key_events`, and the keyboard module's writer have no non-definition call sites. Some underlying helper functions remain covered by tests, so only the wrappers/helpers named here are dead candidates.
- **Suggested fix:** Remove after one release/deprecation pass, or add explicit public-API documentation if they must remain.
- **Estimated effort:** Small, 2-4 hours.

### L4. `playable_range.py` is completely unreferenced

- **Severity:** Low
- **Location:** `playable_range.py`
- **Reason:** No Python file imports it. It also contains unused imports. It may be an abandoned predecessor to range logic now duplicated in `midi_to_keyboard` and `midi_rule_engine`.
- **Suggested fix:** Either delete it after external-consumer confirmation or repurpose it as the neutral home for shared note-map/range constants to resolve M2/M3.
- **Estimated effort:** Small, 1-3 hours.

### L5. `PROJECT_INDEX.md` is stale and encoding-damaged

- **Severity:** Low
- **Location:** `PROJECT_INDEX.md`
- **Reason:** It references obsolete paths/names such as `ui_app.py` and the old MIDI Studio tab, and its text is visibly mojibake. It is more misleading than useful after the UI refactor.
- **Suggested fix:** Regenerate it in UTF-8 from the current package structure or delete it in favor of the maintained README.
- **Estimated effort:** Small, 1-2 hours.

### L6. Naming is inconsistent across code and UI

- **Severity:** Low
- **Location:** `YoutubeMidiApp`, UI labels, source result keys, constants across converter/processing modules
- **Reason:** `YoutubeMidiApp` uses “Youtube” rather than “YouTube”; source labels alternate between `Final`, `Final 37-Key MIDI`, `Raw MIDI`, and `Imported MIDI`; filenames/constants are owned by multiple modules. This increases mapping code in `ui/helpers/selection.py`.
- **Suggested fix:** Define canonical internal enum/key names and separate user-facing labels. Rename the app class in a backward-compatible pass.
- **Estimated effort:** Medium, 0.5-1 day.

### L7. Unknown queue message types are silently ignored

- **Severity:** Low
- **Location:** `ui/helpers/queue_handlers.py:15-33`
- **Reason:** A typo or newly added worker event with no handler disappears without a log entry, leaving UI state potentially stuck.
- **Suggested fix:** Log or assert unknown message kinds in development builds and include a safe generic error path.
- **Estimated effort:** Trivial, under 1 hour.

### L8. No shared formatting/lint configuration

- **Severity:** Low
- **Location:** repository root and multiple modules
- **Reason:** There is no `pyproject.toml`/formatter/linter configuration. Style varies in line length, compactness, import ordering, blank lines, type annotations, and UI grid formatting. Large mixin attribute surfaces are typed mostly as `Any`.
- **Suggested fix:** Add a minimal Ruff/Black or pylint/isort configuration, run it incrementally, and avoid mixing formatting cleanup with behavior changes.
- **Estimated effort:** Medium, 0.5-1 day for initial cleanup.

## Large files that should be split

### `converter.py` — 914 lines

- **Severity:** Medium
- **Reason:** Combines output naming, external MIDI import, stage rebuilds, result discovery, caching, external audio commands, and two duplicated orchestration workflows.
- **Suggested fix:** Split into existing-domain modules: keep orchestration in `converter.py`; move result/path/cache helpers near analysis/selection concerns; extract external MIDI orchestration; consolidate audio workflow helpers.
- **Estimated effort:** Large, 2-4 days.

### `midi_ai_optimizer.py` — 867 lines

- **Severity:** Medium
- **Reason:** Combines legacy arrangement, melody extraction, OpenAI transport/schema validation, rule optimization, key detection, pitch correction, final smoothing, and orchestration.
- **Suggested fix:** Move arrangement behavior to existing `midi_piano_arranger.py`; keep AI transport/optimizer here; move pitch/key/final smoothing into focused existing MIDI modules or a new dedicated processing module only if no suitable existing owner remains.
- **Estimated effort:** Large, 2-4 days.

### `midi_to_keyboard.py` — 688 lines

- **Severity:** Medium
- **Reason:** Contains map constants, cleanup/range logic, a second writer, preview formatting, schedule construction, and keyboard execution.
- **Suggested fix:** Remove cleanup/writer duplication and leave note-to-key mapping plus scheduling/execution. Shared range constants can move to repurposed `playable_range.py`.
- **Estimated effort:** Medium, 1-2 days.

## Files that can probably be deleted

Deletion requires a final check for external consumers, because the repository does not publish an explicit API compatibility policy.

| Confidence | File | Reason |
|---|---|---|
| High | `ui/panels/converter_tab.py` | Compatibility builder has no internal imports/callers; current layout is composed by `main_panel.py`. |
| High | `ui/panels/midi_studio_tab.py` | Three-line compatibility wrapper with no internal caller. |
| High | `ui/panels/optimizer_panel.py` | Unused old panel; duplicates controls now in `cleanup_panel.py`. |
| High | `PROJECT_INDEX.md` | Stale, encoding-damaged, and contradicted by current README/layout. Regeneration is preferable if an index is desired. |
| Medium | `playable_range.py` | Completely unused, but it may be better repurposed to break the MIDI module cycle. |

Files that should **not** be deleted:

- `youtube_to_midi.py`: still the minimal GUI launcher.
- Empty package `__init__.py` files: still define/import-stabilize package boundaries.
- `TIMING_AUDIT_REPORT.md`: now explicitly marked as a historical pre-fix audit and links to the fixed comparison.
- Test files: all are discovered and currently pass.

## Functions/logic that should move into existing modules

1. Move shared note-map/octave constants out of `midi_to_keyboard` into a neutral existing module (`playable_range.py` is the natural candidate), breaking the circular import.
2. Move/remove legacy piano-cover arrangement functions from `midi_ai_optimizer.py`; `midi_piano_arranger.py` should own arrangement behavior.
3. Remove the cleaning/writer compatibility layer from `midi_to_keyboard.py`; `midi_rule_engine.py` should remain canonical for MIDI note parsing and serialization.
4. Extract duplicated YouTube/local result assembly into one private helper inside `converter.py` before considering new files.
5. Centralize generated MIDI filename classification so converter discovery and UI selection cannot drift apart.

## Timing-specific review

- The cumulative delta-rounding bug is fixed in the current working tree. `midi_rule_engine.write_clean_midi()` emits deltas from absolute ticks.
- The direct 100-note variable-tempo round trip reports 0-tick start/end error; the required bound is <=1 tick.
- Remaining intentional changes are Piano Arranger onset grouping, Final quantization/overlap shifts, playback speed/range transforms, repeated-note merging, and chord staggering.
- Remaining risks are the empty-output timing-context loss (M6), Studio's 50 ms dispatch cadence (M9), type-2 inconsistency (M7), and loss of sustain/controller semantics (M8).

## Recommended order of work

1. Fix H1-H5 before additional feature work.
2. Consolidate generated-file identity and cache manifests (H1, H2, M1).
3. Establish one job/cancellation coordinator (H3-H5).
4. Break the MIDI import cycle and remove the duplicate writer/cleanup path (M2, M3).
5. Consolidate duplicated audio orchestration and split the three large modules (M4 and large-file section).
6. Delete/deprecate obsolete UI wrappers and repair documentation.
7. Add integration coverage before deeper scheduling or metadata-preservation changes.
