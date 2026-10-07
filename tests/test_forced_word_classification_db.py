"""Fake connection only; classification reads never write or fall back on errors."""
import unittest
from unittest.mock import MagicMock, patch
from scripts.listing import forced_word_classification_db as db
from scripts.listing.forced_word_policy import load_groups


class ClassificationDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.conn.__enter__.return_value = self.conn
        self.cur = self.conn.cursor.return_value.__enter__.return_value
        self.cur.fetchone.return_value = ("table",)

    def test_fresh_overrides_are_readonly_and_do_not_change_file_defaults(self):
        self.cur.fetchall.side_effect = [[("ou","ignore")],[("ou","block")]]
        with patch.object(db,"connect_db",return_value=self.conn) as connect:
            version, first = load_groups(use_database=True)
            _, second = load_groups(use_database=True)
        self.assertIn("shared-db-v2",version)
        self.assertEqual(first["ou"],"ignore")
        self.assertEqual(second["ou"],"block")
        self.assertEqual(load_groups()[1]["ou"],"review")
        self.assertEqual(connect.call_count,2)
        self.assertIn("default_transaction_read_only=on",connect.call_args.kwargs["options"])
        self.assertTrue(all("SELECT" in call.args[0] and not any(token in call.args[0] for token in ("UPDATE ","INSERT ","CREATE ")) for call in self.cur.execute.call_args_list))

    def test_missing_schema_invalid_data_and_failed_connection_stop_without_fallback(self):
        self.cur.fetchone.return_value = (None,)
        with patch.object(db,"connect_db",return_value=self.conn), self.assertRaises(db.ForcedWordClassificationReadError):
            load_groups(use_database=True)
        self.cur.fetchone.return_value = ("table",)
        self.cur.fetchall.return_value = [("ou","invalid")]
        with patch.object(db,"connect_db",return_value=self.conn), self.assertRaises(db.ForcedWordClassificationReadError):
            db.read_overrides()
        with patch.object(db,"connect_db",side_effect=RuntimeError("private-password-do-not-expose")), self.assertRaises(db.ForcedWordClassificationReadError) as error:
            load_groups(use_database=True)
        self.assertNotIn("private-password",str(error.exception))

    def test_current_active_words_are_store_scoped(self):
        self.cur.fetchall.return_value = [("OU",),("Foo",)]
        with patch.object(db,"connect_db",return_value=self.conn):
            self.assertEqual(db.read_active_words("rakuten_2"),["OU","Foo"])
        self.assertEqual(self.cur.execute.call_args.args[1],("rakuten_2",))
        self.assertIn("p.scope='global'",self.cur.execute.call_args.args[0])
        self.assertIn("p.enabled=TRUE",self.cur.execute.call_args.args[0])


if __name__=="__main__": unittest.main()
