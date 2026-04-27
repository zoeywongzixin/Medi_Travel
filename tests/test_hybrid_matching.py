"""Quick smoke tests for the hybrid search / rerank enhancements."""
import sys
sys.path.insert(0, ".")

# ─── Test 1: build_case_profile enrichment ───────────────────────────────────
from utils.medical_specialty import build_case_profile

profile = build_case_profile({
    "condition": "Lung Cancer",
    "sub_specialty_inference": "Medical Oncology",
    "severity": "Critical",
    "urgency": "High",
    "age_group": "Adult",
    "raw_summary": "Stage 3 NSCLC with metastasis",
})
assert profile["severity"] == "Critical", f"Expected Critical, got {profile['severity']}"
assert profile["urgency"] == "High",     f"Expected High, got {profile['urgency']}"
assert profile["age_group"] == "Adult",  f"Expected Adult, got {profile['age_group']}"
assert "oncology" in profile["groups"],  "Expected oncology group"
assert profile["lung_focus"] is True,    "Expected lung_focus True"
print("Test 1 PASS: build_case_profile enrichment")

# ─── Test 2: RRF helper ───────────────────────────────────────────────────────
from agents.medical_agent import _reciprocal_rank_fusion, _extract_query_tokens, _hard_group_gate

semantic_ids = ["doc_1", "doc_2", "doc_3"]
keyword_ranked = [("doc_2", 5), ("doc_4", 3), ("doc_1", 2)]
fused = _reciprocal_rank_fusion(semantic_ids, keyword_ranked)
assert fused[0] == "doc_2", f"Expected doc_2 first, got {fused[0]}"
print(f"Test 2 PASS: RRF fusion order = {fused}")

# ─── Test 3: _extract_query_tokens ───────────────────────────────────────────
tokens = _extract_query_tokens(profile)
assert "cancer" in tokens or "lung" in tokens, f"Expected clinical tokens, got {tokens}"
print(f"Test 3 PASS: query tokens = {sorted(tokens)[:8]}...")

# ─── Test 4: Hard gate relax-fallback ────────────────────────────────────────
candidates = [{"specialty": "Cardiology", "specialty_tags": "Cardiology", "rag_summary": "", "hospital": ""}]
gated = _hard_group_gate(candidates, required_groups={"oncology"})
assert gated == candidates, "Gate should relax to full list when none match"
print("Test 4 PASS: Hard gate relax-fallback works")

# ─── Test 5: rerank_agent _parse_ranked_ids ───────────────────────────────────
from agents.rerank_agent import _parse_ranked_ids

ids = _parse_ranked_ids('["doc_a", "doc_b", "doc_c"]')
assert ids == ["doc_a", "doc_b", "doc_c"], f"Unexpected: {ids}"

ids2 = _parse_ranked_ids('{"ranked": ["doc_x", "doc_y"]}')
assert ids2 == ["doc_x", "doc_y"], f"Unexpected: {ids2}"

ids3 = _parse_ranked_ids("some text before [\"id_1\", \"id_2\"] after")
assert ids3 == ["id_1", "id_2"], f"Unexpected regex fallback: {ids3}"
print("Test 5 PASS: _parse_ranked_ids handles array, wrapped object, and inline array")

# ─── Test 6: charity _priority enrichment ────────────────────────────────────
from agents.charity_agent import _priority

fund_active = {
    "id": "fund_1",
    "origin_country": "Vietnam",
    "target_countries": ["Vietnam"],
    "target_audience": ["Vietnam", "ASEAN"],
    "conditions_covered": ["oncology"],
    "max_coverage_usd": 2500,
    "active": True,
}
fund_zero = dict(fund_active)
fund_zero["max_coverage_usd"] = 0

md_critical = {"severity": "Critical", "urgency": "High"}
md_low      = {"severity": "Low",      "urgency": "Low"}

score_critical_active = _priority(
    fund_active, "Vietnam", "Lung Cancer", "oncology",
    semantic_ids={"fund_1"}, medical_data=md_critical,
)
score_critical_zero = _priority(
    fund_zero, "Vietnam", "Lung Cancer", "oncology",
    semantic_ids=set(), medical_data=md_critical,
)
score_low = _priority(
    fund_active, "Vietnam", "Lung Cancer", "oncology",
    semantic_ids=set(), medical_data=md_low,
)

assert score_critical_active > score_critical_zero, (
    f"Active+coverage should beat zero-coverage: {score_critical_active} vs {score_critical_zero}"
)
assert score_critical_active > score_low, (
    f"Critical+semantic+coverage should beat low urgency: {score_critical_active} vs {score_low}"
)
print(f"Test 6 PASS: charity priority scores — critical_active={score_critical_active}, "
      f"critical_zero={score_critical_zero}, low={score_low}")

print()
print("All smoke tests PASSED.")
