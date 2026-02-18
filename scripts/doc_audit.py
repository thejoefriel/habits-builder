#!/usr/bin/env python3
"""
Documentation audit tool.

Reads .github/doc-schema.yml and checks the repo for:
- Missing required documents
- Missing optional documents
- Section completeness (expected headings present in each doc)
- Feature spec directory health
- AI agent config files

Outputs a human-readable report and exits non-zero if required docs are missing.

Usage:
    python scripts/doc_audit.py                    # Run audit, print report
    python scripts/doc_audit.py --json             # Output JSON report
    python scripts/doc_audit.py --exit-code        # Non-zero exit if gaps found
    python scripts/doc_audit.py --scaffold         # Print scaffold commands for missing docs
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml")
    sys.exit(1)


SCHEMA_PATH = ".github/doc-schema.yml"


def load_schema(repo_root: str) -> dict:
    schema_file = os.path.join(repo_root, SCHEMA_PATH)
    if not os.path.exists(schema_file):
        print(f"Error: Schema not found at {schema_file}")
        sys.exit(1)
    with open(schema_file) as f:
        return yaml.safe_load(f)


def extract_headings(filepath: str) -> list[str]:
    """Extract markdown headings from a file, normalised to lowercase."""
    if not os.path.exists(filepath):
        return []
    with open(filepath) as f:
        content = f.read()
    headings = []
    for line in content.splitlines():
        match = re.match(r"^#{1,6}\s+(.+)", line)
        if match:
            heading = match.group(1).strip()
            heading = re.sub(r"[^\w\s]", "", heading).strip()
            headings.append(heading.lower())
    return headings


def check_section_coverage(filepath: str, expected_sections: list[str]) -> dict:
    """Check what percentage of expected sections exist in the doc."""
    if not expected_sections:
        return {"total": 0, "found": 0, "missing": [], "score": 1.0}

    headings = extract_headings(filepath)
    found = []
    missing = []

    for section in expected_sections:
        section_lower = section.lower()
        if any(section_lower in h for h in headings):
            found.append(section)
        else:
            missing.append(section)

    score = len(found) / len(expected_sections) if expected_sections else 1.0
    return {
        "total": len(expected_sections),
        "found": len(found),
        "missing": missing,
        "score": round(score, 2),
    }


def audit_documents(schema: dict, repo_root: str) -> list[dict]:
    """Audit all documents defined in the schema."""
    results = []
    for doc in schema.get("documents", []):
        filepath = os.path.join(repo_root, doc["path"])
        exists = os.path.exists(filepath)
        sections = check_section_coverage(filepath, doc.get("sections", []))
        file_size = os.path.getsize(filepath) if exists else 0
        is_stub = exists and file_size < 200

        results.append({
            "id": doc["id"],
            "path": doc["path"],
            "required": doc.get("required", False),
            "exists": exists,
            "is_stub": is_stub,
            "file_size": file_size,
            "sections": sections,
            "template": doc.get("template", ""),
            "description": doc.get("description", ""),
        })
    return results


def audit_agent_config(schema: dict, repo_root: str) -> list[dict]:
    """Audit AI agent infrastructure files."""
    results = []
    for item in schema.get("agent_config", []):
        filepath = os.path.join(repo_root, item["path"])
        exists = os.path.exists(filepath)
        file_size = os.path.getsize(filepath) if exists else 0

        results.append({
            "id": item["id"],
            "path": item["path"],
            "required": item.get("required", False),
            "exists": exists,
            "file_size": file_size,
            "template": item.get("template", ""),
            "description": item.get("description", ""),
        })
    return results


def audit_feature_specs(schema: dict, repo_root: str) -> dict:
    """Audit the feature specs directory."""
    spec_config = schema.get("feature_specs", {})
    if not spec_config:
        return {"checked": False}

    directory = os.path.join(repo_root, spec_config.get("directory", "docs/features/"))
    dir_exists = os.path.isdir(directory)

    specs = []
    if dir_exists:
        for f in sorted(os.listdir(directory)):
            if f.endswith(".md") and not f.startswith("_") and f != "README.md":
                specs.append(f)

    template_path = os.path.join(repo_root, spec_config.get("template", ""))
    template_exists = os.path.exists(template_path)

    return {
        "checked": True,
        "directory": spec_config.get("directory", ""),
        "directory_exists": dir_exists,
        "template_exists": template_exists,
        "spec_count": len(specs),
        "specs": specs,
        "required": spec_config.get("required", False),
    }


def build_report(
    schema: dict,
    doc_results: list[dict],
    agent_results: list[dict],
    feature_result: dict,
) -> dict:
    """Build a structured audit report."""
    required_missing = [r for r in doc_results if r["required"] and not r["exists"]]
    optional_missing = [r for r in doc_results if not r["required"] and not r["exists"]]
    stubs = [r for r in doc_results if r["is_stub"]]
    incomplete = [r for r in doc_results if r["exists"] and r["sections"]["score"] < 1.0]
    agent_missing = [r for r in agent_results if r["required"] and not r["exists"]]

    total_docs = len(doc_results)
    existing_docs = sum(1 for r in doc_results if r["exists"])
    avg_section_score = 0.0
    scored = [r for r in doc_results if r["exists"] and r["sections"]["total"] > 0]
    if scored:
        avg_section_score = round(
            sum(r["sections"]["score"] for r in scored) / len(scored), 2
        )

    has_gaps = bool(required_missing or agent_missing)
    if feature_result.get("required") and not feature_result.get("directory_exists"):
        has_gaps = True
    if feature_result.get("required") and feature_result.get("spec_count", 0) == 0:
        has_gaps = True

    return {
        "project": schema.get("project", {}),
        "summary": {
            "total_documents": total_docs,
            "existing": existing_docs,
            "missing_required": len(required_missing),
            "missing_optional": len(optional_missing),
            "stubs": len(stubs),
            "incomplete_sections": len(incomplete),
            "agent_config_missing": len(agent_missing),
            "average_section_score": avg_section_score,
            "pass": not has_gaps,
        },
        "documents": doc_results,
        "agent_config": agent_results,
        "feature_specs": feature_result,
    }


def print_report(report: dict) -> None:
    """Print a human-readable audit report."""
    project = report["project"]
    summary = report["summary"]

    print("=" * 60)
    print(f"  Documentation Audit: {project.get('name', 'Unknown')}")
    print("=" * 60)
    print()

    status = "PASS" if summary["pass"] else "FAIL"
    print(f"  Status: {status}")
    print(f"  Documents: {summary['existing']}/{summary['total_documents']} present")
    print(f"  Section completeness: {int(summary['average_section_score'] * 100)}%")
    if summary["missing_required"]:
        print(f"  Required missing: {summary['missing_required']}")
    if summary["stubs"]:
        print(f"  Stubs (< 200 bytes): {summary['stubs']}")
    print()

    # Documents
    print("  Documents")
    print("  " + "-" * 56)
    for doc in report["documents"]:
        if doc["exists"]:
            score = doc["sections"]["score"]
            score_str = f"{int(score * 100)}%" if doc["sections"]["total"] > 0 else "n/a"
            stub_flag = " [stub]" if doc["is_stub"] else ""
            icon = "!" if score < 1.0 else " "
            print(f"  {icon} {doc['path']:40s} {score_str:>5s}{stub_flag}")
            if doc["sections"]["missing"]:
                for s in doc["sections"]["missing"]:
                    print(f"      missing section: {s}")
        else:
            req = "REQUIRED" if doc["required"] else "optional"
            print(f"  x {doc['path']:40s} [{req}]")
    print()

    # Agent config
    print("  Agent Config")
    print("  " + "-" * 56)
    for item in report["agent_config"]:
        if item["exists"]:
            print(f"    {item['path']:40s} ok")
        else:
            req = "REQUIRED" if item["required"] else "optional"
            print(f"  x {item['path']:40s} [{req}]")
    print()

    # Feature specs
    fs = report["feature_specs"]
    if fs.get("checked"):
        print("  Feature Specs")
        print("  " + "-" * 56)
        if fs["directory_exists"]:
            print(f"    {fs['directory']:40s} {fs['spec_count']} spec(s)")
            for spec in fs.get("specs", []):
                print(f"      - {spec}")
            if not fs["template_exists"]:
                print("    ! Template missing")
        else:
            print(f"  x {fs['directory']:40s} [directory missing]")
    print()
    print("=" * 60)


def print_scaffold_commands(report: dict) -> None:
    """Print commands to scaffold missing docs from templates."""
    print()
    print("Scaffold commands for missing documents:")
    print("-" * 40)

    has_any = False
    for doc in report["documents"]:
        if not doc["exists"] and doc["template"]:
            has_any = True
            print(f"  cp {doc['template']} {doc['path']}")

    for item in report["agent_config"]:
        if not item["exists"] and item["template"]:
            has_any = True
            parent = str(Path(item["path"]).parent)
            if parent != ".":
                print(f"  mkdir -p {parent}")
            print(f"  cp {item['template']} {item['path']}")

    fs = report["feature_specs"]
    if fs.get("checked") and not fs.get("directory_exists"):
        has_any = True
        print(f"  mkdir -p {fs['directory']}")
        if fs.get("template_exists"):
            template = report.get("feature_specs", {}).get("template", "")
            if template:
                print(f"  cp {template} {fs['directory']}_TEMPLATE.md")

    if not has_any:
        print("  Nothing to scaffold — all docs present.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Audit repository documentation")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument(
        "--exit-code",
        action="store_true",
        help="Exit non-zero if required docs missing",
    )
    parser.add_argument(
        "--scaffold",
        action="store_true",
        help="Print scaffold commands for missing docs",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to repo root (default: current directory)",
    )
    args = parser.parse_args()

    schema = load_schema(args.repo_root)
    doc_results = audit_documents(schema, args.repo_root)
    agent_results = audit_agent_config(schema, args.repo_root)
    feature_result = audit_feature_specs(schema, args.repo_root)
    report = build_report(schema, doc_results, agent_results, feature_result)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    if args.scaffold:
        print_scaffold_commands(report)

    if args.exit_code and not report["summary"]["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
