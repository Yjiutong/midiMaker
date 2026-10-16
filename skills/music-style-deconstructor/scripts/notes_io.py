#!/usr/bin/env python3
"""notes_io.py - 把音符事件导出为模型友好的 notes.json。"""

from __future__ import annotations

import json
from pathlib import Path


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_note_name(pitch):
    octave = int(pitch // 12) - 1
    return f"{NOTE_NAMES[pitch % 12]}{octave}"


def normalize_note(note, default_confidence=0.7):
    pitch = int(note.get("pitch", 0))
    velocity = int(note.get("velocity", 80))
    start = float(note.get("start", 0.0))
    end = float(note.get("end", start + 0.1))
    if end <= start:
        end = start + 0.1
    return {
        "start": round(start, 4),
        "end": round(end, 4),
        "duration": round(end - start, 4),
        "pitch": pitch,
        "midi_note": midi_note_name(pitch),
        "velocity": max(1, min(127, velocity)),
        "confidence": round(float(note.get("confidence", default_confidence)), 3),
    }


def write_notes_json(path, entries, source=None):
    """entries: [{"track": str, "file": str, "channel": int, "program": int, "notes": [...]}]"""
    tracks = []
    for entry in entries:
        tracks.append({
            "track": entry.get("track"),
            "file": entry.get("file"),
            "channel": int(entry.get("channel", 0) or 0),
            "program": int(entry.get("program", 0) or 0),
            "is_drum": bool(entry.get("is_drum", False)),
            "note_count": len(entry.get("notes", [])),
            "notes": [normalize_note(n) for n in entry.get("notes", [])],
        })
    data = {
        "generated_by": "midiMaker notes_io",
        "source": str(source) if source else None,
        "tracks": tracks,
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out
