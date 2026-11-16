"""
Unit tests for CI test report verifier (scripts/verify_ci_test_report.py).

Validates that verify_report() strictly enforces:
- Non-empty, well-formed XML
- Non-zero test execution and minimum baseline count
- Zero failures and zero unhandled errors
- Presence and 100% pass rate of all required release-critical test cases
- Rejection of skips in critical suites
- Rejection of duplicate testcase entries
- Acceptance of complete, valid test reports
"""

import os
import sys
import tempfile
import pytest

# Ensure scripts and backend are on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
for p in (ROOT_DIR, SCRIPTS_DIR, BASE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from verify_ci_test_report import verify_report, REQUIRED_CRITICAL_SUITES


def _create_temp_xml(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".xml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _build_valid_report_xml(extra_cases: int = 209) -> str:
    """Builds a synthetic, fully valid JUnit XML containing all critical suites + extra cases."""
    cases = []
    for suite_name, test_names in REQUIRED_CRITICAL_SUITES.items():
        for t_name in sorted(test_names):
            cases.append(
                f'  <testcase classname="backend.app.tests.{suite_name}" file="backend/app/tests/{suite_name}.py" name="{t_name}" time="0.05" />'
            )

    for i in range(extra_cases):
        cases.append(
            f'  <testcase classname="backend.app.tests.test_backend" file="backend/app/tests/test_backend.py" name="test_dummy_{i}" time="0.01" />'
        )

    total = len(cases)
    xml_str = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuite name="pytest" tests="{total}" errors="0" failures="0" skipped="0" time="10.5">\n'
        + "\n".join(cases)
        + "\n</testsuite>"
    )
    return xml_str


def test_missing_report_file_rejected():
    valid, msg = verify_report("non_existent_report_file_123.xml")
    assert not valid
    assert "not found" in msg.lower()


def test_empty_report_file_rejected(tmp_path):
    p = tmp_path / "empty.xml"
    p.write_text("", encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "empty" in msg.lower()


def test_malformed_xml_rejected(tmp_path):
    p = tmp_path / "malformed.xml"
    p.write_text("<testsuite><unclosed_tag>", encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "malformed" in msg.lower()


def test_zero_tests_executed_rejected(tmp_path):
    xml_str = '<testsuite name="pytest" tests="0" errors="0" failures="0" skipped="0" time="0.0" />'
    p = tmp_path / "zero.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "zero tests executed" in msg.lower()


def test_test_count_deficit_rejected(tmp_path):
    # Valid critical suites (21 tests) but total < 230 baseline
    xml_str = _build_valid_report_xml(extra_cases=50)
    p = tmp_path / "deficit.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "deficit" in msg.lower()


def test_missing_critical_testcase_rejected(tmp_path):
    # Omit one critical test case from test_postgresql_integration
    cases = []
    for suite_name, test_names in REQUIRED_CRITICAL_SUITES.items():
        for t_name in sorted(test_names):
            if suite_name == "test_postgresql_integration" and t_name == "test_01_postgresql_connection_and_version":
                continue  # Omit
            cases.append(
                f'  <testcase classname="backend.app.tests.{suite_name}" file="backend/app/tests/{suite_name}.py" name="{t_name}" time="0.05" />'
            )

    for i in range(215):
        cases.append(
            f'  <testcase classname="backend.app.tests.test_backend" file="backend/app/tests/test_backend.py" name="test_dummy_{i}" time="0.01" />'
        )

    total = len(cases)
    xml_str = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuite name="pytest" tests="{total}" errors="0" failures="0" skipped="0" time="10.5">\n'
        + "\n".join(cases)
        + "\n</testsuite>"
    )
    p = tmp_path / "missing_case.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "missing expected test case" in msg.lower()
    assert "test_01_postgresql_connection_and_version" in msg


def test_skipped_critical_test_rejected(tmp_path):
    # One critical testcase skipped
    cases = []
    for suite_name, test_names in REQUIRED_CRITICAL_SUITES.items():
        for t_name in sorted(test_names):
            if suite_name == "test_database_migrations" and t_name == "test_03_fresh_postgresql_initialization_and_migration":
                cases.append(
                    f'  <testcase classname="backend.app.tests.{suite_name}" file="backend/app/tests/{suite_name}.py" name="{t_name}" time="0.05">\n'
                    '    <skipped message="PostgreSQL service unavailable" />\n'
                    '  </testcase>'
                )
            else:
                cases.append(
                    f'  <testcase classname="backend.app.tests.{suite_name}" file="backend/app/tests/{suite_name}.py" name="{t_name}" time="0.05" />'
                )

    for i in range(215):
        cases.append(
            f'  <testcase classname="backend.app.tests.test_backend" file="backend/app/tests/test_backend.py" name="test_dummy_{i}" time="0.01" />'
        )

    total = len(cases)
    xml_str = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuite name="pytest" tests="{total}" errors="0" failures="0" skipped="1" time="10.5">\n'
        + "\n".join(cases)
        + "\n</testsuite>"
    )
    p = tmp_path / "critical_skipped.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "strictly forbidden" in msg.lower()


def test_failure_or_error_rejected(tmp_path):
    cases = []
    for suite_name, test_names in REQUIRED_CRITICAL_SUITES.items():
        for t_name in sorted(test_names):
            cases.append(
                f'  <testcase classname="backend.app.tests.{suite_name}" file="backend/app/tests/{suite_name}.py" name="{t_name}" time="0.05" />'
            )

    # Add a failing test
    cases.append(
        '  <testcase classname="backend.app.tests.test_backend" file="backend/app/tests/test_backend.py" name="test_failing" time="0.01">\n'
        '    <failure message="AssertionError">assert False</failure>\n'
        '  </testcase>'
    )
    for i in range(215):
        cases.append(
            f'  <testcase classname="backend.app.tests.test_backend" file="backend/app/tests/test_backend.py" name="test_dummy_{i}" time="0.01" />'
        )

    total = len(cases)
    xml_str = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuite name="pytest" tests="{total}" errors="0" failures="1" skipped="0" time="10.5">\n'
        + "\n".join(cases)
        + "\n</testsuite>"
    )
    p = tmp_path / "failure.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "failure(s)" in msg.lower()


def test_duplicate_testcase_entry_rejected(tmp_path):
    # Repeat a critical testcase to inflate count
    xml_str = _build_valid_report_xml(extra_cases=210)
    # Inject duplicate
    dup = '  <testcase classname="backend.app.tests.test_postgresql_integration" file="backend/app/tests/test_postgresql_integration.py" name="test_01_postgresql_connection_and_version" time="0.05" />\n'
    xml_str = xml_str.replace("</testsuite>", dup + "</testsuite>")

    p = tmp_path / "duplicate.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "duplicate testcase entry detected" in msg.lower()


def test_valid_complete_report_accepted(tmp_path):
    xml_str = _build_valid_report_xml(extra_cases=215)
    p = tmp_path / "valid.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert valid, f"Expected valid report to pass, but failed with:\n{msg}"
    assert "CI GATE PASSED" in msg


def test_negative_numeric_attributes_rejected(tmp_path):
    xml_str = '<testsuite name="pytest" tests="-5" errors="0" failures="0" skipped="0" time="0.0" />'
    p = tmp_path / "negative.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "negative counts detected" in msg.lower()


def test_misleading_aggregate_count_mismatch_rejected(tmp_path):
    # Header says 250 tests, but only 21 critical testcases exist
    xml_str = _build_valid_report_xml(extra_cases=0)
    # Tamper header tests count to 250
    xml_str = xml_str.replace('tests="21"', 'tests="250"')
    p = tmp_path / "misleading_aggregate.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "aggregate test count mismatch" in msg.lower()


def test_attribute_spoofing_rejected(tmp_path):
    # Header claims failures="0", but testcase contains a <failure> element
    xml_str = _build_valid_report_xml(extra_cases=215)
    # Inject failure element inside a testcase without updating failures="0" header
    xml_str = xml_str.replace(
        'name="test_dummy_0" time="0.01" />',
        'name="test_dummy_0" time="0.01"><failure message="spoofed">error</failure></testcase>'
    )
    p = tmp_path / "spoofed.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "attribute spoofing detected" in msg.lower()


def test_report_containing_only_unrelated_tests_rejected(tmp_path):
    # 250 tests, but none from the critical suites
    cases = [
        f'  <testcase classname="backend.app.tests.test_random" file="backend/app/tests/test_random.py" name="test_unrelated_{i}" time="0.01" />'
        for i in range(240)
    ]
    xml_str = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuite name="pytest" tests="240" errors="0" failures="0" skipped="0" time="5.0">\n'
        + "\n".join(cases)
        + "\n</testsuite>"
    )
    p = tmp_path / "unrelated.xml"
    p.write_text(xml_str, encoding="utf-8")
    valid, msg = verify_report(str(p))
    assert not valid
    assert "missing expected test case" in msg.lower()
