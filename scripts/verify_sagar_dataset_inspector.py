import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.dependencies import get_assistant_controller
from api.routes import get_review_records, submit_review_decision
from api.schemas import ReviewDecisionRequest

def test_sagar_scenarios():
    print("=" * 70)
    print("TESTING SAGAR DATASET INSPECTOR & REGION FILTERING")
    print("=" * 70)

    controller = get_assistant_controller()

    # 1. Before any query is sent (Empty Session)
    print("\n[Scenario 1] Opening review queue before any query is sent...")
    sess1 = controller.conversation_manager.create_session("sess_empty")
    res1 = get_review_records(session_id=sess1.session_id, controller=controller)
    print(f"  Topic: '{res1.context_topic}'")
    assert "assam" not in res1.context_topic.lower(), f"Expected no Assam in empty topic, got: {res1.context_topic}"
    assert res1.audit_stats is not None, "Audit stats should be populated"
    assert res1.audit_stats.total_master_records > 0, "Master records should be > 0"
    assert len(res1.audit_stats.preprocessing_stages) == 5, "Should have 5 preprocessing stages"
    print(f"  [PASS] Empty session shows Master Corpus ({res1.audit_stats.total_master_records} records, {len(res1.audit_stats.preprocessing_stages)} preprocessing stages), 0 false Assam data.")

    # 2. User queries for "Guwahati"
    print("\n[Scenario 2] User asks 'What is the flood situation in Guwahati?'...")
    sess_guwahati = controller.conversation_manager.create_session("sess_guwahati")
    resp_g = controller.process_query("What is the flood situation in Guwahati?", session_id=sess_guwahati.session_id)
    res_guwahati = get_review_records(session_id=sess_guwahati.session_id, controller=controller)
    print(f"  Resolved Topic: '{res_guwahati.context_topic}'")
    assert "guwahati" in res_guwahati.context_topic.lower(), f"Guwahati must be in topic, got: {res_guwahati.context_topic}"
    print(f"  [PASS] Topic correctly preserved specific city: '{res_guwahati.context_topic}'.")

    # 3. User queries for "Mumbai"
    print("\n[Scenario 3] User asks 'I need Mumbai dataset'...")
    sess_mumbai = controller.conversation_manager.create_session("sess_mumbai")
    resp_m = controller.process_query("I need Mumbai dataset for waterlogging", session_id=sess_mumbai.session_id)
    res_mumbai = get_review_records(session_id=sess_mumbai.session_id, controller=controller)
    print(f"  Resolved Topic: '{res_mumbai.context_topic}'")
    assert "mumbai" in res_mumbai.context_topic.lower(), f"Mumbai must be in topic, got: {res_mumbai.context_topic}"
    print(f"  [PASS] Topic correctly identified Mumbai: '{res_mumbai.context_topic}'.")

    # 4. Sagar filters by Region in the UI dropdown / tabs (e.g. region='mumbai', region='assam', region='bihar')
    print("\n[Scenario 4] Sagar selects 'Mumbai' tab in review inspector...")
    res_tab_mumbai = get_review_records(region="mumbai", controller=controller)
    print(f"  Tab Topic: '{res_tab_mumbai.context_topic}' | Records in view: {res_tab_mumbai.total_records}")
    assert "mumbai" in res_tab_mumbai.context_topic.lower(), f"Expected Mumbai in tab topic, got: {res_tab_mumbai.context_topic}"
    print(f"  [PASS] Region tab 'Mumbai' returned {res_tab_mumbai.total_records} records.")

    print("\n[Scenario 5] Sagar selects 'Bihar' tab in review inspector...")
    res_tab_bihar = get_review_records(region="bihar", controller=controller)
    print(f"  Tab Topic: '{res_tab_bihar.context_topic}' | Records in view: {res_tab_bihar.total_records}")
    assert "bihar" in res_tab_bihar.context_topic.lower(), f"Expected Bihar in tab topic, got: {res_tab_bihar.context_topic}"
    print(f"  [PASS] Region tab 'Bihar' returned {res_tab_bihar.total_records} records.")

    print("\n" + "=" * 70)
    print("ALL SAGAR INSPECTION SCENARIOS PASSED WITH ZERO CONTEXT LEAKAGE!")
    print("=" * 70)

if __name__ == "__main__":
    test_sagar_scenarios()
