"""Deterministic, role-aware range optimization for Heartopia MIDI files.

The scoring layer is intentionally separated from candidate generation and note
transformation.  A future learned scorer can therefore consume the same
``RangeAnalysis`` and ``CandidateResult`` objects without changing the MIDI
pipeline.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from math import exp
from statistics import median
from typing import Callable, Iterable, Mapping, Sequence


MELODY = "melody"
BASS = "bass"
INNER = "inner"
RANGE_OPTIMIZATION_REPORT_NAME = "range_optimization_report.json"


@dataclass(frozen=True)
class RegisterSummary:
    count: int = 0
    minimum: int | None = None
    maximum: int | None = None
    median: float | None = None
    percentile_10: int | None = None
    percentile_90: int | None = None


@dataclass
class RangeAnalysis:
    note_count: int
    playable_low: int
    playable_high: int
    preferred_melody_low: int
    preferred_melody_high: int
    note_histogram: dict[int, int]
    pitch_class_histogram: dict[int, int]
    note_density: float
    peak_onset_density: int
    melody_range: RegisterSummary
    bass_range: RegisterSummary
    main_register: RegisterSummary
    chord_size_distribution: dict[int, int]
    chord_count: int
    outside_count: int
    outside_percentage: float
    below_count: int
    above_count: int
    roles: tuple[str, ...] = field(repr=False)
    onset_groups: tuple[tuple[int, ...], ...] = field(repr=False)

    def to_dict(self) -> dict:
        result = asdict(self)
        result.pop("roles", None)
        result.pop("onset_groups", None)
        return result


@dataclass(frozen=True)
class CandidateStrategy:
    name: str
    description: str
    whole_shift: int = 0
    melody_shift: int = 0
    bass_shift: int = 0
    fold_overflow: bool = False


@dataclass
class ScoreBreakdown:
    playable: float
    melody_preserved: float
    chord_quality: float
    bass_preserved: float
    change_cost: float
    score: float

    def to_dict(self) -> dict:
        return {key: round(value, 2) for key, value in asdict(self).items()}


@dataclass
class CandidateResult:
    strategy: CandidateStrategy
    notes: list
    transformed_pitches: tuple[int | None, ...]
    score: ScoreBreakdown
    retained_notes: int
    dropped_notes: int

    def to_dict(self) -> dict:
        return {
            "strategy": asdict(self.strategy),
            "metrics": self.score.to_dict(),
            "retained_notes": self.retained_notes,
            "dropped_notes": self.dropped_notes,
        }


@dataclass
class OptimizationResult:
    notes: list
    analysis: RangeAnalysis
    chosen: CandidateResult
    candidates: list[CandidateResult]
    explanation: str

    def to_dict(self) -> dict:
        return {
            "analysis": self.analysis.to_dict(),
            "chosen_strategy": self.chosen.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "explanation": self.explanation,
        }


def _percentile(values: Sequence[int], proportion: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * proportion)
    return ordered[index]


def _register(values: Iterable[int]) -> RegisterSummary:
    pitches = list(values)
    if not pitches:
        return RegisterSummary()
    return RegisterSummary(
        count=len(pitches),
        minimum=min(pitches),
        maximum=max(pitches),
        median=round(float(median(pitches)), 2),
        percentile_10=_percentile(pitches, 0.10),
        percentile_90=_percentile(pitches, 0.90),
    )


def _group_onsets(notes: Sequence, tolerance_ticks: int) -> tuple[tuple[int, ...], ...]:
    if not notes:
        return ()
    indexed = sorted(range(len(notes)), key=lambda i: (notes[i].start_tick, notes[i].note))
    groups: list[list[int]] = []
    anchor = None
    for index in indexed:
        tick = notes[index].start_tick
        if anchor is None or tick - anchor > tolerance_ticks:
            groups.append([])
            anchor = tick
        groups[-1].append(index)
    return tuple(tuple(group) for group in groups)


def _detect_roles(notes: Sequence, groups: Sequence[Sequence[int]]) -> tuple[str, ...]:
    roles = [INNER] * len(notes)
    previous_melody = None
    previous_bass = None
    for group in groups:
        if not group:
            continue
        # A continuation bias prevents a one-note accompaniment spike from
        # repeatedly stealing the melody/bass role.
        def melody_rank(index: int) -> tuple[float, int, int]:
            pitch = notes[index].note
            continuity = 0 if previous_melody is None else -abs(pitch - previous_melody) * 0.35
            return pitch + continuity, notes[index].velocity, notes[index].end_tick - notes[index].start_tick

        melody_index = max(group, key=melody_rank)
        previous_melody = notes[melody_index].note
        roles[melody_index] = MELODY

        if len(group) > 1:
            def bass_rank(index: int) -> tuple[float, int, int]:
                pitch = notes[index].note
                continuity = 0 if previous_bass is None else abs(pitch - previous_bass) * 0.2
                return pitch + continuity, -notes[index].velocity, index

            bass_index = min((i for i in group if i != melody_index), key=bass_rank)
            previous_bass = notes[bass_index].note
            roles[bass_index] = BASS
    return tuple(roles)


def analyze_note_distribution(
    notes: Sequence,
    playable_low: int,
    playable_high: int,
    onset_tolerance_ticks: int | None = None,
    preferred_melody_low: int | None = None,
    preferred_melody_high: int | None = None,
) -> RangeAnalysis:
    """Measure register, density, roles, chord sizes, and range overflow."""
    notes = list(notes)
    ppq = notes[0].ppq if notes else 480
    tolerance = onset_tolerance_ticks if onset_tolerance_ticks is not None else max(1, ppq // 32)
    groups = _group_onsets(notes, tolerance)
    roles = _detect_roles(notes, groups)
    pitches = [note.note for note in notes]
    melody = [notes[i].note for i, role in enumerate(roles) if role == MELODY]
    bass = [notes[i].note for i, role in enumerate(roles) if role == BASS]
    chord_sizes = Counter(len(group) for group in groups if len(group) > 1)
    below = sum(pitch < playable_low for pitch in pitches)
    above = sum(pitch > playable_high for pitch in pitches)
    if notes:
        duration = max(note.end for note in notes) - min(note.start for note in notes)
        density = len(notes) / max(duration, 0.001)
    else:
        density = 0.0
    return RangeAnalysis(
        note_count=len(notes),
        playable_low=playable_low,
        playable_high=playable_high,
        preferred_melody_low=(
            playable_low if preferred_melody_low is None else preferred_melody_low
        ),
        preferred_melody_high=(
            playable_high if preferred_melody_high is None else preferred_melody_high
        ),
        note_histogram=dict(sorted(Counter(pitches).items())),
        pitch_class_histogram=dict(sorted(Counter(pitch % 12 for pitch in pitches).items())),
        note_density=round(density, 3),
        peak_onset_density=max((len(group) for group in groups), default=0),
        melody_range=_register(melody),
        bass_range=_register(bass),
        main_register=detect_main_register(pitches),
        chord_size_distribution=dict(sorted(chord_sizes.items())),
        chord_count=sum(chord_sizes.values()),
        outside_count=below + above,
        outside_percentage=round(100.0 * (below + above) / max(1, len(notes)), 2),
        below_count=below,
        above_count=above,
        roles=roles,
        onset_groups=groups,
    )


def detect_main_register(pitches: Iterable[int], coverage: float = 0.80) -> RegisterSummary:
    """Return the narrowest pitch window containing the requested note mass."""
    values = sorted(int(pitch) for pitch in pitches)
    if not values:
        return RegisterSummary()
    window_size = max(1, round(len(values) * min(1.0, max(0.1, coverage))))
    overall_median = median(values)
    start = min(
        range(len(values) - window_size + 1),
        key=lambda i: (
            values[i + window_size - 1] - values[i],
            abs(values[i] - overall_median),
        ),
    )
    return _register(values[start : start + window_size])


def _coverage(notes: Sequence, low: int, high: int, shift: int, roles=None, role=None) -> int:
    return sum(
        low <= note.note + shift <= high
        for i, note in enumerate(notes)
        if role is None or roles[i] == role
    )


def _best_shifts(
    notes: Sequence, low: int, high: int, roles=None, role=None, limit=4,
    octave_only: bool = False,
) -> list[int]:
    candidates = range(-36, 37, 12) if octave_only else range(-36, 37)
    ranked = sorted(
        candidates,
        key=lambda shift: (_coverage(notes, low, high, shift, roles, role), -abs(shift), shift % 12 == 0),
        reverse=True,
    )
    selected = [0]
    for shift in ranked:
        if shift not in selected:
            selected.append(shift)
        if len(selected) >= limit:
            break
    return selected


def generate_candidate_strategies(
    notes: Sequence, analysis: RangeAnalysis
) -> list[CandidateStrategy]:
    """Generate a compact, data-dependent strategy search space."""
    low, high = analysis.playable_low, analysis.playable_high
    strategies = [
        CandidateStrategy("keep_original", "Keep pitches unchanged and omit unplayable overflow."),
        CandidateStrategy("shift_overflow", "Move only overflow notes by octaves.", fold_overflow=True),
    ]
    whole_shifts = _best_shifts(notes, low, high, limit=5)
    melody_shifts = _best_shifts(
        notes,
        analysis.preferred_melody_low,
        analysis.preferred_melody_high,
        analysis.roles,
        MELODY,
        limit=4,
        octave_only=True,
    )
    bass_shifts = _best_shifts(
        notes, low, high, analysis.roles, BASS, limit=4, octave_only=True
    )
    for shift in whole_shifts:
        if shift:
            strategies.append(CandidateStrategy(
                f"transpose_{shift:+d}", f"Transpose the whole song by {shift:+d} semitones.", whole_shift=shift
            ))
            strategies.append(CandidateStrategy(
                f"transpose_{shift:+d}_overflow", f"Transpose by {shift:+d}, then octave-fit residual overflow.",
                whole_shift=shift, fold_overflow=True
            ))
    for shift in melody_shifts:
        if shift:
            strategies.append(CandidateStrategy(
                f"melody_{shift:+d}", f"Shift only the detected melody by {shift:+d} semitones.",
                melody_shift=shift,
            ))
            strategies.append(CandidateStrategy(
                f"melody_{shift:+d}_overflow",
                f"Shift melody by {shift:+d} semitones, then octave-fit residual overflow.",
                melody_shift=shift, fold_overflow=True,
            ))
    for shift in bass_shifts:
        if shift:
            strategies.append(CandidateStrategy(
                f"bass_{shift:+d}", f"Shift only the detected bass by {shift:+d} semitones.",
                bass_shift=shift,
            ))
            strategies.append(CandidateStrategy(
                f"bass_{shift:+d}_overflow",
                f"Shift bass by {shift:+d} semitones, then octave-fit residual overflow.",
                bass_shift=shift, fold_overflow=True,
            ))
    for melody_shift in melody_shifts[:3]:
        for bass_shift in bass_shifts[:3]:
            if melody_shift or bass_shift:
                strategies.append(CandidateStrategy(
                    f"melody_{melody_shift:+d}_bass_{bass_shift:+d}",
                    "Independently place the melody and bass; omit residual overflow.",
                    melody_shift=melody_shift, bass_shift=bass_shift,
                ))
                strategies.append(CandidateStrategy(
                    f"melody_{melody_shift:+d}_bass_{bass_shift:+d}_overflow",
                    "Independently place melody and bass, then fit remaining overflow by octave.",
                    melody_shift=melody_shift, bass_shift=bass_shift,
                    fold_overflow=True,
                ))
    unique = {}
    for strategy in strategies:
        key = (strategy.whole_shift, strategy.melody_shift, strategy.bass_shift, strategy.fold_overflow)
        unique.setdefault(key, strategy)
    return list(unique.values())


def _fold_pitch(pitch: int, low: int, high: int) -> int | None:
    candidates = [pitch + (12 * octave) for octave in range(-8, 9)]
    playable = [candidate for candidate in candidates if low <= candidate <= high]
    return min(playable, key=lambda value: (abs(value - pitch), value)) if playable else None


def _transform_pitches(
    notes: Sequence, analysis: RangeAnalysis, strategy: CandidateStrategy
) -> tuple[int | None, ...]:
    transformed = []
    for index, note in enumerate(notes):
        pitch = note.note + strategy.whole_shift
        if analysis.roles[index] == MELODY:
            pitch += strategy.melody_shift
        elif analysis.roles[index] == BASS:
            pitch += strategy.bass_shift
        if not analysis.playable_low <= pitch <= analysis.playable_high:
            pitch = _fold_pitch(pitch, analysis.playable_low, analysis.playable_high) if strategy.fold_overflow else None
        transformed.append(pitch)
    return tuple(transformed)


def _sequence_quality(notes, pitches, indices) -> float:
    kept = [index for index in indices if pitches[index] is not None]
    if not indices:
        return 100.0
    retention = len(kept) / len(indices)
    if len(kept) < 2:
        return retention * 100.0
    continuity = []
    previous = kept[0]
    for index in kept[1:]:
        original_interval = notes[index].note - notes[previous].note
        new_interval = pitches[index] - pitches[previous]
        error = abs(new_interval - original_interval)
        continuity.append(exp(-error / 8.0))
        previous = index
    return 100.0 * retention * (0.55 + 0.45 * sum(continuity) / len(continuity))


def _chord_quality(notes, pitches, groups) -> float:
    chords = [group for group in groups if len(group) > 1]
    if not chords:
        return 100.0
    qualities = []
    for group in chords:
        kept = [index for index in group if pitches[index] is not None]
        retention = len(kept) / len(group)
        if not kept:
            qualities.append(0.0)
            continue
        unique = len({pitches[index] for index in kept}) / len(kept)
        ordered = sorted(kept, key=lambda i: notes[i].note)
        crossings = sum(pitches[a] > pitches[b] for a, b in zip(ordered, ordered[1:]))
        order = 1.0 - crossings / max(1, len(ordered) - 1)
        # Compare relative interval classes, not absolute pitch classes.  This
        # correctly treats a whole-song key transpose as harmonically intact.
        before_pairs = Counter(
            (notes[b].note - notes[a].note) % 12
            for position, a in enumerate(group)
            for b in group[position + 1 :]
        )
        after_pairs = Counter(
            (pitches[b] - pitches[a]) % 12
            for position, a in enumerate(kept)
            for b in kept[position + 1 :]
        )
        pair_total = sum(before_pairs.values())
        harmony = (
            sum((before_pairs & after_pairs).values()) / pair_total
            if pair_total else 1.0
        )
        span = max(pitches[index] for index in kept) - min(pitches[index] for index in kept)
        spacing = exp(-max(0, 4 - span) / 4.0) if len(kept) > 2 else 1.0
        qualities.append(retention * (0.25 * unique + 0.30 * order + 0.35 * harmony + 0.10 * spacing))
    return 100.0 * sum(qualities) / len(qualities)


def score_strategy(
    notes: Sequence,
    analysis: RangeAnalysis,
    strategy: CandidateStrategy,
    weights: Mapping[str, float] | None = None,
) -> CandidateResult:
    """Transform and score one strategy. Replaceable by a future ML scorer."""
    weights = dict(weights or {
        "playable": 0.25,
        "melody": 0.35,
        "chord": 0.25,
        "bass": 0.15,
    })
    pitches = _transform_pitches(notes, analysis, strategy)
    retained = sum(pitch is not None for pitch in pitches)
    playable = 100.0 * retained / max(1, len(notes))
    melody_indices = [i for i, role in enumerate(analysis.roles) if role == MELODY]
    bass_indices = [i for i, role in enumerate(analysis.roles) if role == BASS]
    melody = _sequence_quality(notes, pitches, melody_indices)
    kept_melody = [i for i in melody_indices if pitches[i] is not None]
    if kept_melody:
        preferred_coverage = sum(
            analysis.preferred_melody_low
            <= pitches[i]
            <= analysis.preferred_melody_high
            for i in kept_melody
        ) / len(kept_melody)
        melody *= 0.75 + (0.25 * preferred_coverage)
    bass = _sequence_quality(notes, pitches, bass_indices)
    chord = _chord_quality(notes, pitches, analysis.onset_groups)
    changed = [abs(pitches[i] - notes[i].note) for i in range(len(notes)) if pitches[i] is not None]
    change_cost = min(100.0, sum(changed) / max(1, len(notes)) * 2.0)
    raw = (
        weights["playable"] * playable
        + weights["melody"] * melody
        + weights["chord"] * chord
        + weights["bass"] * bass
    )
    # A light regularizer breaks near-ties in favor of less intervention; it
    # cannot overpower a materially better melody or chord result.
    score = max(0.0, raw - 0.04 * change_cost)
    transformed_notes = []
    for index, pitch in enumerate(pitches):
        if pitch is None:
            continue
        note = notes[index]
        transformed_notes.append(type(note)(
            start_tick=note.start_tick, end_tick=note.end_tick, ppq=note.ppq,
            tempo_map=note.tempo_map, original_note=note.original_note,
            note=pitch, velocity=note.velocity, octave_shift=pitch - note.original_note,
        ))
    return CandidateResult(
        strategy=strategy,
        notes=transformed_notes,
        transformed_pitches=pitches,
        score=ScoreBreakdown(playable, melody, chord, bass, change_cost, score),
        retained_notes=retained,
        dropped_notes=len(notes) - retained,
    )


def choose_best_strategy(candidates: Sequence[CandidateResult]) -> CandidateResult:
    if not candidates:
        raise ValueError("No range strategies were scored")
    return max(
        candidates,
        key=lambda item: (
            item.score.score,
            item.score.melody_preserved,
            item.score.chord_quality,
            -item.score.change_cost,
        ),
    )


def explain_choice(chosen: CandidateResult, analysis: RangeAnalysis) -> str:
    score = chosen.score
    overflow = (
        f"{analysis.outside_percentage:.1f}% of {analysis.note_count} notes began outside "
        f"the playable range"
    )
    return (
        f"{chosen.strategy.name} was selected because {overflow}. "
        f"It keeps {score.playable:.1f}% playable while preserving an estimated "
        f"{score.melody_preserved:.1f}% of melody continuity and {score.chord_quality:.1f}% "
        f"of chord quality (overall score {score.score:.1f}). "
        f"{chosen.strategy.description}"
    )


def optimize_note_range(
    notes: Sequence,
    playable_low: int,
    playable_high: int,
    scorer: Callable[[Sequence, RangeAnalysis, CandidateStrategy], CandidateResult] = score_strategy,
    preferred_melody_low: int | None = None,
    preferred_melody_high: int | None = None,
) -> OptimizationResult:
    """Analyze, search, score, and apply the best deterministic strategy."""
    notes = list(notes)
    analysis = analyze_note_distribution(
        notes,
        playable_low,
        playable_high,
        preferred_melody_low=preferred_melody_low,
        preferred_melody_high=preferred_melody_high,
    )
    strategies = generate_candidate_strategies(notes, analysis)
    candidates = [scorer(notes, analysis, strategy) for strategy in strategies]
    chosen = choose_best_strategy(candidates)
    return OptimizationResult(
        notes=chosen.notes,
        analysis=analysis,
        chosen=chosen,
        candidates=sorted(candidates, key=lambda item: item.score.score, reverse=True),
        explanation=explain_choice(chosen, analysis),
    )
