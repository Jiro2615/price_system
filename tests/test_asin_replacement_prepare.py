from dataclasses import replace
from unittest.mock import patch
from tests.test_content_refresh_policy import ContentRefreshTests
from scripts.listing.rakuten_payload_builder import calc_listing_price


class AsinReplacementPrepareTests(ContentRefreshTests):
    def replacement(self, **kwargs):
        self.request.replace_source_asin = 'B000OLD001'
        self.existing['asin'] = self.request.replace_source_asin
        return self.prepare(**kwargs)

    def test_replacement_recalculates_price_and_stock_and_keeps_text_conversion(self):
        self.master.kako_ng[self.asin] = 'past NG'
        self.master.prohibited_words_rakuten = ['禁止語']
        self.keepa.avg90_new_offer_count = 0
        result = self.replacement()
        price = result['item_payload']['variants'][self.existing['management_number']]['standardPrice']
        self.assertEqual(int(price),calc_listing_price(amazon_price=1000,amazon_point=0,store_settings=self.store))
        self.assertNotEqual(int(price),self.existing['current_price'])
        self.assertEqual(result['inventory_payload']['quantity'],2)
        self.assertEqual(result['item_payload']['title'],'置換済 禁止語 商品')
        self.assertEqual(result['replace_source_asin'],'B000OLD001')

    def test_replacement_blocks_sale_conditions_that_ordinary_refresh_ignores(self):
        for changes in ({'available_qty':0},{'amazon_price':None},{'amazon_price':0},{'gift_available':False},
                        {'business_ng':True,'ng_reason':'配送NG'},{'page_asin':''},{'system_error':True}):
            with self.subTest(changes=changes):
                result = self.replacement(amazon_fetcher=lambda *_,changes=changes:replace(self.amazon,**changes))
                self.assertFalse(result['execution_allowed'])
                self.assertIsNone(result['item_payload'])

    def test_replacement_requires_exact_source(self):
        self.request.replace_source_asin = 'B000OLD001'
        with self.assertRaisesRegex(RuntimeError,'入れ替え元'):
            self.prepare()

    def test_no_observation_cannot_resume(self):
        result = self.replacement(amazon_fetcher=lambda *_:None)
        self.assertFalse(result['execution_allowed'])

    def test_replacement_refreshes_price_band_settings(self):
        from scripts.listing import prepare_service as prepare
        loader = lambda *args,**kwargs:self.store
        with patch.object(prepare,'load_store_settings',loader), patch.object(prepare,'_resolve_store_settings',return_value=self.store):
            result = self.replacement(store_settings_loader=loader)
        self.assertTrue(result['execution_allowed'])

    def test_saved_replacement_cannot_use_ordinary_refresh_writer(self):
        from scripts.listing.listing_execute_service import ExecuteListingRequest,execute_listing
        result = self.replacement()
        actual = execute_listing(ExecuteListingRequest(dry_run_result=result,execute=True,approved=True,
            asin=self.asin,content_refresh=True))
        self.assertEqual(actual['execute_status'],'validation_failed')

    def test_saved_replacement_rechecks_offer_eligibility(self):
        from scripts.listing.content_refresh_policy import replacement_artifact_error
        result = self.replacement()
        self.assertIsNone(replacement_artifact_error(result))
        result['amazon_result']=replace(self.amazon,available_qty=0)
        self.assertIn('価格・在庫',replacement_artifact_error(result))

    def test_reserved_replacement_cannot_be_content_refreshed(self):
        self.existing['replacement_reserved']=True
        with self.assertRaisesRegex(RuntimeError,'入れ替え依頼'):
            self.prepare()

    def mock_replacement(self, explicit=True, mutate=None):
        from scripts.listing.mock_execute_service import build_mock_execute_result
        dry = self.replacement()
        if mutate:
            mutate(dry)
        preflight = {'asin':self.asin,'management_number':dry['management_number'],
                     'preflight_status':'passed','ready_for_mock_execute':True}
        with patch('scripts.listing.listing_execute_service.time.sleep'):
            return build_mock_execute_result(dry,preflight,asin=self.asin,
                management_number=dry['management_number'],approved=True,asin_replacement=explicit)

    def test_replacement_mock_reproduces_missing_flag_and_passes_explicit_path(self):
        missing = self.mock_replacement(explicit=False)
        self.assertEqual(missing['final_status'],'validation_failed')
        self.assertIn('ASIN入れ替え専用の実行経路',str(missing['errors']))
        result = self.mock_replacement()
        self.assertEqual(result['final_status'],'completed',result.get('errors'))
        self.assertTrue(result['mock_only'])
        self.assertFalse(result['external_actions_performed'])
        self.assertTrue(result['raw_execute_result']['inventory_result']['skipped'])

    def test_replacement_mock_still_checks_identity_price_and_inventory(self):
        for changes in ({'page_asin':'B000OTHER1'},{'available_qty':0},{'gift_available':False},{'amazon_price':None}):
            with self.subTest(changes=changes):
                result = self.mock_replacement(mutate=lambda dry:dry.update(amazon_result=replace(self.amazon,**changes)))
                self.assertEqual(result['final_status'],'validation_failed')
