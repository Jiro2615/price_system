"""Lock lifecycle only, using fake connections. Never start a price worker."""
import ast
from contextlib import contextmanager
import json
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
from rakuten_price_coordination import price_item_write_slot
import rakuten_price_patch as price


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.conn=MagicMock()
        self.cur=self.conn.cursor.return_value.__enter__.return_value
        self.cur.fetchone.return_value=(True,)
    def test_session_lock_is_scoped_and_released_after_exception(self):
        with self.assertRaises(RuntimeError):
            with price_item_write_slot("RAKUTEN_2","Item_1",connect=lambda **kwargs:self.conn) as acquired:
                self.assertTrue(acquired);raise RuntimeError("test")
        self.assertEqual(self.cur.execute.call_args_list[0].args[1],("rakuten-price-item:rakuten_2:item_1",))
        self.assertIn("pg_advisory_unlock",self.cur.execute.call_args.args[0])
        self.conn.close.assert_called_once()
    def test_busy_lock_does_not_release_another_writer(self):
        self.cur.fetchone.return_value=(False,)
        with price_item_write_slot("rakuten_1","x",connect=lambda **kwargs:self.conn) as acquired:self.assertFalse(acquired)
        self.cur.execute.assert_called_once();self.conn.close.assert_called_once()
    def test_worker_patch_verification_and_db_acknowledgment_are_inside_slot(self):
        source=(Path(__file__).parents[1]/"scripts/rakuten_price_patch.py").read_text(encoding="utf-8-sig")
        tree=ast.parse(source)
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="main")
        slot=next(n for n in ast.walk(main) if isinstance(n,ast.With) and any(isinstance(i.context_expr,ast.Call)
            and isinstance(i.context_expr.func,ast.Name) and i.context_expr.func.id=="price_item_write_slot" for i in n.items))
        calls={n.func.id for n in ast.walk(slot) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertTrue({"call_item_patch","call_item_get","mark_success","mark_failed"}.issubset(calls))
        self.assertIn('"status":"write_busy"',ast.get_source_segment(source,slot))

    def test_main_uses_slot_for_fake_patch_verify_and_ack_and_skips_busy_items(self):
        for available in (True,False):
            with self.subTest(available=available),tempfile.TemporaryDirectory() as folder:
                result=Path(folder)/"result.json"
                row={"store_product_id":1,"store_id":2,"store_code":"rakuten_2","asin":"B000TEST01",
                    "mall_item_code":"item_1","sku_code":"sku_1","current_price":100,"target_price":120}
                inside=[]
                @contextmanager
                def slot(*args):
                    inside.append(True)
                    try:yield available
                    finally:inside.clear()
                def request(*args,**kwargs):self.assertTrue(inside);return {"status_code":200,"body":{}}
                def get(*args,**kwargs):self.assertTrue(inside);return {"variants":{"sku_1":{"standardPrice":"120"}}}
                def ack(*args,**kwargs):self.assertTrue(inside)
                with patch("sys.argv",["price","--store","rakuten_2","--execute","--verify","--verify-wait","0","--api-interval","0","--output",str(result)]), \
                     patch("psycopg.connect",side_effect=AssertionError("Live DB forbidden")), \
                     patch("requests.sessions.Session.request",side_effect=AssertionError("Live RMS forbidden")), \
                     patch.object(price,"fetch_price_targets",return_value=[row]), \
                     patch.object(price,"connect_db",return_value=MagicMock()), \
                     patch.object(price,"price_item_write_slot",side_effect=slot), \
                     patch.object(price,"call_item_patch",side_effect=request) as send, \
                     patch.object(price,"call_item_get",side_effect=get) as verify, \
                     patch.object(price,"mark_success",side_effect=ack) as success, \
                     patch.object(price,"mark_failed",side_effect=AssertionError("Unexpected fake failure")), \
                     patch("sys.stdout",new_callable=io.StringIO):
                    self.assertEqual(price.main(),0)
                data=json.loads(result.read_text(encoding="utf-8"))
                if available:
                    send.assert_called_once();verify.assert_called_once();success.assert_called_once()
                    self.assertEqual(data["success_count"],1)
                else:
                    send.assert_not_called();verify.assert_not_called();success.assert_not_called()
                    self.assertEqual(data["items"][0]["status"],"write_busy")


if __name__=="__main__":unittest.main()
