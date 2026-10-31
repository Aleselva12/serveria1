import unittest

from core.shadow_router import primary_route, route_for_tool


class ShadowRouterTests(unittest.TestCase):
    def test_route_categories_are_stable(self):
        self.assertEqual(route_for_tool("audio_agent_tool"), "audio")
        self.assertEqual(route_for_tool("email_agent_tool"), "email")
        self.assertEqual(route_for_tool("calendar_create"), "calendar")
        self.assertEqual(route_for_tool("library_search"), "library")

    def test_direct_when_no_tool_call_exists(self):
        class Message:
            tool_calls = []
        self.assertEqual(primary_route([Message()]), "direct")

    def test_first_actual_tool_call_becomes_primary_route(self):
        class Message:
            tool_calls = [{"name": "search_agent_tool"}]
        self.assertEqual(primary_route([Message()]), "research")


if __name__ == "__main__":
    unittest.main()
