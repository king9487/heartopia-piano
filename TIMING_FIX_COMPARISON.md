# MIDI Timing Fix: Before/After Comparison

Generated: 2026-07-03

## Result

Absolute MIDI ticks are now canonical. `RuleNote` retains `start_tick`, `end_tick`, PPQ, and the source tempo map. Writers emit deltas from absolute tick targets, so no rounding residual is discarded.

## Required round-trip regression

Test path:

```text
Imported MIDI -> Cleanup -> Export -> Re-import
```

Fixture: 100 notes, 960 PPQ, irregular tick positions, and a tempo change.

| Measurement | Before | After |
|---|---:|---:|
| Note count | vulnerable to parser/channel ambiguity | 100 -> 100 |
| Maximum start error | cumulative; control reached 388 ms | 0 ticks |
| Maximum end error | cumulative | 0 ticks |
| PPQ | forced to 480 | preserved at 960 |
| Tempo map | replaced with 120 BPM | preserved exactly |

The enforced regression threshold is `maximum timing error <= 1 tick`; the observed result is **0 ticks**.

## Full processing control

The existing fully processed accompaniment used by the timing audit was regenerated in a temporary directory. Each file was compared with its stage's intended in-memory timing immediately before serialization.

| Stage | Notes expected | Notes written | Maximum serialization error |
|---|---:|---:|---:|
| Cleanup | 3,102 | 3,102 | 0 ticks |
| Piano Arranger | 2,243 | 2,243 | 0 ticks |
| AI Optimizer (Rule) | 2,240 | 2,240 | 0 ticks |
| Pitch Correction | 2,235 | 2,235 | 0 ticks |
| Final | 2,235 | 2,235 | 0 ticks |

## Intentional timing changes that remain

- Piano Arranger may move accompaniment notes to the selected onset-group tick.
- AI/OpenAI output may change timing only when returned `start_ms` differs explicitly; otherwise source tick metadata is restored.
- Final smoothing quantizes starts/durations and shifts same-pitch overlaps. Every start change is recorded in the note's `timing_changes` metadata during smoothing.
- Playback speed, range clipping, repeated-note merging, and chord delay remain playback-only scheduling behavior.

No generated stage independently rounds delta seconds anymore.
