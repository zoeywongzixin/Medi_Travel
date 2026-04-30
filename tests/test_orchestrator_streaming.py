import sys
import time
import types
import unittest
from unittest.mock import patch

chromadb_module = types.ModuleType("chromadb")
chromadb_module.PersistentClient = object
chromadb_module.Collection = object
chromadb_utils_module = types.ModuleType("chromadb.utils")
embedding_functions_module = types.ModuleType("chromadb.utils.embedding_functions")
embedding_functions_module.DefaultEmbeddingFunction = object
chromadb_utils_module.embedding_functions = embedding_functions_module
chromadb_module.utils = chromadb_utils_module

dotenv_module = types.ModuleType("dotenv")
dotenv_module.load_dotenv = lambda: None

serpapi_module = types.ModuleType("serpapi")

ollama_module = types.ModuleType("ollama")
ollama_module.Client = object
ollama_module.chat = lambda *args, **kwargs: {}

sys.modules.setdefault("chromadb", chromadb_module)
sys.modules.setdefault("chromadb.utils", chromadb_utils_module)
sys.modules.setdefault("chromadb.utils.embedding_functions", embedding_functions_module)
sys.modules.setdefault("dotenv", dotenv_module)
sys.modules.setdefault("serpapi", serpapi_module)
sys.modules.setdefault("ollama", ollama_module)

from agents import orchestrator


class OrchestratorStreamingTests(unittest.IsolatedAsyncioTestCase):
    def test_build_reasoning_prompt_is_slim_and_accessibility_focused(self):
        prompt = orchestrator._build_reasoning_prompt(
            doc={
                "name": "Dr Ada Lim",
                "hospital": "Sunrise Medical Centre",
                "specialty": "Orthopedic Surgery",
            },
            logistics={
                "recommendation": "Commercial Flight suitable for Wheelchair passengers",
                "notes": "Wheelchair assistance can be requested at the airport.",
                "ground_transport": [{"title": "Accessible Van KL"}],
            },
            origin_country="Vietnam",
            budget_usd=6000,
        )

        self.assertIn("Write exactly 2 short sentences.", prompt)
        self.assertIn("wheelchair accessibility or assisted travel support", prompt)
        self.assertIn("Dr Ada Lim", prompt)

    async def test_streaming_yields_packages_as_they_finish(self):
        hospitals = [
            {"name": "Doctor One", "hospital": "Hospital A", "specialty": "Oncology"},
            {"name": "Doctor Two", "hospital": "Hospital B", "specialty": "Cardiology"},
            {"name": "Doctor Three", "hospital": "Hospital C", "specialty": "Neurology"},
        ]
        logistics = {"recommendation": "Wheelchair support", "notes": "Airport wheelchair assistance available."}
        charities = [{"name": "Aid Fund"}]
        delays = {"Doctor One": 0.15, "Doctor Two": 0.01, "Doctor Three": 0.05}

        def fake_reasoning(doc, *_args, **_kwargs):
            time.sleep(delays[doc["name"]])
            return f"{doc['name']} reasoning"

        with patch("agents.orchestrator.match_hospitals", return_value=hospitals), \
             patch("agents.orchestrator.get_flight_options", return_value=logistics), \
             patch("agents.orchestrator.match_charities", return_value=charities), \
             patch("agents.orchestrator._generate_package_reasoning", side_effect=fake_reasoning):
            streamed_order = []
            async for package in orchestrator.orchestrate_packages_stream(
                medical_data={"condition": "test"},
                logistics_data={"mobility_level": "Wheelchair"},
                origin_country="Vietnam",
                budget_usd=6000,
            ):
                streamed_order.append(package["package_id"])

            ordered_packages = await orchestrator.orchestrate_packages_async(
                medical_data={"condition": "test"},
                logistics_data={"mobility_level": "Wheelchair"},
                origin_country="Vietnam",
                budget_usd=6000,
            )

        self.assertEqual(streamed_order, ["PKG_2", "PKG_3", "PKG_1"])
        self.assertEqual(
            [package["package_id"] for package in ordered_packages],
            ["PKG_1", "PKG_2", "PKG_3"],
        )


if __name__ == "__main__":
    unittest.main()
