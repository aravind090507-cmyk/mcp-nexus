#!/usr/bin/env python3
"""
CI Strict Test Accounting & Critical Gate Verifier (Phase 15D.4.4.2)

Enforces release-critical verification policies:
1. Report file must exist, be non-empty, and contain well-formed XML.
2. Total test execution count must be strictly greater than zero (minimum baseline: 230 tests).
3. Zero test failures or unhandled errors across all test suites.
4. All required release-critical test suites must be present with 100% of their expected test cases.
5. Zero skips allowed in release-critical suites (PostgreSQL integration, multiprocess reliability, migrations).
6. Rejects duplicate testcase entries that artificially inflate aggregate counts.
7. Emits structured accounting summary and diagnostic outputs for release verification.
"""

import sys
import os
import xml.etree.ElementTree as ET

# Authoritative specification of release-critical suites and their required test cases
REQUIRED_CRITICAL_SUITES = {
    "test_postgresql_integration": {
        "test_01_postgresql_connection_and_version",
        "test_02_postgresql_concurrent_deployment_state_transitions",
        "test_03_postgresql_atomic_deployment_state_and_audit_logging",
        "test_04_postgresql_multi_worker_lock_contention",
        "test_05_postgresql_failure_rollback",
        "test_06_postgresql_tenant_isolation_concurrency",
        "test_07_postgresql_emergency_shutdown_persistence_and_propagation",
    },
    "test_multiprocess_and_audit_reliability": {
        "test_01_cross_process_shutdown_propagation",
        "test_02_shutdown_persistence_across_process_lifecycle",
        "test_03_concurrent_cross_process_shutdown_requests",
        "test_04_cross_process_recovery_and_reset_safety",
        "test_05_atomic_audit_and_state_success",
        "test_06_atomic_audit_rollback_on_failure",
        "test_07_concurrent_audit_events_consistency",
    },
    "test_database_migrations": {
        "test_01_application_import_creates_zero_schema",
        "test_02_sqlite_compatibility_migration_lifecycle",
        "test_03_fresh_postgresql_initialization_and_migration",
        "test_04_existing_database_adoption_and_safe_stamping",
        "test_05_reversible_migration_downgrade_and_reupgrade_postgresql",
        "test_06_migration_failure_transaction_safety",
        "test_07_postgresql_application_connection_preserved",
    },
}

MINIMUM_BASELINE_TEST_COUNT = 230


def verify_report(xml_path: str) -> tuple[bool, str]:
    """
    Validates a JUnit XML test report against release-critical gate policies.
    Returns (is_valid, summary_or_error_message).
    """
    if not xml_path or not os.path.exists(xml_path):
        return False, f"CRITICAL CI ERROR: Test report XML not found at '{xml_path}'"

    if os.path.getsize(xml_path) == 0:
        return False, "CRITICAL CI ERROR: Test report XML file is empty (0 bytes)."

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        return False, f"CRITICAL CI ERROR: Failed to parse JUnit XML report (malformed XML): {e}"

    # Extract testsuite element
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        suites = root.findall("testsuite")
        suite = suites[0] if suites else root

    try:
        total_tests = int(suite.attrib.get("tests", 0))
        failures = int(suite.attrib.get("failures", 0))
        errors = int(suite.attrib.get("errors", 0))
        skipped = int(suite.attrib.get("skipped", 0))
        time_taken = float(suite.attrib.get("time", 0.0))
    except (ValueError, TypeError) as e:
        return False, f"CRITICAL CI ERROR: Invalid testsuite attributes in report: {e}"

    # Reject negative numeric attributes
    if total_tests < 0 or failures < 0 or errors < 0 or skipped < 0:
        return False, "CRITICAL CI ERROR: Invalid testsuite attributes in report: negative counts detected."

    # Verify non-zero test execution
    all_testcase_elems = list(root.iter("testcase"))
    if total_tests <= 0 or len(all_testcase_elems) == 0:
        return False, "CRITICAL CI ERROR: Zero tests executed in test report (total_tests <= 0)."

    passed = total_tests - failures - errors - skipped

    out = []
    out.append("=" * 80)
    out.append("MCP NEXUS CI STRICT TEST ACCOUNTING & GATE AUDIT REPORT")
    out.append("=" * 80)
    out.append(f"Total Tests Executed : {total_tests}")
    out.append(f"Passed               : {passed}")
    out.append(f"Failed               : {failures}")
    out.append(f"Errors               : {errors}")
    out.append(f"Skipped              : {skipped}")
    out.append(f"Total Duration       : {time_taken:.2f}s")
    out.append("-" * 80)

    # Check for baseline count requirement and aggregate mismatch
    violations = []
    if len(all_testcase_elems) != total_tests:
        violations.append(
            f"Aggregate test count mismatch: testsuite header declares {total_tests} tests, "
            f"but document contains {len(all_testcase_elems)} testcase elements."
        )

    if total_tests < MINIMUM_BASELINE_TEST_COUNT:
        violations.append(
            f"Test collection deficit: expected at least {MINIMUM_BASELINE_TEST_COUNT} tests, "
            f"but report only contains {total_tests}."
        )

    # Detect attribute spoofing (elements vs summary attributes)
    actual_failures_count = sum(1 for tc in all_testcase_elems if tc.find("failure") is not None)
    actual_errors_count = sum(1 for tc in all_testcase_elems if tc.find("error") is not None)
    if actual_failures_count != failures or actual_errors_count != errors:
        violations.append(
            f"Attribute spoofing detected: header declares failures={failures}, errors={errors}, "
            f"but XML elements contain {actual_failures_count} failure(s) and {actual_errors_count} error(s)."
        )

    # Track suite-specific execution and check for duplicate testcases
    seen_test_keys = set()
    suite_test_results = {
        suite_name: {"passed": set(), "skipped": set(), "failed": set()}
        for suite_name in REQUIRED_CRITICAL_SUITES
    }
    all_skipped_details = []

    for testcase in all_testcase_elems:
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "")
        file_attr = testcase.attrib.get("file", "")
        full_ident = f"{file_attr}::{name}" if file_attr else f"{classname}::{name}"

        # Duplicate detection
        test_key = (file_attr or classname, name)
        if test_key in seen_test_keys:
            violations.append(f"Duplicate testcase entry detected: '{full_ident}'")
        seen_test_keys.add(test_key)

        is_failure = testcase.find("failure") is not None
        is_error = testcase.find("error") is not None
        skip_elem = testcase.find("skipped")

        # Map to release-critical suites
        for suite_key, expected_test_names in REQUIRED_CRITICAL_SUITES.items():
            if suite_key in classname or suite_key in file_attr:
                if is_failure or is_error:
                    suite_test_results[suite_key]["failed"].add(name)
                elif skip_elem is not None:
                    suite_test_results[suite_key]["skipped"].add(name)
                else:
                    suite_test_results[suite_key]["passed"].add(name)

        if skip_elem is not None:
            reason = skip_elem.attrib.get("message", "No reason provided")
            all_skipped_details.append((full_ident, reason))

    # Evaluate each critical suite
    out.append("RELEASE-CRITICAL SUITE VERIFICATION:")
    for suite_key, expected_tests in REQUIRED_CRITICAL_SUITES.items():
        results = suite_test_results[suite_key]
        n_passed = len(results["passed"])
        n_skipped = len(results["skipped"])
        n_failed = len(results["failed"])
        expected_n = len(expected_tests)

        status_str = f"  • {suite_key}: {n_passed}/{expected_n} PASSED, {n_skipped} SKIPPED, {n_failed} FAILED"
        out.append(status_str)

        # Check for missing test cases
        missing_cases = expected_tests - results["passed"] - results["skipped"] - results["failed"]
        if missing_cases:
            violations.append(f"{suite_key}: missing expected test case(s): {sorted(missing_cases)}")

        if n_skipped > 0:
            violations.append(
                f"{suite_key}: {n_skipped} test(s) skipped ({sorted(results['skipped'])}). "
                "Skips are strictly forbidden in critical suites."
            )

        if n_failed > 0:
            violations.append(f"{suite_key}: {n_failed} test(s) failed ({sorted(results['failed'])}).")

    out.append("-" * 80)

    if all_skipped_details:
        out.append(f"SKIPPED TESTS ({len(all_skipped_details)} total):")
        for test_name, reason in all_skipped_details:
            out.append(f"  [SKIPPED] {test_name} — Reason: {reason}")
        out.append("-" * 80)

    if failures > 0 or errors > 0:
        violations.append(f"Suite contains {failures} failure(s) and {errors} error(s).")

    if violations:
        out.append("❌ CI GATE FAILED: Release-critical test integrity violations:")
        for v in violations:
            out.append(f"  - {v}")
        return False, "\n".join(out)

    out.append("✅ CI GATE PASSED: All tests passed with zero failures, zero errors, and zero critical skips.")
    out.append("=" * 80)
    return True, "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_ci_test_report.py <path_to_junit_xml>")
        sys.exit(1)

    xml_path = sys.argv[1]
    is_valid, report = verify_report(xml_path)
    print(report)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
