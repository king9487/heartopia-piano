import math
from typing import List, Dict, Any, Optional

def note_to_midi(note_name: str) -> int:
    """
    Converts a note name (e.g., 'C4', 'C#4', 'Bb3') to a MIDI pitch number.
    Standard: C4 = 60.
    """
    notes = {
        'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3,
        'E': 4, 'F': 5, 'F#': 6, 'GB': 6, 'G': 7, 'G#': 8,
        'AB': 8, 'A': 9, 'A#': 10, 'BB': 10, 'B': 11
    }
    
    name = note_name.upper()
    
    # Handle accidentals: checking for '#' or 'B' (flat)
    if len(name) > 1 and (name[1] == '#' or name[1] == 'B'):
        # Check if it's a valid 2-char note name like C# or BB (Bb)
        if name[:2] in notes:
            base_name = name[:2]
            octave_str = name[2:]
        else:
            # Fallback for single char note with digit like B3
            base_name = name[:1]
            octave_str = name[1:]
    else:
        base_name = name[:1]
        octave_str = name[1:]
    
    if base_name not in notes:
        raise ValueError(f"Invalid note name: {base_name}")
    
    try:
        octave = int(octave_str)
    except ValueError:
        raise ValueError(f"Invalid octave: {octave_str}")
        
    return (octave + 1) * 12 + notes[base_name]

def fold_note_into_range(pitch: int, min_pitch: int, max_pitch: int) -> int:
    """
    Transposes a pitch by octaves so it falls within [min_pitch, max_pitch].
    If it's impossible to fit (range < 12), it returns the closest octave.
    """
    if min_pitch > max_pitch:
        min_pitch, max_pitch = max_pitch, min_pitch
        
    folded_pitch = pitch
    
    # Move up if too low
    while folded_pitch < min_pitch:
        if folded_pitch + 12 > max_pitch:
            # If moving up once more puts it above max_pitch,
            # we choose the one that is closer to the range or stays in it.
            if abs((folded_pitch + 12) - max_pitch) < abs(folded_pitch - min_pitch):
                folded_pitch += 12
            break
        folded_pitch += 12
        
    # Move down if too high
    while folded_pitch > max_pitch:
        if folded_pitch - 12 < min_pitch:
            # Check which is closer
            if abs(folded_pitch - max_pitch) > abs((folded_pitch - 12) - min_pitch):
                folded_pitch -= 12
            break
        folded_pitch -= 12
        
    return folded_pitch

def group_notes_by_time(notes: List[Dict[str, Any]], tolerance: float = 0.05) -> List[List[Dict[str, Any]]]:
    """
    Groups notes that start within a certain tolerance of each other.
    Each note should be a dict with at least 'start_time' and 'pitch'.
    """
    if not notes:
        return []
    
    # Sort notes by start time
    sorted_notes = sorted(notes, key=lambda x: x['start_time'])
    
    groups = []
    current_group = [sorted_notes[0]]
    
    for i in range(1, len(sorted_notes)):
        if sorted_notes[i]['start_time'] - current_group[0]['start_time'] <= tolerance:
            current_group.append(sorted_notes[i])
        else:
            groups.append(current_group)
            current_group = [sorted_notes[i]]
            
    groups.append(current_group)
    return groups

def apply_playable_range_mapping(
    notes: List[Dict[str, Any]], 
    min_pitch: int, 
    max_pitch: int, 
    max_simultaneous: int = 4,
    tolerance: float = 0.05
) -> List[Dict[str, Any]]:
    """
    Processes a list of notes:
    1. Groups notes by start time.
    2. Identifies the highest note in each group as the melody.
    3. Folds the melody into the playable range.
    4. Transposes the rest of the chord based on the melody's transposition if possible, 
       then folds individual notes if they are still out of range.
    5. Limits the number of simultaneous notes, preserving the melody.
    """
    groups = group_notes_by_time(notes, tolerance)
    processed_notes = []
    
    for group in groups:
        if not group:
            continue
            
        # 1. Detect highest note as melody
        melody_note = max(group, key=lambda n: n['pitch'])
        
        # 2. Fold melody into range
        original_melody_pitch = melody_note['pitch']
        new_melody_pitch = fold_note_into_range(original_melody_pitch, min_pitch, max_pitch)
        octave_shift = (new_melody_pitch - original_melody_pitch)
        
        # 3. Apply shift to all notes in group and fold them
        chord_notes = []
        for note in group:
            new_note = note.copy()
            # Initial shift based on melody transposition
            shifted_pitch = note['pitch'] + octave_shift
            # Fold if still out of range
            new_note['pitch'] = fold_note_into_range(shifted_pitch, min_pitch, max_pitch)
            chord_notes.append(new_note)
            
        # 4. Limit max simultaneous notes, preserving melody
        # Sort by pitch descending (melody first)
        chord_notes.sort(key=lambda n: n['pitch'], reverse=True)
        
        # Keep only unique pitches in the group to avoid redundant notes
        unique_chord = []
        seen_pitches = set()
        for n in chord_notes:
            if n['pitch'] not in seen_pitches:
                unique_chord.append(n)
                seen_pitches.add(n['pitch'])
        
        # Take top N notes
        limited_chord = unique_chord[:max_simultaneous]
        
        processed_notes.extend(limited_chord)
        
    return sorted(processed_notes, key=lambda x: x['start_time'])

if __name__ == "__main__":
    # Basic Unit Tests
    print("Running tests...")
    
    # Test note_to_midi
    assert note_to_midi("C4") == 60
    assert note_to_midi("A4") == 69
    assert note_to_midi("Bb3") == 58
    assert note_to_midi("C#2") == 37
    print("note_to_midi tests passed.")
    
    assert fold_note_into_range(84, 60, 72) == 72 # C6 -> C5 (highest in range)
    assert fold_note_into_range(48, 60, 72) == 60 # C3 -> C4 (lowest in range)
    assert fold_note_into_range(65, 60, 72) == 65 # F4 -> F4
    # Test small range (closest)
    assert fold_note_into_range(71, 60, 65) == 59 # B4 to B3 (59 is closer to 60 than 71 is to 65)
    print("fold_note_into_range tests passed.")
    
    # Test group_notes_by_time
    test_notes = [
        {'start_time': 0.0, 'pitch': 60},
        {'start_time': 0.02, 'pitch': 64},
        {'start_time': 1.0, 'pitch': 67},
    ]
    groups = group_notes_by_time(test_notes, tolerance=0.05)
    assert len(groups) == 2
    assert len(groups[0]) == 2
    assert len(groups[1]) == 1
    print("group_notes_by_time tests passed.")
    
    # Test apply_playable_range_mapping
    complex_notes = [
        {'start_time': 0.0, 'pitch': 72}, # C5 (Melody)
        {'start_time': 0.0, 'pitch': 67}, # G4
        {'start_time': 0.0, 'pitch': 64}, # E4
        {'start_time': 0.0, 'pitch': 60}, # C4
        {'start_time': 0.0, 'pitch': 48}, # C3
    ]
    # Map to range 60-72, max 3 notes
    result = apply_playable_range_mapping(complex_notes, 60, 72, max_simultaneous=3)
    assert len(result) == 3
    # Melody 72 is in range. Shift is 0. 
    # Other notes folded: 67->67, 64->64, 60->60, 48->60.
    # Unique pitches: 72, 67, 64, 60.
    # Top 3: 72, 67, 64.
    pitches = [n['pitch'] for n in result]
    assert 72 in pitches
    assert 67 in pitches
    assert 64 in pitches
    print("apply_playable_range_mapping tests passed.")
    
    print("All tests passed successfully!")
