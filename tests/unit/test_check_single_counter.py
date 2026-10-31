"""The external counter check must flag the pattern measured in production on 2026-10-30."""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_single_counter.py"
_spec = importlib.util.spec_from_file_location("check_single_counter", _PATH)
assert _spec and _spec.loader
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def test_one_counter_passes() -> None:
    results = [(200, 29 - i) for i in range(30)] + [(429, 0)]
    assert check.find_problems(results) == []


def test_interleaved_counters_are_flagged() -> None:
    # Shape of the production measurement: one main countdown, two more starting at 29,
    # and 200s after a 429 from the same client in the same minute.
    results = [(200, 29 - i) for i in range(20)]
    results += [(200, 29), (200, 29), (429, 0), (200, 28), (429, 0), (200, 27), (429, 0)]
    problems = check.find_problems(results)
    assert any("repeated" in p for p in problems)
    assert any("after the first 429" in p for p in problems)


def test_never_reaching_the_limit_is_flagged() -> None:
    assert check.find_problems([(200, 29 - i) for i in range(10)]) != []
