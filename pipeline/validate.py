"""Validate storyboard.json against the JSON Schema plus semantic checks. Runs before every stage."""
from __future__ import annotations

import json
import sys

from pipeline.common import SCHEMA, STORYBOARD


class StoryboardError(SystemExit):
    pass


def validate_storyboard(sb: dict) -> dict:
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = [f"  {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in validator.iter_errors(sb)]

    ids = [s["id"] for s in sb.get("shots", [])]
    if len(ids) != len(set(ids)):
        errors.append("  shots: duplicate shot ids")
    refs = set(sb.get("references", {}))
    for s in sb.get("shots", []):
        for r in s.get("refs", []):
            if r not in refs:
                errors.append(f"  shots/{s['id']}/refs: unknown reference '{r}'")
    cue_ids = {c["id"] for c in sb.get("music", {}).get("cues", [])}
    for s in sb.get("shots", []):
        if s.get("music_cue") not in cue_ids:
            errors.append(f"  shots/{s['id']}/music_cue: unknown cue '{s.get('music_cue')}'")

    total = sum(s["duration_s"] for s in sb.get("shots", [])) + sb["film"]["end_card"]["duration_s"]
    lo, hi = sb["film"]["target_duration_s"]
    if not lo <= total <= hi:
        errors.append(f"  planned duration {total:.1f}s is outside the target {lo}-{hi}s")

    if errors:
        raise StoryboardError("storyboard.json is invalid:\n" + "\n".join(errors))

    words_am = sum(len(s["narration"]["am"].split()) for s in sb["shots"])
    words_en = sum(len(s["narration"]["en"].split()) for s in sb["shots"])
    return {"shots": len(ids), "planned_duration_s": total, "narration_words_am": words_am, "narration_words_en": words_en}


def main() -> None:
    sb = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    summary = validate_storyboard(sb)
    print("storyboard.json is valid:", ", ".join(f"{k}={v}" for k, v in summary.items()))


if __name__ == "__main__":
    try:
        main()
    except StoryboardError as e:
        print(e.code, file=sys.stderr)
        sys.exit(1)
