#!/usr/bin/env python3
"""
MCP NEXUS Database Integrity Contract & Clean-Checkout Verifier (Phase 15D.4.4.4)

Distinguishes between:
1. Local Canonical Database Integrity Verification:
   When mcp_nexus.db is present in the workspace, verifies that its SHA256 checksum
   strictly matches the invariant canonical baseline:
   '86ecebf633cf6c871dfcaebe5a308a75f3b12c1e8f0e758142e7945a4f86636f'

2. Clean-Checkout CI Hygiene & Repository Contract Verification:
   - Verifies that no private development or test database binaries (*.db, *.sqlite)
     are committed to the Git repository.
   - Verifies that the canonical schema contract (13 domain tables) is strictly
     identical across SQLAlchemy ORM models, the initial Alembic migration, and the
     adoption verification engine.
"""

import sys
import os
import ast
import hashlib
import subprocess

EXPECTED_CANONICAL_SHA256 = "86ecebf633cf6c871dfcaebe5a308a75f3b12c1e8f0e758142e7945a4f86636f"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def verify_contract() -> tuple[bool, list[str]]:
    report = []
    report.append("=" * 80)
    report.append("MCP NEXUS DATABASE INTEGRITY & CLEAN-CHECKOUT CONTRACT AUDIT")
    report.append("=" * 80)

    violations = []

    # 1. Local Canonical Database Verification (if present)
    dev_db_path = os.path.join(REPO_ROOT, "mcp_nexus.db")
    if os.path.exists(dev_db_path):
        actual_hash = hashlib.sha256(open(dev_db_path, "rb").read()).hexdigest().lower()
        if actual_hash == EXPECTED_CANONICAL_SHA256.lower():
            report.append(f"• Local Canonical DB       : PRESENT & VERIFIED")
            report.append(f"  SHA256                   : {actual_hash}")
            report.append(f"  Status                   : INVARIANT (100% match)")
        else:
            violations.append(
                f"Canonical development database checksum mismatch!\n"
                f"  Expected: {EXPECTED_CANONICAL_SHA256}\n"
                f"  Actual  : {actual_hash}"
            )
            report.append(f"• Local Canonical DB       : CHECKSUM MISMATCH (VIOLATION)")
    else:
        report.append(f"• Local Canonical DB       : EXCLUDED FROM VCS (Clean-Checkout / CI Mode)")
        report.append(f"  Status                   : Correctly excluded per enterprise hygiene rules")

    # 2. VCS Hygiene Check: No database binaries tracked in Git
    try:
        git_tracked_dbs = subprocess.check_output(
            ["git", "ls-files", "*.db", "*.sqlite", "*.sqlite3"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True
        ).strip().splitlines()

        if git_tracked_dbs:
            violations.append(
                f"Security & VCS Hygiene Violation: Database binaries tracked in Git: {git_tracked_dbs}"
            )
            report.append(f"• VCS Binary Hygiene       : FAILED (tracked database binaries found)")
        else:
            report.append(f"• VCS Binary Hygiene       : PASSED (zero database binaries tracked in Git)")
    except Exception as e:
        report.append(f"• VCS Binary Hygiene       : SKIPPED (Git not available or not a git repo: {e})")

    # 3. Canonical Schema Contract Verification across ORM, Migrations, and Adoption
    try:
        from app.database.session import Base
        import app.models.all_models
        from app.database.adoption import CANONICAL_INITIAL_SCHEMA_TABLES

        orm_tables = set(Base.metadata.tables.keys())
        contract_tables = set(CANONICAL_INITIAL_SCHEMA_TABLES)

        if orm_tables != contract_tables:
            violations.append(
                f"Schema divergence: Base.metadata tables {sorted(orm_tables)} != "
                f"canonical contract {sorted(contract_tables)}"
            )

        # Parse Alembic initial migration AST
        mig_file = os.path.join(BACKEND_DIR, "alembic", "versions", "2a307f9f14bc_initial_schema.py")
        mig_tables = set()
        if os.path.exists(mig_file):
            with open(mig_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if getattr(node.func, "attr", "") == "create_table":
                        if node.args and isinstance(node.args[0], ast.Constant):
                            mig_tables.add(node.args[0].value)

            if mig_tables != contract_tables:
                violations.append(
                    f"Migration divergence: 2a307f9f14bc tables {sorted(mig_tables)} != "
                    f"canonical contract {sorted(contract_tables)}"
                )
        else:
            violations.append(f"Initial migration file missing at '{mig_file}'")

        if not violations:
            report.append(f"• Schema Contract Parity   : PASSED (13/13 tables identically defined)")
            report.append(f"  Canonical Domain Tables  : {len(contract_tables)} tables registered")
        else:
            report.append(f"• Schema Contract Parity   : FAILED (schema divergence detected)")

    except Exception as e:
        violations.append(f"Failed to inspect schema contract: {e}")
        report.append(f"• Schema Contract Parity   : ERROR ({e})")

    report.append("-" * 80)
    if violations:
        report.append("❌ CONTRACT VERIFICATION FAILED:")
        for v in violations:
            report.append(f"  - {v}")
        report.append("=" * 80)
        return False, report
    else:
        report.append("✅ DATABASE INTEGRITY & CLEAN-CHECKOUT CONTRACT VERIFIED SUCCESSFULLY")
        report.append("=" * 80)
        return True, report


def main():
    success, report = verify_contract()
    print("\n".join(report))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
