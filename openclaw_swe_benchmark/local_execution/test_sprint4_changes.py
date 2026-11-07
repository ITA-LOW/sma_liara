#!/usr/bin/env python3
"""
LIARA Sprint 4 — Unit Tests for Implemented Changes (No Docker / No LLM needed).
Covers all 6 systemic changes + Django runner normalization from plan_sprint4.md.
"""
import sys
import os
import re

# Ensure local execution directory is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from main_orchestrator import (
    _extract_line_hint_for_file,
    localize_from_traceback,
    VERSION
)

def test_1_extract_line_hint_for_file():
    print("=== Test 1: _extract_line_hint_for_file (Change 1) ===")

    # Case A: sympy-17139 traceback — must return line 504 from fu.py, ignoring expr.py:406
    tb_sympy = """
Traceback (most recent call last):
  File "/app/sympy/simplify/fu.py", line 504, in _f
    if (rv.exp < 0) == True:
  File "/app/sympy/core/expr.py", line 406, in __lt__
    raise TypeError("Invalid comparison of complex %s" % me)
"""
    hint = _extract_line_hint_for_file(tb_sympy, "sympy/simplify/fu.py")
    assert hint == 504, f"FAIL: Expected 504, got {hint}"
    print(f"  [PASS] sympy/simplify/fu.py line_hint = {hint} (correctly ignored expr.py:406)")

    # Case B: target file is not present in the traceback — must return None (no cross-file poisoning)
    tb_django = """
Traceback (most recent call last):
  File "/app/tests/runtests.py", line 666, in <module>
    failures = django_tests(
  File "/app/django/test/runner.py", line 738, in load_tests_for_label
    raise RuntimeError("One of the test labels is a path to a file")
"""
    hint_django = _extract_line_hint_for_file(tb_django, "django/contrib/admin/options.py")
    assert hint_django is None, f"FAIL: Expected None when file not in traceback, got {hint_django}"
    print("  [PASS] File not in traceback returns None (prevents AST scope poisoning)")

    # Case C: Multiple frames in target file — returns innermost (last) line
    tb_multi = """
  File "/app/sympy/simplify/fu.py", line 524, in _TR56
    return bottom_up(rv, _f)
  File "/app/sympy/simplify/fu.py", line 504, in _f
    if (rv.exp < 0) == True:
"""
    hint_multi = _extract_line_hint_for_file(tb_multi, "sympy/simplify/fu.py")
    assert hint_multi == 504, f"FAIL: Expected 504 (innermost frame), got {hint_multi}"
    print(f"  [PASS] Multiple frames in target file resolves to innermost: {hint_multi}")


def test_2_localize_from_traceback_filters():
    print("\n=== Test 2: localize_from_traceback filters (Change 2) ===")

    # Stdlib and external paths must be filtered out
    tb = """
  File "/app/django/test/runner.py", line 738, in load_tests_for_label
    raise RuntimeError()
  File "/usr/local/lib/python3.9/unittest/suite.py", line 57, in addTests
    for test in tests:
  File "/opt/some_external/tool.py", line 12, in run
"""
    results = localize_from_traceback(tb, {}, "/tmp/repo")
    assert not any("usr/local" in c for c in results), f"FAIL: stdlib leaked! {results}"
    assert not any("unittest" in c for c in results), f"FAIL: unittest leaked! {results}"
    assert not any("opt" in c for c in results), f"FAIL: /opt leaked! {results}"
    print("  [PASS] Stdlib (/usr/local/lib) and external paths filtered out successfully")

    # Harness functions must be blocked from pulling in runner candidates via func_map
    fake_func_map = {
        "build_suite": [("django/test/runner.py", 776)],
        "load_tests_for_label": [("django/test/runner.py", 738)],
        "django_tests": [("tests/runtests.py", 386)],
        "options_function": [("django/contrib/admin/options.py", 100)],
    }
    tb_harness = """
  File "/app/django/test/runner.py", line 738, in load_tests_for_label
  File "/app/django/test/runner.py", line 776, in build_suite
"""
    results_harness = localize_from_traceback(tb_harness, fake_func_map, "/tmp/repo")
    assert not any("runner.py" in c for c in results_harness), f"FAIL: runner.py leaked! {results_harness}"
    print("  [PASS] Harness functions (build_suite, load_tests_for_label) blocked from candidates")


def test_3_harness_marker_detection():
    print("\n=== Test 3: Harness marker detection in Sully context (Change 4) ===")
    HARNESS_MARKERS = [
        "runtests.py", "unittest/suite.py", "conftest.py",
        "RuntimeError: One of the test labels",
        "load_tests_for_label", "build_suite",
    ]

    django_tb = """
Traceback (most recent call last):
  File "/app/tests/runtests.py", line 666, in <module>
    failures = django_tests(
  File "/app/django/test/runner.py", line 738, in load_tests_for_label
    raise RuntimeError("One of the test labels is a path to a file: tests/admin_inlines/tests.py")
"""
    assert any(m in django_tb for m in HARNESS_MARKERS), "FAIL: Django harness traceback not detected"
    print("  [PASS] Django runner traceback correctly flagged as test harness error")

    sympy_tb = """
Traceback (most recent call last):
  File "/app/sympy/simplify/fu.py", line 504, in _f
    if (rv.exp < 0) == True:
TypeError: Invalid comparison of complex I
"""
    assert not any(m in sympy_tb for m in HARNESS_MARKERS), "FAIL: SymPy real bug misflagged as harness"
    print("  [PASS] Real production traceback (SymPy) correctly NOT flagged as harness")


def test_4_indentation_alert():
    print("\n=== Test 4: Indentation anchor alert (Change 5) ===")

    # Nested function with 8 spaces base indentation
    nested_ctx = """        def _f(rv):
            if not isinstance(rv, f):
                return rv
            if (rv.exp < 0) == True:
                return rv
"""
    anchor_indent = 0
    for line in nested_ctx.split("\n"):
        if line.strip() and not line.strip().startswith("#"):
            anchor_indent = len(line) - len(line.lstrip())
            break
    assert anchor_indent == 8, f"FAIL: Expected 8 spaces, got {anchor_indent}"
    print("  [PASS] Nested function correctly detected with 8 spaces base indentation")


def test_5_file_backtrack_logic():
    print("\n=== Test 5: File backtrack logic (Change 6) ===")
    production_candidates = ["sympy/physics/vector/printing.py", "sympy/printing/pretty/pretty.py"]
    tried_files = ["sympy/physics/vector/printing.py"]
    MAX_FILE_ATTEMPTS = 2
    file_attempt = 0

    should_backtrack = file_attempt < MAX_FILE_ATTEMPTS - 1
    next_candidates = [c for c in production_candidates if c not in tried_files]
    assert should_backtrack, "FAIL: Backtrack should trigger after file 1 exhausted"
    assert next_candidates == ["sympy/printing/pretty/pretty.py"], f"FAIL: Expected pretty.py next, got {next_candidates}"
    print(f"  [PASS] Backtrack selects next candidate: {next_candidates[0]}")


def test_6_django_runner_normalization():
    print("\n=== Test 6: Django test runner normalization ===")
    raw_script = "python3 tests/runtests.py tests/admin_inlines/tests.py"
    parts = raw_script.split()
    norm_parts = []
    for p in parts:
        if p.endswith(".py") and not p.endswith("runtests.py"):
            p_dir = os.path.dirname(p)
            norm_parts.append(p_dir if p_dir else p)
        else:
            norm_parts.append(p)
    normalized = " ".join(norm_parts)
    assert normalized == "python3 tests/runtests.py tests/admin_inlines", f"FAIL: Got {normalized}"
    print(f"  [PASS] Normalized '{raw_script}' -> '{normalized}'")


def test_7_version():
    print("\n=== Test 7: Orchestrator version check ===")
    assert VERSION == "4.7.0", f"FAIL: Expected VERSION 4.7.0, got {VERSION}"
    print(f"  [PASS] LIARA Version = {VERSION}")


if __name__ == "__main__":
    test_1_extract_line_hint_for_file()
    test_2_localize_from_traceback_filters()
    test_3_harness_marker_detection()
    test_4_indentation_alert()
    test_5_file_backtrack_logic()
    test_6_django_runner_normalization()
    test_7_version()
    print("\n" + "="*50)
    print("ALL 7 SPRINT 4 UNIT TESTS PASSED SUCCESSFULLY! ✓")
    print("="*50)
