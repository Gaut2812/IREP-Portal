import json
from pathlib import Path
import pytest

def get_keys(d, prefix=""):
    """Recursively collect dot-notated key paths."""
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        keys.add(full_key)
        if isinstance(v, dict):
            keys.update(get_keys(v, full_key))
    return keys

def load_json_with_duplicate_check(path: Path):
    """Parses JSON and fails if any duplicate key exists at any nesting level."""
    def dict_raise_on_duplicates(ordered_pairs):
        d = {}
        for k, v in ordered_pairs:
            if k in d:
                raise ValueError(f"Duplicate key found in {path.name}: '{k}'")
            d[k] = v
        return d

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=dict_raise_on_duplicates)

def test_locale_json_parses_without_duplicate_keys():
    repo_root = Path(__file__).resolve().parents[3]
    en_path = repo_root / "apps" / "web" / "src" / "locales" / "en.json"
    ta_path = repo_root / "apps" / "web" / "src" / "locales" / "ta.json"

    assert en_path.exists(), f"en.json does not exist at {en_path}"
    assert ta_path.exists(), f"ta.json does not exist at {ta_path}"

    en_data = load_json_with_duplicate_check(en_path)
    ta_data = load_json_with_duplicate_check(ta_path)

    assert isinstance(en_data, dict)
    assert isinstance(ta_data, dict)

def test_en_and_ta_locales_have_identical_key_sets():
    repo_root = Path(__file__).resolve().parents[3]
    en_path = repo_root / "apps" / "web" / "src" / "locales" / "en.json"
    ta_path = repo_root / "apps" / "web" / "src" / "locales" / "ta.json"

    en_data = load_json_with_duplicate_check(en_path)
    ta_data = load_json_with_duplicate_check(ta_path)

    en_keys = get_keys(en_data)
    ta_keys = get_keys(ta_data)

    missing_in_ta = en_keys - ta_keys
    missing_in_en = ta_keys - en_keys

    assert not missing_in_ta, f"Keys in en.json but missing in ta.json: {sorted(missing_in_ta)}"
    assert not missing_in_en, f"Keys in ta.json but missing in en.json: {sorted(missing_in_en)}"
    assert en_keys == ta_keys, "en.json and ta.json keys must be identical"
