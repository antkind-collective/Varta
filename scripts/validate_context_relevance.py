import sys
import os
import json
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.context_relevance_validator import ContextRelevanceValidator

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    print("=" * 80)
    print("VARTA — Context-Driven Corpus Filtering Layer Validation Suite")
    print("=" * 80)

    validator = ContextRelevanceValidator()
    report = validator.run_all_checks()

    print(f"\nTotal Validation Checks: {report['total_checks']}")
    print(f"Passed Checks: {report['passed_checks']}")
    print(f"Compliance Percentage: {report['compliance_pct']}%\n")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    for idx, item in enumerate(report["details"], 1):
        status = "[PASSED]" if item["passed"] else "[FAILED]"
        print(f"[{idx}/{report['total_checks']}] {item['check']}: {status}")
        if "decision" in item:
            print(f"   Decision: {item['decision']} | Score: {item['score']} | Reason: {item['reason']}")
        if "stats" in item:
            print(f"   Batch Stats: Passed {item['stats']['total_passed']}/{item['stats']['total_inspected']} (Excluded {item['stats']['total_excluded']})")
        print()

    print("=" * 80)
    if report["compliance_pct"] == 100.0:
        print("ALL 8 VALIDATION SCENARIOS COMPLIANT AND VERIFIED (100% SUCCESS)")
        print("=" * 80)
        sys.exit(0)
    else:
        print("VALIDATION SUITE FAILED")
        print("=" * 80)
        sys.exit(1)

if __name__ == "__main__":
    main()
