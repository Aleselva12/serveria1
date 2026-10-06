import unittest

from core.context_pages import resolve_context_pages, selected_tool_names, preload_context


class ContextPageTests(unittest.TestCase):
    def test_casual_chat_loads_no_domain_page_or_tool(self):
        selected = resolve_context_pages("ciao")
        self.assertEqual(selected, [])
        self.assertEqual(selected_tool_names(selected), [])

    def test_calendar_selects_calendar_only(self):
        selected = resolve_context_pages("Che appuntamenti ho domani?")
        ids = [page.id for page in selected]
        self.assertIn("calendar", ids)
        tools = selected_tool_names(selected)
        self.assertIn("calendar_list_events", tools)
        self.assertNotIn("programmer_agent_tool", tools)

    def test_programming_loads_programmer_capability(self):
        selected = resolve_context_pages("Controlla il codice della repository")
        ids = [page.id for page in selected]
        self.assertIn("programming", ids)
        self.assertIn("programmer_agent_tool", selected_tool_names(selected))

    def test_owner_context_preloads_without_exposing_tool_schema(self):
        from unittest.mock import patch
        selected = resolve_context_pages("Cosa sai di me?")
        self.assertIn("owner_context", [page.id for page in selected])
        self.assertEqual(selected_tool_names(selected), [])
        with patch("core.system_context.get_system_context", return_value={"content":"Owner facts","version":1}):
            data, providers = preload_context(selected)
        self.assertEqual(providers, ["owner_context"])
        self.assertIn("Owner facts", data)

    def test_pages_can_compose(self):
        selected = resolve_context_pages("Cerca nel file del server il problema")
        ids = [page.id for page in selected]
        self.assertIn("files_research", ids)
        self.assertIn("system", ids)
        self.assertLessEqual(len(ids), 3)


if __name__ == "__main__":
    unittest.main()
