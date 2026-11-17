import unittest
from dataclasses import asdict
from unittest.mock import Mock

from scripts.listing.game_delivery_policy import game_delivery_block, saved_game_delivery_block
from scripts.listing.keepa_product_client import parse_keepa_product
from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing


class DeliveryTests(unittest.TestCase):
    def check(self, expected, amazon_title="", **data):
        product = parse_keepa_product("B000TEST01", {"rootCategory": 637394, "title": "作品A", **data})
        for block in (game_delivery_block(product, amazon_title),
                      saved_game_delivery_block({"keepa_result": asdict(product), "amazon_result": {"title": amazon_title}})):
            self.assertEqual(block and block["listing_status"], expected, data)

    def test_online_base_game_without_title_keyword(self):
        for fields in [{"productType": 1}, {"binding": "Software_Download"}, {"productGroup": "Digital Video Games"},
                       {"style": "オンラインコード版"}, {"edition":"ダウンロード版"}, {"title": "作品A [Online Game Code]"},
                       {"features": ["ゲーム本編のコードをメールでお届けします。"]},
                       {"description": "Your game code will be sent via email."}]:
            with self.subTest(fields=fields):
                self.check("business_ng", **fields)
        self.check("business_ng", amazon_title="作品A オンラインコード版", productType=0, packageWeight=25)
        self.check("business_ng", title="作品A 本編＋DLC オンラインコード版")
        self.check("business_ng", title="特典付き 作品A オンラインコード版（パッケージ版と同内容）")
        self.check("business_ng", rootCategory=1, itemTypeKeyword="pc-games", productType=1,
                   categoryTree=[{"name":"PCゲーム・周辺機器"},{"name":"ゲームソフト"}])

    def test_real_media_and_bonus_codes(self):
        for fields in [{"title":"作品A パッケージ版（初回特典：オンラインコード）"},
                       {"title":"作品A パッケージ版【封入特典】衣装のダウンロード番号付き"},
                       {"title":"作品A コードインボックス"}, {"title":"作品A ゲームキーカード"},
                       {"title":"作品A ダウンロードカード版", "categoryTree":[{"catId":206233867051}]},
                       {"title":"作品A ダウンロード番号", "features":["番号を印刷したカードを発送します。"]},
                       {"binding":"DVD-ROM", "features":["予約特典コードをメールで送信します。"]},
                       {"productType":0,"binding":"DVD-ROM","variations":[{"asin":"SIBLING","attributes":[{"dimension":"エディション","value":"オンラインコード版"}]}]},
                       {"productType":0, "packageWeight":52, "binding":"Video Game"}]:
            with self.subTest(fields=fields):
                self.check(None, **fields)

    def test_ambiguous_games_are_not_published(self):
        self.check("missing_required_data", categoryTree=[{"catId":206233867051}])
        self.check("missing_required_data", title="作品A パッケージ版", productType=1)
        self.check("missing_required_data", title="作品A カード版", amazon_title="作品A オンラインコード版")
        self.check("missing_required_data", binding="Video Game")
        self.check("business_ng", title="作品A オンラインコード版（現物の発送はありません）")

    def test_out_of_scope_products_keep_existing_rules(self):
        self.check(None, title="追加コンテンツ シーズンパス オンラインコード版", productType=1)
        self.check(None, title="PlayStation ギフトカード オンラインコード版", productType=1)
        self.check(None, title="Xbox Game Pass Ultimate オンラインコード版", productType=1)
        self.check(None, title="PS5 Slim 冷却ファン デジタル版対応")
        self.check(None, rootCategory=13299531, title="emojam 専用ダウンロードカード")
        self.check(None, rootCategory=1, title="音楽制作ソフト オンラインコード版",binding="Software Download")

    def test_saved_approved_force_and_resume_do_not_call_writers(self):
        for store in ("rakuten_1", "rakuten_2"):
            dry = {"asin":"B000TEST01", "store_code":store, "management_number":"m",
                   "listing_status":"eligible","execution_allowed":True,"item_payload":{},"inventory_payload":{},
                   "keepa_result":{"category_id":637394, "binding":"software_download"},
                   "forced_bypass_checks":[{"rule":"prohibited_words"}]}
            for resume in (False, True):
                untouched=Mock(side_effect=AssertionError("unexpected IO"))
                result=execute_listing(ExecuteListingRequest(dry, execute=True, approved=True, resume_after_item_upsert=resume),
                                       image_downloader=untouched, image_client=untouched, item_client=untouched,
                                       inventory_client=untouched, category_checker=untouched)
                self.assertEqual(result["final_state"], "blocked")
                self.assertIn("オンラインコード納品",result["errors"][0])
                self.assertFalse(untouched.mock_calls)
