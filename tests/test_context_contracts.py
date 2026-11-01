import unittest

from core.context_contracts import ContextRequest, ContextPacket, ContextItem, ContextConflict


class ContextContractTests(unittest.TestCase):
    def test_request_is_bounded_and_permission_scoped(self):
        request = ContextRequest(
            task_id="task-1",
            requester="supervisor",
            objective="Trova l'ultimo preventivo del cliente",
            requested_topics=["cliente", "preventivo"],
            required_precision="exact",
            permission_scope=["library.read"],
        )
        self.assertEqual(request.version, 1)
        self.assertEqual(request.required_precision, "exact")
        self.assertEqual(request.permission_scope, ["library.read"])

    def test_packet_distinguishes_literal_and_summary_and_conflicts(self):
        literal = ContextItem(
            id="l1", kind="literal", content="dato", source_type="file",
            source_ref="cliente.docx", authority="primary"
        )
        summary = ContextItem(
            id="s1", kind="summary", content="sintesi", source_type="memory",
            source_ref="memory:1", authority="derived", expandable=True
        )
        packet = ContextPacket(
            packet_id="p1", task_id="task-1",
            literal_items=[literal], summarized_items=[summary],
            conflicts=[ContextConflict(topic="cliente", winner_item_id="l1", loser_item_ids=["s1"])],
            expandable_sections=["s1"], budget_used=512, budget_available=4096
        )
        self.assertEqual(packet.literal_items[0].kind, "literal")
        self.assertTrue(packet.summarized_items[0].expandable)
        self.assertEqual(packet.conflicts[0].winner_item_id, "l1")


if __name__ == "__main__":
    unittest.main()
