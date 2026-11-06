"""No external API calls or Ollama installation required to test advisory classifier."""
import asyncio
import io
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from core import roadmap_classifier_api as classifier


def goal(identifier="T1"):
    return classifier.Objective(id=identifier, title="Verifica orchestratore", summary="Controlli di collegamento tra chat e agenti")


def result(identifier, **overrides):
    data = {
        "id": identifier, "importance": 5, "urgency": 4, "blockers": 5,
        "impact": 4, "effort": 2, "risk": 3, "confidence": "low",
        "explanation": "La verifica di integrazione blocca il collaudo del percorso richiesto.",
    }
    data.update(overrides)
    return data


class FakeResponse:
    status = 200

    def __init__(self, response):
        self._data = io.BytesIO(json.dumps(response).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, size=None):
        return self._data.read(size)


class ClassifierTests(unittest.TestCase):
    def test_bounded_inputs_and_reject_duplicate_ids(self):
        with self.assertRaises(ValidationError):
            classifier.PreviewRequest(objectives=[goal()] * 2)
        with self.assertRaises(ValidationError):
            classifier.PreviewRequest(objectives=[goal(str(i)) for i in range(9)])
        with self.assertRaises(ValidationError):
            classifier.PreviewRequest(objectives=[goal()], additional_context="x" * 501)
        with self.assertRaises(ValidationError):
            classifier.Objective(id="../secrets", title="Bad task")

    def test_model_unavailable_does_not_attempt_inference(self):
        request = classifier.PreviewRequest(objectives=[goal()])
        with patch.object(classifier, "model_status", return_value={
            "model": "qwen3:1.7b", "available": True, "installed": False,
            "detail": "Modello assente",
        }), patch.object(classifier, "urlopen") as network:
            with self.assertRaises(HTTPException) as err:
                classifier._evaluate(request)
            self.assertEqual(err.exception.status_code, 409)
            network.assert_not_called()

    def test_structured_output_and_deterministic_score(self):
        request = classifier.PreviewRequest(objectives=[goal("T1"), goal("E1")],
            additional_context="Il sistema deve funzionare senza cloud.")
        payload = {"message": {"content": json.dumps({"items": [
            result("T1"), result("E1", importance=2, blockers=0, urgency=1, impact=2, effort=5),
        ]})}}
        with patch.object(classifier, "model_status", return_value={
            "model": "qwen3:1.7b", "available": True, "installed": True,
        }), patch.object(classifier, "urlopen", return_value=FakeResponse(payload)) as network:
            output = classifier._evaluate(request)
        self.assertEqual([v["id"] for v in output["ratings"]], ["T1", "E1"])
        self.assertFalse(output["writes_map"])
        self.assertTrue(output["not_a_test_result"])
        self.assertGreater(output["ratings"][0]["score"], output["ratings"][1]["score"])
        sent = json.loads(network.call_args.args[0].data)
        self.assertEqual(sent["options"]["num_predict"], 330)
        self.assertEqual(sent["options"]["num_ctx"], 4096)
        self.assertEqual(sent["keep_alive"], "5m")
        self.assertFalse(sent["stream"])
        self.assertFalse(sent["think"])
        self.assertEqual(sent["format"]["type"], "object")
        self.assertEqual(sent["model"], classifier.MODEL)
        self.assertNotIn("https://", network.call_args.args[0].full_url)

    def test_unknown_or_missing_task_ids_are_rejected_not_invented(self):
        for ids in [["T1", "F999"], ["T1", "T1"], ["T1"]]:
            payload = {"message": {"content": json.dumps({"items": [result(i) for i in ids]})}}
            with patch.object(classifier, "model_status", return_value={
                "model": "qwen3:1.7b", "available": True, "installed": True,
            }), patch.object(classifier, "urlopen", return_value=FakeResponse(payload)):
                with self.assertRaises(HTTPException) as err:
                    classifier._evaluate(classifier.PreviewRequest(objectives=[goal("T1"), goal("E1")]))
                self.assertEqual(err.exception.status_code, 422)

    def test_out_of_range_results_cannot_be_recorded(self):
        payload = {"message": {"content": json.dumps({"items": [result("T1", urgency=13)]})}}
        with patch.object(classifier, "model_status", return_value={
            "model": "qwen3:1.7b", "available": True, "installed": True,
        }), patch.object(classifier, "urlopen", return_value=FakeResponse(payload)):
            with self.assertRaises(HTTPException) as err:
                classifier._evaluate(classifier.PreviewRequest(objectives=[goal()]))
            self.assertEqual(err.exception.status_code, 422)

    def test_model_status_uses_only_local_ollama_catalog(self):
        with patch.object(classifier, "_read_tags", return_value={"qwen3:0.6b"}):
            status = classifier.model_status()
        if classifier.MODEL == "qwen3:1.7b":
            self.assertFalse(status["installed"])
            self.assertIn("ollama pull", status["detail"])

    def test_local_model_does_not_send_project_context_to_public_endpoint(self):
        from unittest.mock import patch
        for host in ("https://api.example.com:443", "http://203.0.113.7:11434"):
            with patch.object(classifier, "get_ollama_base_url", return_value=host):
                with self.assertRaises(ValueError):
                    classifier._local_ollama_url()
        for host in ("http://localhost:11434", "http://ollama:11434",
                     "http://host.docker.internal:11434", "https://worker.tailnet.ts.net"):
            with patch.object(classifier, "get_ollama_base_url", return_value=host):
                self.assertEqual(classifier._local_ollama_url(), host)

    def test_timeout_has_specific_diagnosis_and_larger_cold_start_budget(self):
        with patch.object(classifier, "model_status", return_value={"available": True, "installed": True}), patch.object(classifier, "urlopen", side_effect=TimeoutError):
            with self.assertRaises(HTTPException) as err:
                classifier._evaluate(classifier.PreviewRequest(objectives=[goal()]))
        self.assertEqual(err.exception.status_code, 504)
        self.assertIn(str(classifier.TIMEOUT_SECONDS), err.exception.detail)

    def test_activity_records_success_and_failure(self):
        from core import run_lifecycle
        from core import priority_evaluations
        request = classifier.PreviewRequest(objectives=[goal()])
        evaluation = {"model": classifier.MODEL, "reported_model": classifier.MODEL, "objective_count": 1}
        for failure in [False, True]:
            with patch("core.execution_traces.append_event"), patch.object(run_lifecycle, "create_run", return_value={"id": "test-run"}) as create, patch.object(run_lifecycle, "transition_run") as transition, patch.object(classifier, "_evaluate", side_effect=HTTPException(504, "Timeout") if failure else None, return_value=evaluation), patch.object(priority_evaluations, "save", return_value=True):
                if failure:
                    with self.assertRaises(HTTPException):
                        asyncio.run(classifier.classifier_preview(request))
                else:
                    self.assertEqual(asyncio.run(classifier.classifier_preview(request))["run_id"], "test-run")
                self.assertEqual(create.call_args.kwargs["target"], "roadmap_classifier")
                self.assertEqual([call.args[1] for call in transition.call_args_list], ["running", "failed" if failure else "completed"])

    def test_missing_activity_store_never_starts_untracked_inference(self):
        with patch("core.run_lifecycle.create_run", side_effect=OSError), patch.object(classifier, "_evaluate") as evaluate:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(classifier.classifier_preview(classifier.PreviewRequest(objectives=[goal()])))
            self.assertEqual(error.exception.status_code, 503)
            evaluate.assert_not_called()
        self.assertTrue(classifier._BUSY.acquire(blocking=False))
        classifier._BUSY.release()

    def test_scalars_are_capped_and_repeatable(self):
        hi = classifier.Rating.model_validate(result("T1", importance=5, urgency=5,
            blockers=5, impact=5, effort=0, risk=0))
        lo = classifier.Rating.model_validate(result("T1", importance=0, urgency=0,
            blockers=0, impact=0, effort=5, risk=5))
        self.assertEqual(classifier.score(hi), 100)
        self.assertEqual(classifier.score(lo), 0)


if __name__ == "__main__":
    unittest.main()
