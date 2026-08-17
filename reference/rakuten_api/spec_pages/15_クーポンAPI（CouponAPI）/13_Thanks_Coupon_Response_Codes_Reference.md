RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/couponapi/thankscouponresponsecodesreference
サービス: クーポンAPI（CouponAPI）

サービス一覧へ戻る / CouponAPI

RMS WEB SERVICE : Thanks Coupon Response Codes Reference
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
10	COUPON_E030-003	One ore more thanksCoupon do not exist.	クーポン存在エラー
11	COUPON_E032-005	thanks coupon grant end date is earlier than thanks coupon grant start date.	クーポン獲得期間の終了日時エラー
12	COUPON_E036-001	couponName.required	クーポン名必須エラー
13	COUPON_E036-002	couponName.out_of_bounds	クーポン名範囲外エラー
14	COUPON_E040-011	Reg date invalid.	クーポン登録日時エラー
15	COUPON_E042-001	discountType.required	値引きプラン必須エラー
16	COUPON_E042-002	discountType.invalid_choice	値引きプラン選択エラー
17	COUPON_E042-003	discountType.forbidden	値引きプラン不正エラー
18	COUPON_E043-001	discountFactor.required	割引因子必須エラー
19	COUPON_E043-002	discountFactor.out_of_bounds	割引因子範囲外エラー
20	COUPON_E043-003	discountFactor.invalid_choice	割引因子選択エラー
21	COUPON_E048-001	memberAvailMaxCount.required	1ユーザあたりの利用回数上限必須エラー
22	COUPON_E048-002	memberAvailMaxCount.out_of_bounds	1ユーザあたりの利用回数上限範囲外エラー
23	COUPON_E048-003	memberAvailMaxCount.forbidden	1ユーザあたりの利用回数上限不正エラー
24	COUPON_E056-001	couponCaption.out_of_bounds	クーポン詳細説明範囲外エラー
25	COUPON_E065-001	memberAvailMaxCount.max_out_count	会員上限エラー
26	COUPON_E081-001	combineFlag.combine_impossible	併用不可エラー
27	COUPON_E081-002	combineFlag.required	併用可否フラグ必須エラー
28	COUPON_E081-003	combineFlag.invalid_choice	併用可否フラグ選択エラー
29	COUPON_E082-001	page.required	ページ番号必須エラー
30	COUPON_E082-002	page.out_of_bounds	ページ番号範囲外エラー
31	COUPON_E082-003	page.invalid_format	ページ番号フォーマットエラー
32	COUPON_E083-001	hits.required	取得件数必須エラー
33	COUPON_E083-002	hits.out_of_bounds	取得件数範囲外エラー
34	COUPON_E083-003	hits.invalid_format	取得件数フォーマットエラー
35	COUPON_E085-001	pcRedirectUrl.out_of_bounds	PCリダイレクトURL不正エラー
36	COUPON_E085-002	pcRedirectUrl.required	PCリダイレクトURL必須エラー
37	COUPON_E089-001	startValue.required	開始値必須エラー
38	COUPON_E089-002	startValue.out_of_bounds	開始値範囲外エラー
39	COUPON_E090-001	conditionTypeCode.required	その他条件種別コード必須エラー
40	COUPON_E090-002	conditionTypeCode.absent	その他条件種別コードデータなしエラー
41	COUPON_E090-003	conditionTypeCode.out_of_bounds	その他条件種別コード範囲外エラー
42	COUPON E110-001	otherConditions.out_of_bounds	その他条件範囲外エラー
43	COUPON E110-002	otherConditions.max_out_count	その他条件上限エラー
44	COUPON E113-001	shopImage.out_of_bounds	店舗画像範囲外エラー
45	COUPON_E137-001	issueStatus.required	獲得ステータス必須エラー
46	COUPON_E137-002	issueStatus.out_of_bounds	獲得ステータス（範囲外）不正エラー
47	COUPON_E137-003	issueStatus.forbidden	獲得ステータス不正エラー
48	COUPON_E138_001	grantDate.invalid_value	付与開始日・付与終了日不正エラー
49	COUPON_E139_002	baseCoupon.max_out_count	発行元クーポン発行上限エラー
50	COUPON_E140-001	couponUnavailableTerm.required	クーポン有効期間開始前期間必須エラー
51	COUPON_E140-002	couponUnavailableTerm.out_of_bounds	クーポン有効期間開始前期間不正エラー
52	COUPON_E142-001	couponTerm.required	クーポン有効期間必須エラー
53	COUPON_E142-002	couponTerm.out_of_bounds	クーポン有効期間の指定が不正な場合
54	COUPON_E145-001	getCondCd.required	獲得条件コード必須エラー
55	COUPON_E145-002	getCondCd.invalid_choice	獲得条件コード選択エラー
error list (validation)
thanksCoupon.issue
No.	Code	Message	Description
1	COUPON_ER00-000	requestData.invalid_format	入力されたフォーマットが不正です。
2	COUPON_EE01-001	couponName.limit_over	入力された文字数が制限を越えています。
3	COUPON_EE01-002	couponName.invalid_value	入力された文字種が不正です。
4	COUPON_EE01-003	couponName.invalid_url	入力されたURLが不正です。
5	COUPON_EE01-004	couponName.required	必須項目が未設定です。
6	COUPON_EE02-001	couponCaption.limit_over	入力された文字数が制限を越えています。
7	COUPON_EE02-002	couponCaption.invalid_value	入力された文字種が不正です。
8	COUPON_EE03-001	discountType.invalid_value	数値項目に半角整数以外の文字が入力されています。
9	COUPON_EE03-002	discountType.out_of_bounds	入力された数値は指定できません。
10	COUPON_EE03-003	discountType.required	必須項目が未設定です。
11	COUPON_EE04-001	discountFactor.invalid_value	数値項目に半角整数以外の文字が入力されています。
12	COUPON_EE04-002	discountFactor.limit_over	入力された文字数が制限を越えています。
13	COUPON_EE04-003	discountFactor.out_of_bounds	入力された数値は指定できません。
14	COUPON_EE04-004	discountFactor.required	必須項目が未設定です。
15	COUPON_EE08-001	couponImage.invalid_url	入力されたURLが不正です。
16	COUPON_EE08-002	couponImage.not_available_url	入力されたURLが不正です。
17	COUPON_EE09-001	memberAvailMaxCount.invalid_value	数値項目に半角整数以外の文字が入力されています。
18	COUPON_EE09-002	memberAvailMaxCount.limit_over	入力された文字数が制限を越えています。
19	COUPON_EE09-003	memberAvailMaxCount.required	必須項目が未設定です。
20	COUPON_EE10-001	startValue.invalid_value	数値項目に半角整数以外の文字が入力されています。
21	COUPON_EE10-002	startValue.out_of_bounds	入力された数値は指定できません。
22	COUPON_EE10-003	startValue.limit_over	入力された文字数が制限を越えています。
23	COUPON_EE19-001	combineFlag.required	必須項目が未設定です。
24	COUPON_EE19-002	combineFlag.invalid_value	入力された文字種が不正です。
25	COUPON_EE19-003	combineFlag.out_of_bounds	入力された数値は指定できません。
26	COUPON_EE101_001	thankOtherConditions.invalid_value	入力された値は指定できないか、未設定です。
27	COUPON_EE101_002	thanksOtherConditions.duplicate	クーポンその他条件リストの入力が重複しています。
28	COUPON_EE102_001	couponUnavailableTerm.invalid_value	数値項目に半角整数以外の文字が入力されています。
29	COUPON_EE102_003	couponUnavailableTerm.out_of_bounds	入力された数値は指定できません。
30	COUPON_EE102_004	couponUnavailableTerm.required	必須項目が未設定です。
31	COUPON_EE103_001	couponTerm.invalid_value	数値項目に半角整数以外の文字が入力されています。
32	COUPON_EE103_002	couponTerm.out_of_bounds	入力された数値は指定できません。
33	COUPON_EE103_003	couponTerm.required	必須項目が未設定です。
34	COUPON_EE104_001	autoGetConditions.invalid_value	入力された値は指定できません。
35	COUPON_EE104_002	autoGetCondUseHistory_StartValue_EndValue.duplicate_value	「獲得対象ユーザ」の設定が同一の場合、獲得期間が重複したクーポンは登録できません。
36	COUPON_EE104_003	autoGetCondUseHistory_MemberAvailMax.invalid_value	獲得対象ユーザが「初回購入ユーザのみ」の場合、1ユーザあたりの利用回数上限を1回として設定してください。
37	COUPON_EE104-004	autoGetConditions.required	必須項目が未設定です。
38	COUPON_EE104_005	autoGetConditions.duplicate	サンキュークーポン獲得条件の入力が重複しています。
39	COUPON_EE105_001	autoGetCondStartValue.invalid_value	日付フォーマットが不正です。
40	COUPON_EE105_002	autoGetCondStartValue.limit_over	入力された文字数が制限を越えています。
41	COUPON_EE105_003	autoGetCondStartValue.out_of_bounds	入力された数値は指定できません。
42	COUPON_EE105_004	autoGetCondStartValue.invalid_term	「開始日時」は、現在日付の最短2日後から最長6ヶ月の範囲で設定してください。
43	COUPON_EE105_005	autoGetCondStartValue.required	必須項目が未設定です。
44	COUPON_EE106_001	autoGetCondEndValue.invalid_values	数値項目に半角整数以外の文字が入力されています。
45	COUPON_EE106_002	autoGetCondEndValue.out_of_bounds	入力された数値は指定できません。
46	COUPON_EE106_003	autoGetCondEndValue.invalid_term	「終了日時」は「開始日時」より5分後以降、「開始日時」と「終了日時」の期間は、最長36ヶ月以内を設定してください。
47	COUPON_EE106_004	autoGetCondEndValue.required	必須項目が未設定です。
48	COUPON_EE113_001	compOperatorCd.invalid_value	数値項目に半角整数以外の文字が入力されています。
49	COUPON_EE113_002	compOperatorCd.out_of_bounds	入力された数値は指定できません。
50	COUPON_EE113_003	compOperatorCd.required	必須項目が未設定です。
thanksCoupon.update
No.	Code	Message	Description
1	COUPON_ER00-000	requestData.invalid_format	入力されたフォーマットが不正です。
2	COUPON_EE01-001	couponName.limit_over	入力された文字数が制限を越えています。
3	COUPON_EE01-002	couponName.invalid_value	入力された文字種が不正です。
4	COUPON_EE01-003	couponName.invalid_url	入力されたURLが不正です。
5	COUPON_EE01-004	couponName.required	必須項目が未設定です。
6	COUPON_EE02-001	couponCaption.limit_over	入力された文字数が制限を越えています。
7	COUPON_EE02-002	couponCaption.invalid_value	入力された文字種が不正です。
8	COUPON_EE03-001	discountType.invalid_value	数値項目に半角整数以外の文字が入力されています。
9	COUPON_EE03-002	discountType.out_of_bounds	入力された数値は指定できません。
10	COUPON_EE03-003	discountType.required	必須項目が未設定です。
11	COUPON_EE04-001	discountFactor.invalid_value	数値項目に半角整数以外の文字が入力されています。
12	COUPON_EE04-002	discountFactor.limit_over	入力された文字数が制限を越えています。
13	COUPON_EE04-003	discountFactor.out_of_bounds	入力された数値は指定できません。
14	COUPON_EE04-004	discountFactor.required	必須項目が未設定です。
15	COUPON_EE09-001	memberAvailMaxCount.invalid_value 	数値項目に半角整数以外の文字が入力されています。
16	COUPON_EE09-002	memberAvailMaxCount.limit_over 	入力された文字数が制限を越えています。
17	COUPON_EE09-003	memberAvailMaxCount.required	必須項目が未設定です。
18	COUPON_EE10-001	startValue.invalid_value 	数値項目に半角整数以外の文字が入力されています。
19	COUPON_EE10-002	startValue.out_of_bounds 	入力された数値は指定できません。
20	COUPON_EE10-003	startValue.limit_over 	入力された文字数が制限を越えています。
21	COUPON_EE19-001	combineFlag.required	必須項目が未設定です。
22	COUPON_EE19-002	combineFlag.invalid_value	入力された文字種が不正です。
23	COUPON_EE19-003	combineFlag.out_of_bounds	入力された数値は指定できません
24	COUPON_EE100-001	couponUpdate.over_term	このクーポンは現在獲得期間中（開始前1日含む）、停止済み、または獲得期間を過ぎているため情報の編集はできません。
25	COUPON_EE101_001	thankOtherConditions.invalid_value	入力された値は指定できないか、未設定です。
26	COUPON_EE102_001	couponUnavailableTerm.invalid_value	数値項目に半角整数以外の文字が入力されています。
27	COUPON_EE102_003	couponUnavailableTerm.out_of_bounds	入力された数値は指定できません。
28	COUPON_EE102_004	couponUnavailableTerm.required	必須項目が未設定です。
29	COUPON_EE103_001	couponTerm.invalid_value	数値項目に半角整数以外の文字が入力されています。
30	COUPON_EE103_002	couponTerm.out_of_bounds	入力された数値は指定できません。
31	COUPON_EE103_003	couponTerm.required 	必須項目が未設定です。
32	COUPON_EE104_001	autoGetConditions.invalid_value	入力された値は指定できません。
33	COUPON_EE104_002	autoGetCondUseHistory_StartValue_EndValue.duplicate_value	「獲得対象ユーザ」の設定が同一の場合、獲得期間が重複したクーポンは登録できません。
34	COUPON_EE104_003	autoGetCondUseHistory_MemberAvailMax.invalid_value	獲得対象ユーザが「初回購入ユーザのみ」の場合、1ユーザあたりの利用回数条件を1回として設定してください。
35	COUPON_EE104_004	autoGetConditions.required	必須項目が未設定です。
36	COUPON_EE105_001	autoGetCondStartValue.invalid_value	日付フォーマットが不正です。
37	COUPON_EE105_002	autoGetCondStartValue.limit_over	入力された文字数が制限を越えています。
38	COUPON_EE105_003	autoGetCondStartValue.out_of_bounds	入力された数値は指定できません。
39	COUPON_EE105_004	autoGetCondStartValue.invalid_term	「開始日時」は、現在日付の最短2日後から最長6ヶ月の範囲で設定してください。
40	COUPON_EE105_005	autoGetCondStartValue.required	必須項目が未設定です。
41	COUPON_EE106_001	autoGetCondEndValue.invalid_value	日付フォーマットが不正です。
42	COUPON_EE106_002	autoGetCondEndValue.out_of_bounds	入力された数値は指定できません。
43	COUPON_EE106_003	autoGetCondEndValue.invalid_term	 「終了日時」は「開始日時」より5分後以降、「開始日時」と「終了日時」の期間は、最長36ヶ月以内を設定してください。
44	COUPON_EE106_004	autoGetCondEndValue.required	必須項目が未設定です。
45	COUPON_EE104_005	autoGetConditions.duplicate	サンキュークーポン獲得条件の入力が重複しています。
46	COUPON_EE107_001	thanksCouponId.required	必須項目が未設定です。
47	COUPON_EE107_002	thanksCouponId.out_of_bounds	入力された値は不正です。
48	COUPON_EE107_003	thanksCouponId.invalid_value	サンキュークーポンIDの値が不正です。
49	COUPON_EE107_004	thanksCouponId.forbidden	入力された値は不正です。
50	COUPON_EE113_001	compOperatorCd.invalid_value	数値項目に半角整数以外の文字が入力されています。
51	COUPON_EE113_002	compOperatorCd.out_of_bounds	入力された数値は指定できません。
52	COUPON_EE113_003	compOperatorCd.required	必須項目が未設定です
thanksCoupon.stop
No.	Code	Message	Description
1	COUPON_EE100-002	thanksCouponStop.over_term	このクーポンは現在獲得期間中（開始前1日含む）、停止済み、または獲得期間を過ぎているため情報の編集はできません。
2	COUPON_EE107_003	thanksCouponId.invalid_value	サンキュークーポンIDの値が不正です。
thanksCoupon.search
No.	Code	Message	Description
1	COUPON_EE108-001	grantStartDate.invalid_value	日付フォーマットが不正です。
2	COUPON_EE109_001	grantEndDate.invalid_value	日付フォーマットが不正です。
3	COUPON_EE110_001	hits.invalid_value	数値項目に半角整数以外の文字が入力されています。
4	COUPON_EE110_002	hits.out_of_bounds	入力された数値は指定できません。
5	COUPON_EE111_001	page.invalid_value	数値項目に半角整数以外の文字が入力されています。
6	COUPON_EE111_002	page.out_of_bound	入力された数値は指定できません。
7	COUPON_EE112_001	issueStatus.invalid_value	数値項目に半角整数以外の文字が入力されています。
8	COUPON_EE112_002	issueStatus.out_of_bounds	入力された数値は指定できません。
