"""Home update flow reuses the authenticated fixed-operation host bridge."""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from core import desktop_updates as updates


class HomeUpdaterBridgeTests(unittest.TestCase):
    def test_preparation_uses_main_git_workspace_and_fixed_operations(self):
        with patch.object(updates, "desktop", return_value=False), \
             patch("programmer_agent.releases.status", return_value={"available": True}), \
             patch("programmer_agent.releases.create", return_value={"id": "workspace-1"}) as create, \
             patch("programmer_agent.releases.commit", return_value={"commit": "a" * 40}) as commit, \
             patch("programmer_agent.releases.request", return_value={"status": "queued"}) as request:
            self.assertEqual(updates.prepare_server()["status"], "queued")
        create.assert_called_once()
        commit.assert_called_once_with("workspace-1", "Prepare current main for deployment")
        request.assert_called_once_with("POST", "/jobs", {
            "kind": "prepare", "workspace_id": "workspace-1", "commit": "a" * 40
        })

    def test_unconfigured_updater_never_creates_workspace(self):
        with patch.object(updates, "desktop", return_value=False), \
             patch("programmer_agent.releases.status", return_value={"available": False}), \
             patch("programmer_agent.releases.create") as create:
            with self.assertRaises(HTTPException) as raised:
                updates.prepare_server()
            self.assertEqual(raised.exception.status_code, 503)
            create.assert_not_called()

    def test_installation_requires_verified_exact_release(self):
        data = updates.ApplyServerRequest(release_id="12345678-1234-1234-1234-123456789abc", expected_commit="b" * 40)
        with patch.object(updates, "desktop", return_value=False), \
             patch("programmer_agent.releases.request", side_effect=[
                 {"status": "ready", "kind": "prepare", "commit": "b" * 40},
                 {"status": "queued"}
             ]) as request:
            self.assertEqual(updates.apply_server(data)["status"], "queued")
            self.assertEqual(request.call_args.args, ("POST", "/jobs", {
                "kind": "apply", "release_id": data.release_id, "commit": data.expected_commit
            }))

    def test_installation_rejects_unverified_candidate(self):
        data = updates.ApplyServerRequest(release_id="12345678-1234-1234-1234-123456789abc", expected_commit="b" * 40)
        with patch.object(updates, "desktop", return_value=False), \
             patch("programmer_agent.releases.request", return_value={
                 "status": "failed", "kind": "prepare", "commit": "b" * 40
             }) as request:
            with self.assertRaises(HTTPException) as raised:
                updates.apply_server(data)
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
