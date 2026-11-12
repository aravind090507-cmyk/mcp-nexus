"""
Risk Intelligence Engine
Evaluates and correlates cross-server enterprise telemetry across ERP, Equipment, and Inventory domains.
Generates structured, auditable risk assessments with factual evidence traceability.
Tailored for L&T Heavy Civil IC infrastructure operations.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

DATASET_NOTICE = "SYNTHETIC DEMONSTRATION DATA (L&T Heavy Civil IC Simulation — No live S/4HANA or Maximo link claimed)"

class RiskIntelligenceEngine:
    @staticmethod
    def correlate_and_assess_risk(
        executed_results: List[Dict[str, Any]],
        project_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Correlates outputs from ERP, Equipment, and Inventory MCP tools.
        Classifies risk as CRITICAL, HIGH, MEDIUM, LOW.
        Extracts supporting evidence, business impacts, and recommended actions.
        """
        # Extract domain-specific tool outputs
        erp_data: List[Dict[str, Any]] = []
        eqp_data: List[Dict[str, Any]] = []
        inv_data: List[Dict[str, Any]] = []

        for res in executed_results:
            server = res.get("server", "")
            tool = res.get("tool", "")
            output = res.get("output", {})

            if "ERP" in server or tool in ("get_project_status", "get_project_details", "get_financial_summary"):
                erp_data.append({"server": server, "tool": tool, "data": output})
            elif "Equipment" in server or tool in ("get_equipment_status", "get_maintenance_schedule"):
                eqp_data.append({"server": server, "tool": tool, "data": output})
            elif "Inventory" in server or tool in ("get_inventory", "get_low_stock_items", "check_stock_availability"):
                inv_data.append({"server": server, "tool": tool, "data": output})

        # Known project definitions for fallback or enrichment
        projects = {
            "PRJ-HAZ-002": {
                "name": "Hazira Cryogenic LNG Expansion & Gas Compression",
                "site": "Hazira Cryo Terminal Jetty 3",
                "division": "Hydrocarbon Engineering IC",
                "equipment_ids": ["EQP-CRN-8800"],
                "warehouse_ids": ["WH-HAZ-CENTRAL"]
            },
            "PRJ-MUM-001": {
                "name": "Mumbai Coastal Road Tunnel & Sea Bridge Package 4",
                "site": "Worli Sea Face Shaft",
                "division": "Heavy Civil Infrastructure IC",
                "equipment_ids": ["EQP-TBM-004"],
                "warehouse_ids": ["WH-MUM-WORLI"]
            },
            "PRJ-HYD-003": {
                "name": "Hyderabad Airport Metro Express Rail Package 1",
                "site": "Raidurg Elevated Corridor",
                "division": "Transportation Infrastructure IC",
                "equipment_ids": ["EQP-PLR-1400"],
                "warehouse_ids": ["WH-HYD-METRO"]
            }
        }

        # 1. Parse ERP findings
        erp_status_map = {}
        for item in erp_data:
            data = item["data"]
            if isinstance(data, dict):
                if "projects" in data and isinstance(data["projects"], list):
                    for p in data["projects"]:
                        erp_status_map[p["project_id"]] = {
                            "status": p.get("status", "UNKNOWN"),
                            "completion_pct": p.get("completion_pct", p.get("completion_percentage", 0)),
                            "critical_path_items": p.get("critical_issues", p.get("critical_path_items", [])),
                            "source_tool": item["tool"]
                        }
                elif "project_id" in data:
                    erp_status_map[data["project_id"]] = {
                        "status": data.get("status", "UNKNOWN"),
                        "completion_pct": data.get("completion_pct", data.get("completion_percentage", 0)),
                        "critical_path_items": data.get("critical_path_items", []),
                        "source_tool": item["tool"]
                    }
                elif "project" in data:
                    p = data["project"]
                    erp_status_map[p["project_id"]] = {
                        "status": p.get("status", "UNKNOWN"),
                        "completion_pct": p.get("completion_percentage", 0),
                        "critical_path_items": p.get("critical_path_items", []),
                        "source_tool": item["tool"]
                    }

        # 2. Parse Equipment findings
        equipment_map = {}
        maintenance_issues = []
        for item in eqp_data:
            data = item["data"]
            if isinstance(data, dict):
                records = data.get("maintenance_records") or data.get("overdue_tasks") or []
                if isinstance(records, list):
                    for task in records:
                        maintenance_issues.append({**task, "source_tool": item["tool"]})
                
                if "equipment" in data:
                    eq = data["equipment"]
                    equipment_map[eq["equipment_id"]] = {**eq, "source_tool": item["tool"]}
                elif "equipment_list" in data:
                    for eq in data["equipment_list"]:
                        equipment_map[eq["equipment_id"]] = {**eq, "source_tool": item["tool"]}

        # 3. Parse Inventory findings
        inventory_issues = []
        for item in inv_data:
            data = item["data"]
            if isinstance(data, dict):
                items_list = data.get("items") or data.get("low_stock_items") or []
                if isinstance(items_list, list):
                    for mat in items_list:
                        inventory_issues.append({**mat, "source_tool": item["tool"]})

        # 4. Synthesize project-by-project risk assessments
        project_assessments = []

        target_pids = [project_filter] if project_filter and project_filter in projects else list(projects.keys())

        for pid in target_pids:
            p_meta = projects[pid]
            p_name = p_meta["name"]
            p_erp = erp_status_map.get(pid, {})
            p_status = p_erp.get("status", "AVAILABLE")
            critical_paths = p_erp.get("critical_path_items", [])

            # Correlate equipment for this project
            p_equipment = [eq for eq_id, eq in equipment_map.items() if eq.get("project_id") == pid]
            p_maintenance = [m for m in maintenance_issues if m.get("project_id") == pid]

            # Correlate inventory for this project warehouses
            wh_ids = p_meta["warehouse_ids"]
            p_inventory = [inv for inv in inventory_issues if inv.get("warehouse_id") in wh_ids]

            # Determine Risk Score (0-100) & Classification
            score = 0
            evidence_points = []
            affected_assets = []
            affected_materials = []

            # Factor A: ERP Milestone Delay
            if "DELAYED" in p_status:
                score += 35
                evidence_points.append(f"ERP Project status flagged as {p_status} ({p_erp.get('completion_pct', 0)}% completed)")
            elif "ACTIVE" in p_status:
                score += 5
                evidence_points.append(f"ERP Project progress on track ({p_erp.get('completion_pct', 0)}% completed)")
            else:
                evidence_points.append("ERP status: Nominal or information unavailable from live probe")

            # Factor B: Equipment Telemetry & Maintenance Overdue
            for m in p_maintenance:
                overdue = m.get("overdue_days", 0)
                sev = m.get("severity", "LOW")
                eq_id = m.get("equipment_id", "UNKNOWN")
                affected_assets.append(f"{eq_id} ({m.get('task_name', 'Maintenance')})")

                if sev == "CRITICAL" or overdue > 30:
                    score += 40
                    evidence_points.append(f"Equipment {eq_id} overdue for overhaul by {overdue} days (Severity: {sev})")
                elif overdue > 0:
                    score += 20
                    evidence_points.append(f"Equipment {eq_id} maintenance past due by {overdue} days")

            for eq in p_equipment:
                vibe = eq.get("vibration_index_mm_s", 0)
                t_stat = eq.get("telemetry_status", "NOMINAL")
                if vibe > 5.0 or "ALARM" in t_stat:
                    score += 25
                    evidence_points.append(f"Vibration telemetry breach on {eq.get('equipment_id')}: {vibe} mm/s (Alert limit: 5.0 mm/s)")

            # Factor C: Inventory Stockouts & Deficits
            for inv in p_inventory:
                stat = inv.get("status", "")
                code = inv.get("item_code", "")
                lead = inv.get("lead_time_days", 0)
                deficit = inv.get("safety_stock_deficit", inv.get("safety_stock", 0) - inv.get("available_stock", 0))
                affected_materials.append(f"{code}: {inv.get('description', '')} ({stat})")

                if stat == "OUT_OF_STOCK":
                    score += 35
                    evidence_points.append(f"Material {code} is OUT OF STOCK (Deficit: {deficit} units, Lead time: {lead} days)")
                elif stat == "CRITICAL_LOW_STOCK":
                    score += 25
                    evidence_points.append(f"Material {code} at CRITICAL LOW STOCK (Available: {inv.get('available_stock')} vs Safety: {inv.get('safety_stock')})")
                elif stat == "LOW_STOCK":
                    score += 15
                    evidence_points.append(f"Material {code} stock below safety threshold (Deficit: {deficit})")

            # Classification
            if score >= 75:
                overall_risk = "CRITICAL"
                impact = f"Imminent operational halt at {p_meta['site']}. Compound bottleneck of delayed milestone, critical equipment maintenance alarm, and zero-stock material shortage."
                next_action = f"1. Issue emergency maintenance overhaul for {', '.join(affected_assets) or 'fleet assets'}. 2. Authorize expedited air-freight procurement for {', '.join(affected_materials) or 'critical inventory'}."
            elif score >= 50:
                overall_risk = "HIGH"
                impact = f"Significant schedule risk on critical path. Maintenance backlog or material shortages risk halting upcoming project milestones."
                next_action = f"Schedule immediate preventative inspection for plant assets and advance purchase orders for low-stock inventory."
            elif score >= 25:
                overall_risk = "MEDIUM"
                impact = f"Minor operational vulnerability detected. Materials or telemetry near warning thresholds; no active milestone stoppage."
                next_action = f"Monitor sensor telemetry and replenish warehouse safety stock before scheduled maintenance intervals."
            else:
                overall_risk = "LOW"
                impact = "Operations proceeding within nominal engineering tolerances. Fleet telemetry nominal and supply buffer verified."
                next_action = "Continue standard operational monitoring and regular telemetry polling."

            project_assessments.append({
                "project_id": pid,
                "project_name": p_name,
                "division": p_meta["division"],
                "site": p_meta["site"],
                "overall_risk": overall_risk,
                "risk_score": min(score, 100),
                "erp_status": p_status,
                "affected_equipment": affected_assets,
                "affected_materials": affected_materials,
                "evidence": evidence_points,
                "business_impact": impact,
                "recommended_action": next_action,
                "source_servers": list(set(r.get("server") for r in executed_results))
            })

        # Summary statistics
        critical_count = sum(1 for p in project_assessments if p["overall_risk"] == "CRITICAL")
        high_count = sum(1 for p in project_assessments if p["overall_risk"] == "HIGH")
        medium_count = sum(1 for p in project_assessments if p["overall_risk"] == "MEDIUM")
        low_count = sum(1 for p in project_assessments if p["overall_risk"] == "LOW")

        critical_projects = [p["project_id"] for p in project_assessments if p["overall_risk"] == "CRITICAL"]
        high_projects = [p["project_id"] for p in project_assessments if p["overall_risk"] == "HIGH"]

        return {
            "summary": {
                "total_projects_assessed": len(project_assessments),
                "critical_risks": critical_count,
                "high_risks": high_count,
                "medium_risks": medium_count,
                "low_risks": low_count,
                "critical_projects": critical_projects,
                "high_risk_projects": high_projects,
                "overall_system_health": "CRITICAL_ATTENTION_REQUIRED" if critical_count > 0 else "NOMINAL",
                "dataset_notice": DATASET_NOTICE
            },
            "projects": project_assessments,
            "evidence_details": {
                "equipment_issues": maintenance_issues,
                "inventory_shortages": inventory_issues,
                "erp_status_points": erp_status_map
            }
        }
