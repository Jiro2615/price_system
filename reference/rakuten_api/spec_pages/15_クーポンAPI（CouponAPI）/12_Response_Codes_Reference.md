RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/couponapi/couponapiresponsecodesreference
サービス: クーポンAPI（CouponAPI）

サービス一覧へ戻る / CouponAPI

RMS WEB SERVICE : CouponAPI Response Codes Reference
error list
No.	Code	Message	Description
1	COUPON_N000-000	success	正常終了
2	COUPON_W001-001	maintenance	メンテナンス中
3	COUPON_E999-999	unknown	システムエラー
4	COUPON_E017-001	shopId.required	店舗ID必須エラー
5	COUPON_E017-002	shopId.out_of_bounds	店舗ID範囲外エラー
6	COUPON_E017-003	shopId.forbidden	店舗ID不正エラー
7	COUPON_E018-001	shopName.out_of_bounds	店舗名範囲外エラー
8	COUPON_E018-002	shopName.required	店舗名必須エラー
9	COUPON_E019-001	shopUrl.out_of_bounds	店舗URL範囲外エラー
10	COUPON_E021-001	itemId.required	商品ID必須エラー
11	COUPON_E021-002	itemId.out_of_bounds	商品ID範囲外エラー
12	COUPON_E022-001	itemName.out_of_bounds	商品名範囲外エラー
13	COUPON_E022-002	itemName.required	商品名必須エラー
14	COUPON_E023-001	itemUrl.out_of_bounds	商品管理番号範囲外エラー
15	COUPON_E030-001	couponCode.required	クーポンコード必須エラー
16	COUPON_E030-002	couponCode.out_of_bounds	クーポンコード範囲外エラー
17	COUPON_E030-003	couponCode.over_term	クーポンコード有効期限外エラー
18	COUPON_E030-005	couponCode.absent	クーポンコードデータなしエラー
19	COUPON_E030-006	couponCode.forbidden	クーポンコード不正エラー
20	COUPON_E030-007	couponCode.max_out_count	クーポンコード発行上限エラー
21	COUPON_E033-001	couponStatus.required	クーポンステータス必須エラー
22	COUPON_E033-002	couponStatus.invalid_choice	クーポンステータス選択エラー
23	COUPON_E033-003	couponStatus.forbidden	クーポンステータス不正エラー
24	COUPON_E036-001	couponName.required	クーポン名必須エラー
25	COUPON_E036-002	couponName.out_of_bounds	クーポン名範囲外エラー
26	COUPON_E037-001	couponStartDate.required	クーポン有効期間（開始日）必須エラー
27	COUPON_E037-002	couponStartDate.forbidden	クーポン有効期間（開始日）不正エラー
28	COUPON_E038-001	couponEndDate.required	クーポン有効期間（終了日）必須エラー
29	COUPON_E038-002	couponEndDate.forbidden	クーポン有効期間（終了日）不正エラー
30	COUPON_E038-003	couponEndDate.over_term	クーポン有効期間（終了日）期限不正エラー
31	COUPON_E039-001	issueCount.required	クーポンの全利用回数上限必須エラー
32	COUPON_E039-002	issueCount.out_of_bounds	クーポンの全利用回数上限範囲外エラー
33	COUPON_E039-003	issueCount.forbidden	クーポンの全利用回数上限不正エラー
34	COUPON_E040-001	itemType.required	商品タイプ必須エラー
35	COUPON_E040-002	itemType.invalid_choice	商品タイプ選択エラー
36	COUPON_E040-003	itemType.forbidden	商品タイプ不正エラー
37	COUPON_E042-001	discountType.required	値引きプラン必須エラー
38	COUPON_E042-002	discountType.invalid_choice	値引きプラン選択エラー
39	COUPON_E042-003	discountType.forbidden	値引きプラン不正エラー
40	COUPON_E043-001	discountFactor.required	割引因子必須エラー
41	COUPON_E043-002	discountFactor.out_of_bounds	割引因子範囲外エラー
42	COUPON_E043-003	discountFactor.invalid_choice	割引因子選択エラー
43	COUPON_E048-001	memberAvailMaxCount.required	1ユーザあたりの利用回数上限必須エラー
44	COUPON_E048-002	memberAvailMaxCount.out_of_bounds	1ユーザあたりの利用回数上限範囲外エラー
45	COUPON_E048-003	memberAvailMaxCount.forbidden	1ユーザあたりの利用回数上限不正エラー
46	COUPON_E053-003	multiRankCond.invalid_choice	複数会員ランク条件選択エラー
47	COUPON_E053-004	multiRankCond.required	複数会員ランク条件必須エラー
48	COUPON_E056-001	couponCaption.out_of_bounds	クーポン説明文範囲外エラー
49	COUPON_E064-001	availCount.max_out_count	利用上限エラー
50	COUPON_E065-001	memberAvailMaxCount.max_out_count	会員上限エラー
51	COUPON_E081-001	combineFlag.combine_impossible	併用不可エラー
52	COUPON_E081-002	combineFlag.required	併用可否フラグ必須エラー
53	COUPON_E081-003	combineFlag.invalid_choice	併用可否フラグ選択エラー
54	COUPON_E082-001	page.required	ページ番号必須エラー
55	COUPON_E082-002	page.out_of_bounds	ページ番号範囲外エラー
56	COUPON_E082-003	page.invalid_format	ページ番号フォーマットエラー
57	COUPON_E083-001	hits.required	取得件数必須エラー
58	COUPON_E083-002	hits.out_of_bounds	取得件数範囲外エラー
59	COUPON_E083-003	hits.invalid_format	取得件数フォーマットエラー
60	COUPON_E084-001	displayFlag.required	公開設定フラグ必須エラー
61	COUPON_E084-002	displayFlag.invalid_choice	公開設定フラグ選択エラー
62	COUPON_E085-001	pcRedirectUrl.out_of_bounds	PCリダイレクトURL不正エラー
63	COUPON_E085-002	pcRedirectUrl.required	PCリダイレクトURL必須エラー
64	COUPON_E087-001	couponStatus.stop	クーポンステータス停止エラー
65	COUPON_E088-001	items.max_out_count	商品数上限エラー
66	COUPON_E089-001	startValue.required	開始値必須エラー
67	COUPON_E089-002	startValue.out_of_bounds	開始値範囲外エラー
68	COUPON_E090-001	conditionTypeCode.required	その他条件種別コード必須エラー
69	COUPON_E090-002	conditionTypeCode.absent	その他条件種別コードデータなしエラー
70	COUPON_E090-003	conditionTypeCode.out_of_bounds	その他条件種別コード範囲外エラー
71	COUPON E110-001	otherConditions.out_of_bounds	その他条件範囲外エラー
72	COUPON E110-002	otherConditions.max_out_count	その他条件上限エラー
73	COUPON E113-001	shopImage.out_of_bounds	店舗画像範囲外エラー
74	COUPON_E119-001	items.out_of_bounds	商品数範囲外エラー
error list (validation)
coupon.issue
No.	Code	Message	Description
1	COUPON_EE01-001	couponName.limit_over	入力された文字数が制限を越えています。
2	COUPON_EE01-002	couponName.invalid_value	入力された文字種が不正です。
3	COUPON_EE01-003	couponName.invalid_url	入力されたURLが不正です。
4	COUPON_EE02-001	couponCaption.limit_over	入力された文字数が制限を越えています。
5	COUPON_EE02-002	couponCaption.invalid_value	入力された文字種が不正です。
6	COUPON_EE02-003	couponCaption.invalid_url	入力されたURLが不正です。（楽天市場で許可されていないドメインが入力された場合）
7	COUPON_EE03-001	discountType.invalid_value	数値項目に半角整数以外の文字が入力されています。
8	COUPON_EE03-002	discountType.out_of_bounds	入力された数値は指定できません。
9	COUPON_EE04-001	discountFactor.invalid_value	数値項目に半角整数以外の文字が入力されています。
10	COUPON_EE04-002	discountFactor.limit_over	入力された文字数が制限を越えています。
11	COUPON_EE04-003	discountFactor.out_of_bounds	入力された数値は指定できません。
12	COUPON_EE05-001	itemType.invalid_value	数値項目に半角整数以外の文字が入力されています。
13	COUPON_EE05-002	itemType.out_of_bounds	入力された数値は指定できません。
14	COUPON_EE06-001	couponStartDate.over_term	現在日時の最短60分後から最長30日後の範囲で設定してください。
15	COUPON_EE07-001	couponEndDate.over_term	クーポン有効期間の「終了日時」は「開始日時」より5分以降を指定してください。
16	COUPON_EE08-001	couponImage.invalid_url	入力されたURLが不正です。
17	COUPON_EE08-002	couponImage.not_available_url	入力されたURLが不正です。
18	COUPON_EE09-001	memberAvailMaxCount.invalid_value	数値項目に半角整数以外の文字が入力されています。
19	COUPON_EE09-002	memberAvailMaxCount.limit_over	入力された文字数が制限を越えています。
20	COUPON_EE10-001	startValue.invalid_value	数値項目に半角整数以外の文字が入力されています。
21	COUPON_EE10-003	startValue.limit_over	入力された文字数が制限を越えています。
22	COUPON_EE11-001	displayFlag.invalid_value	数値項目に半角整数以外の文字が入力されています。
23	COUPON_EE12-003	multiRankCond.set_only_zero_or_only_otherValues	会員ランク「0：条件なし」とそれ以外の会員ランクは同時に設定できません。
24	COUPON_EE12-004	multiRankCond.invalid_value	数値項目に半角整数以外の文字が入力されています。
25	COUPON_EE12-005	multiRankCond.illegal_condition	会員ランク条件を指定した場合、他の条件は指定できません。
26	COUPON_EE13-001	RS003_RS004.set_only_one	金額条件、個数条件はいずれか1つしか設定できません。
27	COUPON_EE13-003	itemType3_RS004_notAllowed_forNon39shop	39ショップ以外の場合、個数条件を設定した場合には複数商品を指定できません。
28	COUPON_EE15-001	itemUrl.absent : xxxxx(itemUrl)	指定された商品は存在しないか、通常販売可能な商品ではありません。
商品管理番号を再度ご確認ください。
29	COUPON_EE15-002	itemUrl.not_normal : xxxxx(itemUrl)	商品指定クーポンの場合は、通常商品以外の商品を設定することはできません。
30	COUPON_EE15-004	itemUrl.duplicate : xxxxx(itemUrl)	重複した商品を設定することはできません。
31	COUPON_EE15-005	itemUrl.over_discount : xxxxx(itemUrl)	値引き額より小さい価格の商品を設定することはできません。

※SKU移行済み店舗様の場合、チェック内容が以下に変更となります。
1.商品が楽天サーチ検索対象外の場合
　すべてのSKUの中の最低価格と値引き額を比較
2.一部SKUが楽天サーチ検索対象外の場合
　楽天サーチ検索対象であるSKU内の最低価格と値引き額を比較
32	COUPON_EE15-007	itemUrl.no_cart_button : xxxxx(itemUrl)	商品指定クーポンの場合は、注文ボタン非表示の商品を設定することはできません。
33	COUPON_EE15-008	itemUrl.not_subscription_item : xxxxx(itemUrl) 	定期購入のみ指定可能のクーポンの場合は、定期設定のない通常商品を設定することはできません。
34	COUPON_EE16-001	items.not_specified	送料無料の場合は、商品を指定できません。
35	COUPON_EE18-001	issueCount.invalid_value	数値項目に半角整数以外の文字が入力されています。
36	COUPON_EE18-002	issueCount.limit_over	入力された文字数が制限を越えています。
37	COUPON_EE19-002	combineFlag.invalid_value	入力された文字種が不正です。
38	COUPON_EE19-003	combineFlag.out_of_bounds	入力された数値は指定できません。
39	COUPON_EE21-001	otherConditions.invalid_value : xxxxx(conditionTypeCode)	入力された値が制限を越えています。
40	COUPON_EE22-001	endDate_issueCount_multiRankCond.specify_any_one	「商品を指定する」を選択した場合、クーポン有効期間を14日以内の範囲で設定する、またはクーポンの全利用回数上限を1000回以下に指定する、または会員ランクを指定して下さい。
41	COUPON_EE23-003	type.invalid_value	入力された値が不正です。
42	COUPON_EE23-005	dynamicPeriod.invalid_value	入力された値が不正です。
43	COUPON_EE23-008	minimum.invalid_value	入力された値が不正です。
44	COUPON_EE23-010	maximum.invalid_value	入力された値が不正です。
45	COUPON_EE23-011	maximum.below_minimum	購入回数の下限値に購入回数の上限値より大きい値を指定できません。
46	COUPON_EE24-002	genderCond.invalid_value	入力された値が不正です。
47	COUPON_EE24-004	genderCond.invalid_subscription_only	定期購入のみ指定可能のクーポンの場合は、性別条件を設定することはできません。
48	COUPON_EE25-002	ageRangeCond.invalid_value	入力された値が不正です。
49	COUPON_EE25-004	lowerBound.invalid_value	入力された値が不正です。
50	COUPON_EE25-006	upperBound.invalid_value	入力された値が不正です。
51	COUPON_EE25-007	upperBound.below_lowerBound	年齢の下限値に年齢の上限値よりも大きい値を指定できません。
52	COUPON_EE25-009	lowerBound.invalid_subscription_only	定期購入のみ指定可能のクーポンの場合は、年齢条件を設定することはできません。
53	COUPON_EE26-002	birthmonthCond.invalid_value	入力された値が不正です。
54	COUPON_EE26-003	birthmonthCond.invalid_subscription_only	定期購入のみ指定可能のクーポンの場合は、誕生月条件を設定することはできません。
55	COUPON_EE27-003	prefectureCond.invalid_value	入力された値が不正です。
56	COUPON_EE27-004	prefectureCond.too_many	居住地条件に48件以上の要素は指定できません。
coupon.update
No.	Code	Message	Description
1	COUPON_EE00-001	couponUpdate.over_term	このクーポンは有効期間を過ぎているため編集できません。
2	COUPON_EE01-001	couponName.limit_over	入力された文字数が制限を越えています。
3	COUPON_EE01-002	couponName.invalid_value	入力された文字種が不正です。
4	COUPON_EE01-003	couponName.invalid_url	入力されたURLが不正です。
5	COUPON_EE02-001	couponCaption.limit_over	入力された文字数が制限を越えています。
6	COUPON_EE02-002	couponCaption.invalid_value	入力された文字種が不正です。
7	COUPON_EE02-003	couponCaption.invalid_url	入力されたURLが不正です。（楽天市場で許可されていないドメインが入力された場合）
8	COUPON_EE03-001	discountType.invalid_value	数値項目に半角整数以外の文字が入力されています。
9	COUPON_EE03-002	discountType.out_of_bounds	入力された数値は指定できません。
10	COUPON_EE04-001	discountFactor.invalid_value	数値項目に半角整数以外の文字が入力されています。
11	COUPON_EE04-002	discountFactor.limit_over	入力された文字数が制限を越えています。
12	COUPON_EE04-003	discountFactor.out_of_bounds	入力された数値は指定できません。
13	COUPON_EE05-001	itemType.invalid_value	数値項目に半角整数以外の文字が入力されています。
14	COUPON_EE05-002	itemType.out_of_bounds	入力された数値が制限を越えています。
15	COUPON_EE06-001	couponStartDate.over_term	現在日時の最短60分後から最長30日後の範囲で設定してください。
16	COUPON_EE07-001	couponEndDate.over_term	クーポン有効期間の「終了日時」は「開始日時」より5分以降を指定してください。
17	COUPON_EE08-001	couponImage.invalid_url	入力されたURLが不正です。
18	COUPON_EE08-002	couponImage.not_available_url	入力されたURLが不正です。
19	COUPON_EE09-001	memberAvailMaxCount.invalid_value	数値項目に半角整数以外の文字が入力されています。
20	COUPON_EE09-002	memberAvailMaxCount.limit_over	入力された文字数が制限を越えています。
21	COUPON_EE10-001	startValue.invalid_value	数値項目に半角整数以外の文字が入力されています。
22	COUPON_EE10-003	startValue.limit_over	入力された文字数が制限を越えています。
23	COUPON_EE11-001	displayFlag.invalid_value	数値項目に半角整数以外の文字が入力されています。
24	COUPON_EE12-003	multiRankCond.set_only_zero_or_only_otherValues	会員ランク「0：条件なし」とそれ以外の会員ランクは同時に設定できません。
25	COUPON_EE12-004	multiRankCond.invalid_value	数値項目に半角整数以外の文字が入力されています。
26	COUPON_EE12-005	multiRankCond.illegal_condition	会員ランク条件を指定した場合、他の条件は指定できません。
27	COUPON_EE13-001	RS003_RS004.set_only_one	金額条件、個数条件はいずれか1つしか設定できません。
28	COUPON_EE13-003	itemType3_RS004_notAllowed_forNon39shop	39ショップ以外の場合、個数条件を設定した場合には複数商品を指定できません。
29	COUPON_EE15-001	itemUrl.absent : xxxxx(itemUrl)	指定された商品は存在しないか、通常販売可能な商品ではありません。
商品管理番号を再度ご確認ください。
30	COUPON_EE15-002	itemUrl.not_normal : xxxxx(itemUrl)	商品指定クーポンの場合は、通常商品以外の商品を設定することはできません。
31	COUPON_EE15-004	itemUrl.duplicate : xxxxx(itemUrl)	重複した商品を設定することはできません。
32	COUPON_EE15-005	itemUrl.over_discount : xxxxx(itemUrl)	値引き額より小さい価格の商品を設定することはできません。

※SKU移行済み店舗様の場合、チェック内容が以下に変更となります。
1.商品が楽天サーチ検索対象外の場合
　すべてのSKUの中の最低価格と値引き額を比較
2.一部SKUが楽天サーチ検索対象外の場合
　楽天サーチ検索対象であるSKU内の最低価格と値引き額を比較
33	COUPON_EE15-007	itemUrl.no_cart_button : xxxxx(itemUrl)	商品指定クーポンの場合は、注文ボタン非表示の商品を設定することはできません。
34	COUPON_EE15-008	itemUrl.not_subscription_item : xxxxx(itemUrl) 	定期購入のみ指定可能のクーポンの場合は、定期設定のない通常商品を設定することはできません。
35	COUPON_EE16-001	items.not_specified	送料無料の場合は、商品を指定できません。
36	COUPON_EE18-001	issueCount.invalid_value	数値項目に半角整数以外の文字が入力されています。
37	COUPON_EE18-002	issueCount.limit_over	入力された文字数が制限を越えています。
38	COUPON_EE19-002	combineFlag.invalid_value	入力された文字種が不正です。
39	COUPON_EE19-003	combineFlag.out_of_bounds	入力された数値は指定できません。
40	COUPON_EE21-001	otherConditions.invalid_value : xxxxx(conditionTypeCode)	入力された値が制限を越えています。
41	COUPON_EE22-001	endDate_issueCount_multiRankCond.specify_any_one	「商品を指定する」を選択した場合、クーポン有効期間を14日以内の範囲で設定する、またはクーポンの全利用回数上限を1000回以下に指定する、または会員ランクを指定して下さい。
42	COUPON_EE23-003	type.invalid_value	入力された値が不正です。
43	COUPON_EE23-005	dynamicPeriod.invalid_value	入力された値が不正です。
44	COUPON_EE23-008	minimum.invalid_value	入力された値が不正です。
45	COUPON_EE23-010	maximum.invalid_value	入力された値が不正です。
46	COUPON_EE23-011	maximum.below_minimum	購入回数の下限値に購入回数の上限値より大きい値を指定できません。
47	COUPON_EE23-012	purchaseHistoryCond.too_many_entries	購入履歴条件に関するデータ不整合エラー
48	COUPON_EE23-013	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
49	COUPON_EE23-014	purchaseHistoryCond.too_many_entries	購入履歴条件に関するデータ不整合エラー
50	COUPON_EE23-015	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
51	COUPON_EE23-017	dynamicPeriod.invalid_value	購入履歴条件に関するデータ不整合エラー
52	COUPON_EE23-018	dynamicPeriod.invalid_value	購入履歴条件に関するデータ不整合エラー
53	COUPON_EE24-002	genderCond.invalid_value	入力された値が不正です。
54	COUPON_EE24-003	genderCond.too_many_entries	性別条件に関するデータ不整合エラー
55	COUPON_EE24-004	genderCond.invalid_subscription_only	定期購入のみ指定可能のクーポンの場合は、性別条件を設定することはできません。
56	COUPON_EE25-002	ageRangeCond.invalid_value	入力された値が不正です。
57	COUPON_EE25-004	lowerBound.invalid_value	入力された値が不正です。
58	COUPON_EE25-006	upperBound.invalid_value	入力された値が不正です。
59	COUPON_EE25-007	upperBound.below_lowerBound	年齢の下限値に年齢の上限値よりも大きい値を指定できません。
60	COUPON_EE25-008	ageRangeCond.too_many_entries	年齢条件に関するデータ不整合エラー
61	COUPON_EE25-009	lowerBound.invalid_subscription_only	定期購入のみ指定可能のクーポンの場合は、年齢条件を設定することはできません。
62	COUPON_EE26-002	birthmonthCond.invalid_value	入力された値が不正です。
63	COUPON_EE26-003	birthmonthCond.invalid_subscription_only	定期購入のみ指定可能のクーポンの場合は、誕生月条件を設定することはできません。
64	COUPON_EE27-003	prefectureCond.invalid_value	入力された値が不正です。
65	COUPON_EE27-004	prefectureCond.too_many	居住地条件に48件以上の要素は指定できません。
coupon.delete
No.	Code	Message	Description
1	COUPON_EE00-002	couponDelete.over_term	このクーポンは有効期間を過ぎているため編集できません。
2	COUPON_EE23-008	minimum.invalid_value	購入履歴条件に関するデータ不整合エラー
3	COUPON_EE23-010	maximum.invalid_value	購入履歴条件に関するデータ不整合エラー
4	COUPON_EE23-012	purchaseHistoryCond.too_many_entries	購入履歴条件に関するデータ不整合エラー
5	COUPON_EE23-013	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
6	COUPON_EE23-015	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
7	COUPON_EE23-016	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
8	COUPON_EE23-017	dynamicPeriod.invalid_value	購入履歴条件に関するデータ不整合エラー
9	COUPON_EE23-018	dynamicPeriod.invalid_value	購入履歴条件に関するデータ不整合エラー
10	COUPON_EE12-005	multiRankCond.illegal_condition	ランク条件に関するデータ不整合エラー
11	COUPON_EE24-002	genderCond.invalid_value	性別条件に関するデータ不整合エラー
12	COUPON_EE24-003	genderCond.too_many_entries	性別条件に関するデータ不整合エラー
13	COUPON_EE25-008	ageRangeCond.too_many_entries	年齢条件に関するデータ不整合エラー
14	COUPON_EE25-004	lowerBound.invalid_value	年齢条件に関するデータ不整合エラー
15	COUPON_EE25-006	upperBound.invalid_value	年齢条件に関するデータ不整合エラー
16	COUPON_EE26-002	birthmonthCond.invalid_value	誕生月条件に関するデータ不整合エラー
coupon.get
No.	Code	Message	Description
1	COUPON_EE23-008	minimum.invalid_value	購入履歴条件に関するデータ不整合エラー
2	COUPON_EE23-010	maximum.invalid_value	購入履歴条件に関するデータ不整合エラー
3	COUPON_EE23-012	purchaseHistoryCond.too_many_entries	購入履歴条件に関するデータ不整合エラー
4	COUPON_EE23-013	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
5	COUPON_EE23-014	purchaseHistoryCond.too_many_entries	購入履歴条件に関するデータ不整合エラー
6	COUPON_EE23-015	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
7	COUPON_EE23-016	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
8	COUPON_EE23-017	dynamicPeriod.invalid_value	購入履歴条件に関するデータ不整合エラー
9	COUPON_EE23-018	dynamicPeriod.invalid_value	購入履歴条件に関するデータ不整合エラー
10	COUPON_EE12-005	multiRankCond.illegal_condition	ランク条件に関するデータ不整合エラー
11	COUPON_EE24-002	genderCond.invalid_value	性別条件に関するデータ不整合エラー
12	COUPON_EE24-003	genderCond.too_many_entries	性別条件に関するデータ不整合エラー
13	COUPON_EE25-008	ageRangeCond.too_many_entries	年齢条件に関するデータ不整合エラー
14	COUPON_EE25-004	lowerBound.invalid_value	年齢条件に関するデータ不整合エラー
15	COUPON_EE25-006	upperBound.invalid_value	年齢条件に関するデータ不整合エラー
16	COUPON_EE26-002	birthmonthCond.invalid_value	誕生月条件に関するデータ不整合エラー
coupon.search
No.	Code	Message	Description
1	COUPON_EP01-002	couponStartDate.invalid_value	クーポン有効期間　開始日時パラメータ不正エラー
2	COUPON_EP02-002	couponEndDate.invalid_value	クーポン有効期間　終了日時パラメータ不正エラー
3	COUPON_EP03-002	hits.invalid_value	件数パラメータ不正エラー
4	COUPON_EP04-002	page.invalid_value	ページ番号パラメータ不正エラー
coupon.patch
No.	Code	Message	Description
1	COUPON_ER00-000	requestData.invalid_format	リクエストのHTTP Bodyに入力されたデータが不正なフォーマットです。
2	COUPON_EE00-003	couponUpdate.not_started	このクーポンは適用期間前（開始前60分含む）のクーポンのため情報の編集はできません。
代わりに、coupon.update をご利用ください。
3	COUPON_EE00-004	couponUpdate.over_term	このクーポンは有効期間を過ぎているため編集できません。
4	COUPON_EE11-001	displayFlag.invalid_value	数値項目に半角整数以外の文字が入力されています。
5	COUPON_EE23-008	minimum.invalid_value	購入履歴条件に関するデータ不整合エラー
6	COUPON_EE23-010	maximum.invalid_value	購入履歴条件に関するデータ不整合エラー
7	COUPON_EE23-012	purchaseHistoryCond.too_many_entries	購入履歴条件に関するデータ不整合エラー
8	COUPON_EE23-013	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
9	COUPON_EE23-015	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
10	COUPON_EE23-016	purchaseHistoryCond.invalid_value	購入履歴条件に関するデータ不整合エラー
11	COUPON_EE23-017	dynamicPeriod.invalid_value	購入履歴条件に関するデータ不整合エラー
12	COUPON_EE23-018	dynamicPeriod.invalid_value	購入履歴条件に関するデータ不整合エラー
13	COUPON_EE12-005	multiRankCond.illegal_condition	ランク条件に関するデータ不整合エラー
14	COUPON_EE24-002	genderCond.invalid_value	性別条件に関するデータ不整合エラー
15	COUPON_EE24-003	genderCond.too_many_entries	性別条件に関するデータ不整合エラー
16	COUPON_EE25-008	ageRangeCond.too_many_entries	年齢条件に関するデータ不整合エラー
17	COUPON_EE25-004	lowerBound.invalid_value	年齢条件に関するデータ不整合エラー
18	COUPON_EE25-006	upperBound.invalid_value	年齢条件に関するデータ不整合エラー
19	COUPON_EE26-002	birthmonthCond.invalid_value	誕生月条件に関するデータ不整合エラー
