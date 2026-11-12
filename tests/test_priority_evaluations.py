import asyncio
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from core.api import roadmap_classifier_api as classifier
from core.domain import priority_evaluations as store
from tests.test_roadmap_classifier import FakeResponse, goal, result


class PriorityEvaluationTests(unittest.TestCase):
    def setUp(self):
        for target, kwargs in [
            ("core.infra.run_lifecycle.create_run", {"return_value": {"id": "test-run"}}),
            ("core.infra.run_lifecycle.transition_run", {}),
            ("core.infra.execution_traces.append_event", {}),
        ]:
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def reply(self, **metadata):
        return {"message":{"content":json.dumps({"items":[result("T1")]})}, **metadata}

    def test_provider_identity_is_confirmed_and_titles_come_from_requested_objectives(self):
        with patch.object(classifier,"model_status",return_value={"available":True,"installed":True}), patch.object(classifier,"urlopen",return_value=FakeResponse(self.reply(model=classifier.MODEL,done=True))):
            evaluation = classifier._evaluate(classifier.PreviewRequest(objectives=[goal()]))
        self.assertTrue(evaluation["model_verified"])
        self.assertEqual(evaluation["reported_model"], classifier.MODEL)
        self.assertEqual(evaluation["ratings"][0]["title"], goal().title)
        self.assertEqual(evaluation["objective_count"],1)
        self.assertEqual(evaluation["weights"],classifier.WEIGHTS)
        self.assertIn("evaluated_at",evaluation)

    def test_wrong_or_incomplete_provider_reply_is_rejected(self):
        for metadata in ({"model":"wrong-model","done":True},{"model":classifier.MODEL,"done":False}):
            with patch.object(classifier,"model_status",return_value={"available":True,"installed":True}), patch.object(classifier,"urlopen",return_value=FakeResponse(self.reply(**metadata))):
                with self.assertRaises(HTTPException) as error:
                    classifier._evaluate(classifier.PreviewRequest(objectives=[goal()]))
                self.assertEqual(error.exception.status_code,422)

    def test_missing_native_model_metadata_remains_explicitly_unconfirmed(self):
        with patch.object(classifier,"model_status",return_value={"available":True,"installed":True}), patch.object(classifier,"urlopen",return_value=FakeResponse(self.reply())):
            evaluation=classifier._evaluate(classifier.PreviewRequest(objectives=[goal()]))
        self.assertFalse(evaluation["model_verified"])
        self.assertIsNone(evaluation["reported_model"])

    def test_success_is_saved_for_home_and_failures_never_replace_previous_result(self):
        evaluation={"model":"selected","reported_model":"selected","objective_count":1,"ratings":[],"writes_map":False}
        with patch.object(classifier,"_evaluate",return_value=evaluation),patch.object(store,"save",return_value=True) as save:
            response=asyncio.run(classifier.classifier_preview(classifier.PreviewRequest(objectives=[goal()])))
            self.assertTrue(response["persisted"])
            save.assert_called_once_with(evaluation)
        with patch.object(classifier,"_evaluate",side_effect=HTTPException(422,"Invalid output")),patch.object(store,"save") as save:
            with self.assertRaises(HTTPException):
                asyncio.run(classifier.classifier_preview(classifier.PreviewRequest(objectives=[goal()])))
            save.assert_not_called()

    def test_save_failure_keeps_preview_and_explains_unchanged_homepage(self):
        with patch.object(classifier,"_evaluate",return_value={"model":"selected","reported_model":"selected","objective_count":1,"ratings":[]}),patch.object(store,"save",return_value=False):
            response=asyncio.run(classifier.classifier_preview(classifier.PreviewRequest(objectives=[goal()])))
        self.assertFalse(response["persisted"])
        self.assertIn("non salvata",response["persistence_detail"])

    def test_architecture_separates_configured_model_from_last_used_model(self):
        previous={"model":"previous-request","reported_model":"previous-reported","model_verified":True,"evaluated_at":"2026-11-06T00:00:00+00:00"}
        with patch.object(classifier,"model_status",return_value={"model":"current","available":True,"installed":True}),patch.object(store,"latest",return_value={"evaluation":previous,"available":True}):
            status=classifier.classifier_status()
        self.assertEqual(status["model"],"current")
        self.assertEqual(status["last_evaluation"]["reported_model"],"previous-reported")
        self.assertTrue(status["separate_from_supervisor"])

    def test_reads_never_trigger_inference_and_storage_errors_are_not_empty_successes(self):
        with patch("core.infra.database.DATABASE_URL","configured"),patch("core.infra.database.db_connection") as db,patch.object(classifier,"_evaluate") as evaluate:
            db.return_value.__enter__.return_value.execute.return_value.fetchone.return_value={"snapshot":{"ratings":[{"id":"T1"}]}}
            self.assertTrue(classifier.latest_evaluation()["available"])
            self.assertFalse(db.call_args.kwargs["ensure_schema"])
            evaluate.assert_not_called()
        with patch("core.infra.database.DATABASE_URL","configured"),patch("core.infra.database.db_connection",side_effect=OSError("private-details")):
            self.assertEqual(store.latest(),{"evaluation":None,"available":False})


if __name__ == "__main__":
    unittest.main()
