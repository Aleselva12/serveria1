import unittest

from core.context_pages import resolve_context_pages, selected_tool_names, preload_context, routing_text


class ContextPageTests(unittest.TestCase):
    def test_mail_audio_and_quotes_are_reachable_without_calendar_false_positive(self):
        for text, expected in (("Riassumi le mail", "email_agent_tool"),
                               ("Trascrivi questa registrazione", "audio_agent_tool"),
                               ("Prepara un preventivo", "email_agent_tool")):
            tools = selected_tool_names(resolve_context_pages(text))
            self.assertIn(expected, tools)
            self.assertNotIn("calendar_list_events", tools)

    def test_whole_words_and_normalized_phrases(self):
        self.assertNotIn("calendar", [p.id for p in resolve_context_pages("preventivo eventuale")])
        self.assertIn("owner_context", [p.id for p in resolve_context_pages("USA  IL\nCONTESTO personale")])

    def test_explicit_continuations_preserve_last_user_topic_not_attachment_text(self):
        history = [{"role":"user", "content":"Riassumi le mail\nAllegati forniti dall’utente: calendario"},
                   {"role":"assistant", "content":"Vuoi procedere?"}, {"role":"user", "content":"Sì, procedi"}]
        tools = selected_tool_names(resolve_context_pages(routing_text("Sì, procedi", history)))
        self.assertIn("email_agent_tool", tools)
        self.assertNotIn("calendar_list_events", tools)
        self.assertEqual(routing_text("Parliamo del calendario", history), "Parliamo del calendario")
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
