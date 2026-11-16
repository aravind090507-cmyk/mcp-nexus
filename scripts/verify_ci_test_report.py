#!/usr/bin/env python3
"""
CI Strict Test Accounting & Gate Verification Script (Phase 15D.4.4)

Parses JUnit XML test results and strictly enforces release quality policies:
1. Zero test failures or errors across the entire suite.
2. Required PostgreSQL integration tests (7/7) must be executed with ZERO skips.
3. Multiprocess and audit reliability tests (7/7) must be executed with ZERO skips.
4. Database migration lifecycle tests (7/7) must be executed with ZERO skips.
5. Emits structured accounting summary for CI logs and release gate audit.
"""

import sys
import os
import xml.etree.ElementTree as ET

REQUIRED_CRITICAL_TESTS = {
    "test_postgresql_integration": 7,
    "test_multiprocess_and_audit_reliability": 7,
    "test_database_migrations": 7,
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_ci_test_report.py <path_to_junit_xml>")
        sys.exit(1)

    xml_path = sys.argv[1]
    if not os.path.exists(xml_path):
        print(f"CRITICAL CI ERROR: Test report XML not found at '{xml_path}'")
        sys.exit(1)

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"CRITICAL CI ERROR: Failed to parse JUnit XML report: {e}")
        sys.exit(1)

    # In pytest, root can be <testsuites> or <testsuite>
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        suites = root.findall("testsuite")
        if suites:
            suite = suites[0]
        else:
            suite = root

    total_tests = int(suite.attrib.get("tests", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    skipped = int(suite.attrib.get("skipped", 0))
    time_taken = float(suite.attrib.get("time", 0.0))

    passed = total_tests - failures - errors - skipped

    print("=" * 80)
    print("MCP NEXUS CI STRICT TEST ACCOUNTING & GATE AUDIT REPORT")
    print("=" * 80)
    print(f"Total Tests Executed : {total_tests}")
    print(f"Passed               : {passed}")
    print(f"Failed               : {failures}")
    print(f"Errors               : {errors}")
    print(f"Skipped              : {skipped}")
    print(f"Total Duration       : {time_taken:.2f}s")
    print("-" * 80)

    # Track suite-specific execution
    critical_counts = {k: {"passed": 0, "skipped": 0, "failed": 0} for k in REQUIRED_CRITICAL_TESTS}
    skipped_test_details = []

    for testcase in root.iter("testcase"):
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "")
        file_attr = testcase.attrib.get("file", "")
        full_ident = f"{file_attr}::{name}" if file_attr else f"{classname}::{name}"

        is_failure = testcase.find("failure") is not None
        is_error = testcase.find("error") is not None
        skip_elem = testcase.find("skipped")

        for key in REQUIRED_CRITICAL_TESTS:
            if key in classname or key in file_attr:
                if is_failure or is_error:
                    critical_counts[key]["failed"] += 1
                elif skip_elem is not None:
                    critical_counts[key]["skipped"] += 1
                else:
                    critical_counts[key]["passed"] += 1

        if skip_elem is not None:
            reason = skip_elem.attrib.get("message", "No reason provided")
            skipped_test_details.append((full_ident, reason))

    # Evaluate critical release suites
    critical_violations = []
    print("RELEASE-CRITICAL SUITE VERIFICATION:")
    for suite_name, expected_count in REQUIRED_CRITICAL_TESTS.items():
        stats = critical_counts[suite_name]
        total_suite = stats["passed"] + stats["skipped"] + stats["failed"]
        status_line = (
            f"  • {suite_name}: {stats['passed']}/{expected_count} PASSED, "
            f"{stats['skipped']} SKIPPED, {stats['failed']} FAILED"
        )
        print(status_line)

        if total_suite < expected_count:
            critical_violations.append(
                f"{suite_name}: expected {expected_count} tests, but only {total_suite} were collected."
            )
        if stats["skipped"] > 0:
            critical_violations.append(
                f"{suite_name}: {stats['skipped']} test(s) skipped! Skips strictly forbidden in critical suites."
            )
        if stats["failed"] > 0:
            critical_violations.append(
                f"{suite_name}: {stats['failed']} test(s) failed!"
            )

    print("-" * 80)

    if skipped_test_details:
        print(f"SKIPPED TESTS ({len(skipped_test_details)} total):")
        for test_name, reason in skipped_test_details:
            print(f"  [SKIPPED] {test_name} — Reason: {reason}")
        print("-" * 80)

    # Final Gate Decisions
    has_errors = failures > 0 or errors > 0
    if has_errors:
        print("❌ CI GATE FAILED: Test suite contains failures or unhandled errors.")
        sys.exit(1)

    if critical_violations:
        print("❌ CI GATE FAILED: Release-critical test integrity violations:")
        for violation in critical_violations:
            print(f"  - {violation}")
        sys.exit(1)

    print("✅ CI GATE PASSED: All tests passed with zero failures and zero unexpected skips.")
    print("=" * 80)
    sys.exit(0)


if __name__ == "__main__":
    main()
