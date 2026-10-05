import json
import os
import unittest
from unittest.mock import patch


class PublicDatabaseErrorsTests(unittest.TestCase):
    def test_connection_exception_is_not_exposed_through_any_status_consumer(self):
        from core.database import database_status
        from core.memory import memory_stats
        from core.runtime_api import component_states
        from api import health, memory_status
        secret = 'password=private-db-password host=internal-db /srv/private/db.sql SELECT confidential'
        with patch('core.database.database_configured', return_value=True), \
             patch('core.database.db_connection', side_effect=RuntimeError(secret)), \
             patch('core.runtime_status._ollama_online', return_value=False), \
             patch('api._ollama_online', return_value=False):
            for consumer in (database_status, memory_stats, health, memory_status, component_states):
                with self.subTest(consumer=consumer.__name__):
                    result=json.dumps(consumer())
                    for fragment in ('private-db-password','internal-db','db.sql','SELECT confidential','RuntimeError'):
                        self.assertNotIn(fragment,result)
                    self.assertIn('Database non raggiungibile',result)
