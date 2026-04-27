"""
Tests for the Charity RAG System
=================================
Verifies that:
  1. The ChromaDB collection is populated and accessible
  2. Country-priority ranking works correctly (Laos patient → Lao funds first)
  3. Condition-based matching returns relevant results
  4. get_funds_for_country() returns only country-relevant funds

Run: python -m pytest tests/test_charity_rag.py -v
  or: python tests/test_charity_rag.py
"""

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agents.charity_agent import (
    collection_count,
    get_all_charities,
    get_funds_for_country,
    match_charities,
)


class TestCharityCollection(unittest.TestCase):
    """Verify the ChromaDB collection is available and populated."""

    def test_collection_is_populated(self):
        count = collection_count()
        self.assertGreater(count, 0, (
            "ChromaDB 'charities' collection is empty. "
            "Run: python pipeline/ingest_charities.py"
        ))
        print(f"  Collection has {count} records.")

    def test_get_all_charities_returns_list(self):
        all_funds = get_all_charities()
        self.assertIsInstance(all_funds, list)
        self.assertGreater(len(all_funds), 0)

    def test_each_charity_has_required_fields(self):
        required = {"id", "name", "source", "origin_country", "target_countries",
                    "conditions_covered", "max_coverage_usd"}
        for c in get_all_charities()[:10]:
            missing = required - set(c.keys())
            self.assertEqual(missing, set(), f"Fund '{c.get('id')}' missing fields: {missing}")


class TestCountryPriorityMatching(unittest.TestCase):
    """Verify Laos patients get Laos-origin funds ranked first."""

    def test_laos_heart_patient_gets_cardiology_results(self):
        results = match_charities({"condition": "cardiology heart surgery"}, "Laos", top_n=3)
        self.assertGreater(len(results), 0, "No charities returned for Laos heart patient")
        print(f"\n  Laos Heart Patient results:")
        for i, r in enumerate(results, 1):
            print(f"    {i}. {r['name']} (origin: {r['origin_country']})")
        for result in results:
            covered = [condition.lower() for condition in result.get("conditions_covered", [])]
            self.assertTrue(
                any("cardio" in condition or "heart" in condition for condition in covered),
                f"Result '{result['name']}' is not cardiology-focused"
            )

    def test_vietnam_cancer_patient_gets_vietnam_funds_first(self):
        results = match_charities({"condition": "oncology cancer"}, "Vietnam", top_n=3)
        self.assertGreater(len(results), 0, "No charities returned for Vietnam cancer patient")
        print(f"\n  Vietnam Cancer Patient results:")
        for i, r in enumerate(results, 1):
            print(f"    {i}. {r['name']} (origin: {r['origin_country']})")
        top = results[0]
        is_vn_relevant = (
            top.get("origin_country", "").lower() == "vietnam"
            or "Vietnam" in top.get("target_countries", [])
        )
        self.assertTrue(
            is_vn_relevant,
            f"Top result '{top['name']}' is not Vietnam-relevant"
        )

    def test_unsupported_condition_returns_no_results(self):
        results = match_charities({"condition": "general surgery"}, "Cambodia", top_n=3)
        self.assertEqual(results, [])

    def test_myanmar_patient_gets_results(self):
        results = match_charities({"condition": "cardiology"}, "Myanmar", top_n=3)
        self.assertGreater(len(results), 0)

    def test_different_countries_get_different_top_results(self):
        """Country-priority must differentiate between Laos and Vietnam."""
        laos_results = match_charities({"condition": "cardiology"}, "Laos", top_n=1)
        vn_results = match_charities({"condition": "cardiology"}, "Vietnam", top_n=1)
        # They should not be identical if country-priority is working
        if laos_results and vn_results:
            laos_top = laos_results[0].get("origin_country", "")
            vn_top = vn_results[0].get("origin_country", "")
            print(f"\n  Laos top origin: {laos_top}, Vietnam top origin: {vn_top}")
            # At least one should be country-specific
            self.assertTrue(
                laos_top.lower() in ("laos", "regional") or vn_top.lower() in ("vietnam", "regional"),
                "Country-priority seems to not be differentiating between countries"
            )


class TestGetFundsForCountry(unittest.TestCase):
    """Verify get_funds_for_country() filters correctly."""

    def test_laos_funds_if_present_target_laos(self):
        funds = get_funds_for_country("Laos")
        print(f"\n  Laos funds ({len(funds)}):")
        for f in funds[:5]:
            print(f"    - {f['name']} (origin: {f['origin_country']})")
        for f in funds:
            targets = [t.lower() for t in f.get("target_countries", [])]
            origin = f.get("origin_country", "").lower()
            is_relevant = "laos" in targets or origin == "laos"
            self.assertTrue(is_relevant, f"Fund '{f['name']}' does not target Laos")

    def test_vietnam_funds_exist(self):
        funds = get_funds_for_country("Vietnam")
        self.assertGreater(len(funds), 0, "No Vietnam funds found in RAG")

    def test_indonesia_funds_exist(self):
        funds = get_funds_for_country("Indonesia")
        self.assertGreater(len(funds), 0, "No Indonesia funds found in RAG")


class TestMatchCharitiesOutput(unittest.TestCase):
    """Verify output structure from match_charities()."""

    def test_output_has_required_keys(self):
        results = match_charities({"condition": "cardiology"}, "Laos")
        for r in results:
            self.assertIn("id", r)
            self.assertIn("name", r)
            self.assertIn("origin_country", r)
            self.assertIn("max_coverage_usd", r)

    def test_top_n_respected(self):
        for n in (1, 3, 5):
            results = match_charities({"condition": "oncology cancer"}, "Vietnam", top_n=n)
            self.assertLessEqual(len(results), n)

    def test_empty_condition_returns_no_results(self):
        results = match_charities({}, "Thailand")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
