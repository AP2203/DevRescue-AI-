import pytest
from app.services.sandbox_service import parse_test_duration


def test_parse_pytest_duration_standard():
    stdout = """
============================= test session starts ==============================
collecting ... collected 65 items

tests/test_api.py ....................................................   [ 80%]
tests/test_models.py .............                                      [100%]

============================== 65 passed in 16.14s ==============================
"""
    duration = parse_test_duration("pytest", stdout)
    assert duration == 16.14


def test_parse_pytest_duration_with_warnings():
    stdout = """
======================== 65 passed, 2 warnings in 16.34s ========================
"""
    duration = parse_test_duration("pytest", stdout)
    assert duration == 16.34


def test_parse_pytest_duration_with_failures():
    stdout = """
========================= 1 failed, 64 passed in 5.82s ==========================
"""
    duration = parse_test_duration("pytest", stdout)
    assert duration == 5.82


def test_parse_jest_duration():
    stdout = """
PASS tests/unit/parser.test.js
Test Suites: 5 passed, 5 total
Tests:       42 passed, 42 total
Snapshots:   0 total
Time:        12.45 s
Ran all test suites.
"""
    duration = parse_test_duration("npm test", stdout)
    assert duration == 12.45


def test_parse_vitest_duration():
    stdout = """
Test Files  6 passed (6)
     Tests  35 passed (35)
  Duration  3.21s (transform 210ms, setup 0ms, collect 45ms, tests 2.95s)
"""
    duration = parse_test_duration("npm test", stdout)
    assert duration == 3.21


def test_parse_unittest_duration():
    stderr = """
----------------------------------------------------------------------
Ran 12 tests in 0.456s

OK
"""
    duration = parse_test_duration("python -m unittest", "", stderr)
    assert duration == 0.46


def test_parse_duration_empty_output():
    assert parse_test_duration("pytest", "") is None
    assert parse_test_duration("pytest", "   ") is None

