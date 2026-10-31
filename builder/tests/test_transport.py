import unittest
from scripts.build_transport import hour,unique

class TransportValidationTests(unittest.TestCase):
    def test_service_day_times(self):
        self.assertEqual(hour('25:05:00'),25)
        self.assertEqual(hour('00:00:00'),0)
        for invalid in ('','08:99:00','99:00:00','24:01','-1:00:00'):
            with self.assertRaises(ValueError):hour(invalid)
    def test_duplicate_and_missing_source_identifiers_fail(self):
        with self.assertRaises(ValueError):unique([{'id':'1'},{'id':'1'}],'id')
        with self.assertRaises(ValueError):unique([{'id':''}],'id')
        self.assertEqual(len(unique([{'id':'1'},{'id':'2'}],'id')),2)
