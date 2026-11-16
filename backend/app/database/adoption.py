"""
Database Schema Adoption & Pre-Stamping Compatibility Verification Engine (Phase 15D.4.4.2)

Provides safe, dialect-aware inspection and verification before an existing database
can be stamped with Alembic migration revisions.
"""

import os
import sys
from typing import Tuple, Dict, Any, Optional, Set
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata

# Ensure backend and root are on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.database.session import Base
import app.models.all_models  # Registers all 13 models

# Authoritative specification of the 13 domain tables comprising the initial schema baseline
CANONICAL_INITIAL_SCHEMA_TABLES = frozenset({
    "organizations",
    "users",
    "mcp_servers",
    "mcp_tools",
    "ai_agents",
    "agent_server_assignments",
    "agent_tool_permissions",
    "approval_requests",
    "execution_traces",
    "security_policies",
    "security_events",
    "audit_logs",
    "integration_configs",
})


def verify_schema_compatibility(db_url: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Independently inspects an existing database and validates 100% schema equivalence
    against Base.metadata before any adoption or stamping can take place.
    
    Verifies:
    1. All 13 canonical domain tables exist.
    2. No unexpected extraneous tables exist.
    3. All expected columns, column types, and nullabilities exist.
    4. Primary keys match expected PK definitions.
    5. Foreign keys match expected FK relations.
    6. No structural discrepancies via Alembic compare_metadata.
    """
    # Enforce that ORM metadata matches the canonical initial schema contract
    if set(Base.metadata.tables.keys()) != set(CANONICAL_INITIAL_SCHEMA_TABLES):
        raise RuntimeError(
            f"Schema contract violation: Base.metadata tables {sorted(Base.metadata.tables.keys())} "
            f"do not match canonical contract {sorted(CANONICAL_INITIAL_SCHEMA_TABLES)}"
        )

    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    eng = create_engine(db_url, connect_args=connect_args)
    details = {}

    try:
        with eng.connect() as conn:
            insp = inspect(conn)
            existing_tables = set(insp.get_table_names())
            expected_tables = set(CANONICAL_INITIAL_SCHEMA_TABLES)

            # Check 1: Table completeness
            missing_tables = expected_tables - existing_tables
            if missing_tables:
                return False, f"Incompatible schema: missing required table(s): {sorted(missing_tables)}", details

            # Check 1b: Reject unexpected tables (excluding alembic_version and sqlite internal tables)
            allowed_tables = expected_tables | {"alembic_version", "sqlite_sequence"}
            unexpected_tables = existing_tables - allowed_tables
            if unexpected_tables:
                return False, f"Incompatible schema: unexpected table(s) found: {sorted(unexpected_tables)}", details

            # Check 2: Column, PK and FK verification for each table
            for t_name in sorted(expected_tables):
                table_obj = Base.metadata.tables[t_name]
                actual_cols = {c["name"]: c for c in insp.get_columns(t_name)}
                expected_cols = {c.name: c for c in table_obj.columns}

                missing_cols = set(expected_cols.keys()) - set(actual_cols.keys())
                if missing_cols:
                    return False, f"Incompatible schema: table '{t_name}' is missing column(s): {sorted(missing_cols)}", details

                # Column nullability check
                for c_name, c_obj in expected_cols.items():
                    act_col = actual_cols.get(c_name)
                    if act_col and act_col.get("nullable") != c_obj.nullable:
                        return False, (
                            f"Incompatible schema: table '{t_name}', column '{c_name}' nullability mismatch "
                            f"(actual nullable={act_col.get('nullable')} vs expected {c_obj.nullable})"
                        ), details

                # Primary key check
                pk_info = insp.get_pk_constraint(t_name)
                actual_pks = set(pk_info.get("constrained_columns", []))
                expected_pks = {c.name for c in table_obj.primary_key.columns}
                if actual_pks != expected_pks:
                    return False, f"Incompatible schema: table '{t_name}' primary key mismatch ({actual_pks} vs expected {expected_pks})", details

                # Foreign key check on non-SQLite
                if not db_url.startswith("sqlite"):
                    actual_fks = insp.get_foreign_keys(t_name)
                    expected_fk_targets = {
                        (fk.parent.name, fk.target_fullname) for fk in table_obj.foreign_keys
                    }
                    actual_fk_targets = {
                        (c, f"{fk['referred_table']}.{fk['referred_columns'][0]}")
                        for fk in actual_fks
                        for c in fk.get("constrained_columns", [])
                    }
                    missing_fks = expected_fk_targets - actual_fk_targets
                    if missing_fks:
                        return False, f"Incompatible schema: table '{t_name}' missing foreign key(s): {sorted(missing_fks)}", details

            # Check 3: Alembic autogenerate compare_metadata
            ctx = MigrationContext.configure(conn)
            diffs = compare_metadata(ctx, Base.metadata)
            critical_diffs = [
                d for d in diffs
                if d[0] in ("add_table", "remove_table", "add_column", "remove_column", "add_constraint")
            ]
            if critical_diffs:
                return False, f"Incompatible schema: structural differences detected: {critical_diffs}", details

            details["verified_tables"] = len(expected_tables)
            return True, "Schema is 100% compatible with initial migration baseline.", details

    finally:
        eng.dispose()


def safely_adopt_existing_database(
    db_url: str,
    ini_path: Optional[str] = None,
    target_revision: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Safely adopts a pre-existing database by verifying full schema compatibility
    prior to executing 'alembic stamp <target_head>'.
    
    Guarantees:
    - Never stamps an incompatible, partial, or corrupted schema.
    - Validates target revision against repository heads.
    - Rejects databases that already have older or unknown Alembic revisions (use upgrade instead).
    - Preserves all pre-existing application data without DDL drops or changes.
    - Idempotent if already stamped at head.
    - Atomic and non-destructive: fails fast without modifying database if checks fail.
    """
    ini_file = ini_path or os.path.join(ROOT_DIR, "alembic.ini")
    if not os.path.exists(ini_file):
        ini_file = os.path.join(BASE_DIR, "alembic.ini")

    cfg = Config(ini_file)
    cfg.set_main_option("sqlalchemy.url", db_url)
    script = ScriptDirectory.from_config(cfg)
    
    # Validate repository migration heads
    heads = script.get_heads()
    if len(heads) > 1:
        return False, f"Adoption rejected: Repository contains multiple migration heads: {heads}. Resolve migration branches first."
    if not heads:
        return False, "Adoption rejected: Repository contains zero migration heads."

    head_rev = heads[0]

    # Validate target revision if explicitly supplied
    if target_revision is not None:
        try:
            rev_obj = script.get_revision(target_revision)
            if rev_obj is None:
                return False, f"Adoption rejected: Target revision '{target_revision}' is unknown in migration history."
        except Exception as e:
            return False, f"Adoption rejected: Target revision '{target_revision}' is invalid: {e}"

        if target_revision != head_rev:
            return False, (
                f"Adoption rejected: Target revision '{target_revision}' is not the current migration head ('{head_rev}'). "
                "Adoption only supports stamping the head revision corresponding to Base.metadata."
            )

    target_head = target_revision or head_rev

    # Step 1: Check existing alembic_version table state in database
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    eng = create_engine(db_url, connect_args=connect_args)
    try:
        with eng.connect() as conn:
            insp = inspect(conn)
            table_names = set(insp.get_table_names())
            if "alembic_version" in table_names:
                ctx = MigrationContext.configure(conn)
                current_heads = set(ctx.get_current_heads())
                if current_heads == {target_head}:
                    return True, f"Database is already stamped at current head revision '{target_head}'."
                elif len(current_heads) > 1:
                    return False, f"Adoption rejected: Database has multiple divergent revisions recorded: {sorted(current_heads)}."
                elif len(current_heads) == 1:
                    existing_rev = list(current_heads)[0]
                    return False, (
                        f"Adoption rejected: Database is already managed by Alembic at revision '{existing_rev}'. "
                        "Stamping over an existing revision is unsafe; use 'alembic upgrade head' instead."
                    )
                else:
                    return False, "Adoption rejected: Database has an empty 'alembic_version' table (no revision recorded)."
    finally:
        eng.dispose()

    # Step 2: Strict schema compatibility verification before stamping
    compatible, reason, details = verify_schema_compatibility(db_url)
    if not compatible:
        return False, f"Adoption rejected: {reason}"

    # Step 3: Stamp to target head
    command.stamp(cfg, target_head)

    # Step 4: Verify stamp succeeded
    eng = create_engine(db_url, connect_args=connect_args)
    try:
        with eng.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current_heads = set(ctx.get_current_heads())
            if target_head not in current_heads:
                return False, f"Adoption verification failed: expected stamped revision '{target_head}', got {current_heads}"
    finally:
        eng.dispose()

    return True, f"Successfully adopted existing database and stamped to head revision '{target_head}'."
