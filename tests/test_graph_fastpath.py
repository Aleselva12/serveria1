import unittest

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END

from graph import _bounded_tool_calls, after_tools


def call(name, ident):
    return {"name": name, "args": {}, "id": ident, "type": "tool_call"}


class FastPathTests(unittest.TestCase):
    def test_parallel_reads_are_kept_but_writes_are_serialized(self):
        reads = AIMessage(
            content="",
            tool_calls=[
                call("system_status_tool", "1"),
                call("recall_memory_tool", "2"),
            ],
        )
        bounded = _bounded_tool_calls(reads)
        self.assertEqual(len(bounded.tool_calls), 2)

        mixed = AIMessage(
            content="",
            tool_calls=[
                call("remember_tool", "1"),
                call("system_status_tool", "2"),
            ],
        )
        bounded = _bounded_tool_calls(mixed)
        self.assertEqual(len(bounded.tool_calls), 1)
        self.assertEqual(bounded.tool_calls[0]["name"], "remember_tool")

    def test_delegation_and_deterministic_tools_can_end_without_rewrite(self):
        for name in ("search_agent_tool", "calculator_tool", "system_status_tool"):
            ai = AIMessage(content="", tool_calls=[call(name, "1")])
            state = {
                "messages": [
                    ai,
                    ToolMessage(content="risultato finale", tool_call_id="1"),
                ]
            }
            self.assertEqual(after_tools(state), END)

        ai = AIMessage(content="", tool_calls=[call("recall_memory_tool", "1")])
        state = {
            "messages": [
                ai,
                ToolMessage(content="memorie", tool_call_id="1"),
            ]
        }
        self.assertEqual(after_tools(state), "agent")


if __name__ == "__main__":
    unittest.main()
