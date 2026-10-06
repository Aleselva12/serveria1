import unittest
from core.context_pages import resolve_context_pages, selected_tool_names

class OwnerContextSelectionTests(unittest.TestCase):
    def test_ciao_does_not_load_owner_context(self):
        selected=resolve_context_pages("ciao")
        self.assertNotIn("owner_context",[p.id for p in selected])
        self.assertNotIn("owner_context_tool",selected_tool_names(selected))

    def test_explicit_owner_context_request_loads_only_when_relevant(self):
        selected=resolve_context_pages("Usa il contesto personale e dimmi cosa sai di me")
        self.assertIn("owner_context",[p.id for p in selected])
        self.assertIn("owner_context_tool",selected_tool_names(selected))

if __name__ == "__main__":
    unittest.main()
