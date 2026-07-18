RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itemapi2_0/itemssearch/
サービス: 商品API 2.0（ItemAPI 2.0）

サービス一覧へ戻る / ItemAPI 2.0

RMS WEB SERVICE : items.search
Overview
この機能を利用すると、指定した条件から通常商品（定期購入設定ありも含む）・予約商品・頒布会商品の商品情報を検索することができます。
商品を登録・削除してから本機能の検索情報に反映されるまで、最大24時間かかります。
削除済みの商品が検索結果に含まれる場合、「manageNumber」のみが返却されます。

※定期購入リニューアルにて追加・修正となる項目は背景色を緑に変更しています。
　定期購入リニューアルの概要は こちら をご確認ください。



Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/items/search	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
None

Query Parameter
No	Parameter Name	Logical Name	Required	Type	Multiplicity	Description
1	title	商品名	no	string	0..1	部分一致
2	tagline	キャッチコピー	no	string	0..1	部分一致
3	manageNumber	商品管理番号	no	string	0..1	部分一致
4	itemNumber	商品番号	no	string	0..1	部分一致
5	articleNumber	カタログID	no	string	0..1	部分一致
6	variantId	SKU管理番号	no	string	0..1	部分一致
7	merchantDefinedSkuId	システム連携用SKU番号	no	string	0..1	部分一致
8	genreId	ジャンルID	no	string	0..1	完全一致
9	itemType	商品種別	no	enum	0..1	完全一致

・NORMAL：通常商品
・PRE_ORDER：予約商品
・BUYING_CLUB：頒布会商品
10	standardPriceFrom	販売価格下限	no	number	0..1	1 SKUでもヒットしたら、検索結果に返却。
11	standardPriceTo	販売価格上限	no	number	0..1	1 SKUでもヒットしたら、検索結果に返却。
12	isVariantStockout	SKU在庫切れ	no	boolean	0..1	・true：在庫切れ
・false：在庫あり

※レスポンスは商品管理番号単位となるため、
検索条件によっては本フラグの指定に関わらず、
在庫ありまたは在庫なしの全てのSKU情報がレスポンスされます。
13	isItemStockout	商品在庫切れ	no	boolean	0..1	・true：商品在庫切れ
・false：商品在庫あり（一部SKU在庫切れを含む）
14	purchasablePeriodFrom	販売期間指定開始	no	date	0..1	タイムゾーンは日本標準時（JST）。
フォーマットはISO 8601（YYYY-MM-DD）。
時刻は00:00:00.000Zで自動補完。
15	purchasablePeriodTo	販売期間指定終了	no	date	0..1	タイムゾーンは日本標準時（JST）。
フォーマットはISO 8601（YYYY-MM-DD）。
時刻は23:59:59.999Zで自動補完。
16	isHiddenItem	商品倉庫指定フラグ	no	boolean	0..1	・true：商品単位で倉庫
・false：商品単位で販売中（一部SKU販売中を含む）
17	isHiddenVariant	SKU倉庫指定フラグ	no	boolean	0..1	・true：倉庫
・false：販売中

※レスポンスは商品管理番号単位となるため、
検索条件により、本フラグの指定に関わらず、
販売中または倉庫指定の全てのSKU情報がレスポンスされます。
18	isSearchable	サーチ表示フラグ	no	boolean	0..1	・true：表示
・false：非表示
19	isYamiichi	闇市フラグ	no	boolean	0..1	・true：闇市
・false：闇市ではない
20	pointApplicablePeriodFrom	ポイント変倍適用期間開始日	no	date	0..1	タイムゾーンは日本標準時（JST）。
フォーマットはISO 8601（YYYY-MM-DD）。
時刻は00:00:00.000Zで自動補完。
21	pointApplicablePeriodTo	ポイント変倍適用期間終了日	no	date	0..1	タイムゾーンは日本標準時（JST）。
フォーマットはISO 8601（YYYY-MM-DD）。
時刻は23:59:59.999Zで自動補完。
22	isOptimizedPoint	ポイント変倍種別	no	boolean	0..1	・true：運用型
・false：通常
23	pointRate	ポイント変倍率	no	number	0..1	許容値：1～20
24	maxPointRate	運用型ポイント変倍用ポイント上限倍率	no	number	0..1	許容値：5～20
25	categoryId	カテゴリID	no	string	0..1	
26	isBackOrder	在庫切れ時の注文受付	no	boolean	0..1	・true：注文を受け付ける
・false：注文を受け付けない
27	isPostageIncluded	送料無料フラグ	no	boolean	0..1	・true：送料無料
・false：送料別
28	createdFrom	検索開始日（登録日）	no	date	0..1	タイムゾーンは日本標準時（JST）。
フォーマットはISO 8601（YYYY-MM-DD）。
時刻は00:00:00.000Zで自動補完。
29	createdTo	検索終了日（登録日）	no	date	0..1	タイムゾーンは日本標準時（JST）。
フォーマットはISO 8601（YYYY-MM-DD）。
時刻は23:59:59.999Zで自動補完。
30	updatedFrom	検索開始日（更新日）	no	date	0..1	タイムゾーンは日本標準時（JST）。
フォーマットはISO 8601（YYYY-MM-DD）。
時刻は00:00:00.000Zで自動補完。
31	updatedTo	検索終了日（更新日）	no	date	0..1	タイムゾーンは日本標準時（JST）。
フォーマットはISO 8601（YYYY-MM-DD）。
時刻は23:59:59.999Zで自動補完。
32	sortKey	ソートキー	no	enum	0..1	・updated：更新日（デフォルト）
・created：登録日
・itemDisplaySequence：カテゴリ表示順位
・manageNumber：商品管理番号
・purchasablePeriodStart：販売期間開始
・purchasablePeriodEnd：販売期間終了
・pointCampaignStart：ポイント変倍期間開始
・pointCampaignEnd：ポイント変倍期間終了
・pointRate：ポイント変倍率
・reviewCount：レビュー件数
・reviewAverageRating：レビュー評価平均点
33	sortOrder	ソート順	no	enum	0..1	・desc：降順（デフォルト）
・asc：昇順
34	offset	検索結果取得開始位置	no	number	0..1	許容値：0～10000
指定した場合、cursorMarkは指定不可。
35	hits	検索結果取得上限数	no	number	0..1	許容値：1～100
デフォルト：10
36	cursorMark	カーソルマーク	no	string	0..1	指定した場合、sortKeyとsortOrderは指定不可。
37	isCategoryIncluded	店舗内カテゴリ情報返却	no	boolean	0..1	・true：取得する
・false：取得しない（デフォルト）
38	isReviewIncluded	レビュー情報返却	no	boolean	0..1	・true：取得する
・false：取得しない（デフォルト）
39	isInventoryIncluded	在庫情報返却	no	boolean	0..1	・true：取得する
・false：取得しない（デフォルト）
40	isSubscription	定期購入設定	no	boolean	0..1	・true：通常商品（定期購入設定あり）
・false：通常商品（定期購入設定あり）以外
41	basePriceFrom	定期購入販売価格・頒布会販売価格下限	no	number	0..1	
42	basePriceTo	定期購入販売価格・頒布会販売価格上限	no	number	0..1	
HTTP Body
None

Response
HTTP Header
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合

No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
L1	L2	L3	L4	L5	L6	L7
1	numFound	検索結果数	yes	int	32	1	
2	offset	検索結果取得開始位置	yes	int	-	1	
3	nextCursorMark	ネクストカーソルマーク	no	string	-	1	終了条件は指定したcursorMark=nextCursorMarkとなることです。
Query Parameterに"cursorMark"が指定された時のみ返却。
4	results	検索結果リスト	yes	List<object>	-	0..100	
5		item	商品情報	no	object	-	0,1	
6			manageNumber	商品管理番号	yes	string	32	1	以下の英数字、記号。
・"a~z"
・"0~9"
・"-", "_" 
7			itemNumber	商品番号	no	string	32	0,1	
8			title	商品名	yes	string	255	1	
9			tagline	キャッチコピー	no	string	174	0,1	
10			productDescription	商品説明文	no	object	-	0,1	
11				pc	PC用商品説明文	no	string	10240	0,1	
12				sp	スマートフォン用商品説明文	no	string	10240	0,1	
13			salesDescription	PC用販売説明文	no	string	10240	0,1	
14			precautions	医薬品説明文・注意事項	no	object	-	0,1	
15				description	医薬品説明文	no	string	20480	0,1	
16				agreement	医薬品注意事項	no	string	20480	0,1	
17			itemType	商品種別	yes	enum	-	1	・NORML：通常商品
・PRE_ORDER：予約商品
・BUYING_CLUB：頒布会商品
18			images	商品画像	no	List<images>	-	0..20	商品画像のリスト
19				type	商品画像種別	no	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
20				location	商品画像URL	no	string	255	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
21				alt	商品画像名（ALT）	no	string	255	0,1	商品レベルでの画像の代替テキスト。
22			whiteBgImage	白背景画像	no	object	-	0,1	
23				type	白背景画像種別	no	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
24				location	白背景画像URL	no	string	-	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
25			video	動画	no	object	-	0,1	
26				type	動画種別	no	enum	-	1	・HTML：HTML形式
27				parameters	動画パラメータ	no	object	-	1	
28					value	動画のURL	no	string	2048	1	固定のフォーマットとドメイン
29			genreId	ジャンルID	yes	string	6	1	6桁の数字：100000 ～ 999999
30			tags	非製品属性タグID	no	List<int>	-	0..32	商品の詳細属性情報。
7桁の数字：5000000～9999999
31			hideItem	倉庫指定	yes	boolean	-	1	・true：倉庫に入れる
・false：販売中
32			unlimitedInventoryFlag	在庫設定なし	yes	boolean	-	1	・true：在庫設定なし
・false：在庫設定あり
33			customizationOptions	商品オプション（項目選択肢）	no	list<customizationOptions>	-	0..20	
34				displayName	商品オプション（項目選択肢）項目名	no	string	255	1	
35				inputType	商品オプション選択肢タイプ	no	enum	-	1	・SINGLE_SELECTION：セレクトボックス
・MULTIPLE_SELECTION：チェックボックス
・FREE_TEXT：フリーテキスト
36				required	商品オプション必須フラグ	no	boolean	-	1	・true：必須
・false：任意
37				selections	Select/Checkbox用選択肢リスト	no	List<selections>	-	0..n	範囲
・inputType=SINGLE_SELECTION：1～100
・inputType=MULTIPLE_SELECTION：1～40
38					displayValue	商品オプション選択肢名	no	string	32	1	
39			releaseDate	予約商品発売日	no	string	-	0,1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、日まで。
40			purchasablePeriod	販売期間指定	no	object	-	0,1	
41				start	販売開始日時	no	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）。
42				end	販売終了日時	no	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）。
43			subscription	定期購入商品設定	no	object	-	0,1	
44				shippingDateFlag	お届け日付指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可
45				shippingIntervalFlag	お届け間隔（曜日）指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可
46			buyingClub	頒布会商品設定	no	object	-	0,1	
47				numberOfDeliveries	お届け回数	no	number	-	1	許容値：2～12
48				displayItems	商品内訳情報の表示	no	boolean	-	1	
49				items	商品内訳情報	no	List<string>	127	0..12	
50				shippingDateFlag	お届け日付指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可
51				shippingIntervalFlag	お届け間隔（曜日）指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可
52			features	その他設定	yes	object	-	1	
53				searchVisibility	サーチ表示	yes	enum	-	1	・ALWAYS_VISIBLE：表示
・ALWAYS_HIDDEN：非表示
54				displayNormalCartButton	注文ボタン	yes	boolean	-	1	・true：表示
・false：非表示
55				displaySubscriptionCartButton	定期購入・頒布会ボタン	yes	boolean	-	1	・true：表示
・false：非表示
56				inventoryDisplay	在庫数表示	yes	enum	-	1	・DISPLAY_ABSOLUTE_STOCK_COUNT：表示
・HIDDEN_STOCK：非表示
・DISPLAY_LOW_STOCK：残り在庫数表示閾値より小さい場合、△を表示する
57				lowStockThreshold	残り在庫数表示閾値	no	number	-	0,1	許容値：1～20
58				shopContact	商品問い合わせボタン	yes	boolean	-	1	・true：表示
・false：非表示
59				review	レビュー本文表示	yes	enum	-	1	・SHOP_SETTING：店舗設定に従う
・VISIBLE：表示
・HIDDEN：非表示
60				displayManufacturerContents	メーカー提供情報表示	yes	boolean	-	1	・true：表示
・false：非表示
61				socialGiftFlag	ソーシャルギフトフラグ	yes	boolean	-	1	・true：対応する
・false：対応しない
62			accessControl	アクセスコントロール	no	object	-	1	
63				accessPassword	闇市パスワード	no	string	32	1	小文字で以下の英数字、記号。

・"a~z"
・"0-9"
・"-", "_" 
64			payment	決済情報	yes	object	-	1	
65				taxIncluded	消費税込み	yes	boolean	-	1	・true：税込
・false：税別
66				taxRate	消費税税率	no	string	-	0,1	以下のいずれか。

・0：非課税
・0.08：8%
・0.1：10%
・null：店舗設定に従う
67				cashOnDeliveryFeeIncluded	代引料	yes	boolean	-	1	・true：代引料込
・false：代引料別
68			pointCampaign	ポイント変倍情報	no	object	-	0,1	
69				applicablePeriod	ポイント変倍適用期間	no	object	-	1	
70					start	開始日時	no	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）。
71					end	終了日時	no	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）。
"9999-12-31T23:59:59+09:00"が設定されている場合は終了日時が設定されていないポイント変倍情報であることを示す。
72				benefits	ポイント情報	no	object	-	1	
73					pointRate	ポイント変倍率	no	number	-	1	許容値：1～20
74				optimization	運用型ポイント情報	no	object	-	0,1	運用型ポイント変倍サービスを申し込んだ店舗のみ返される。
75					maxPointRate	ポイント上限倍率	no	number	-	1	許容値：5～20
76			itemDisplaySequence	店舗内カテゴリでの表示順位	yes	number	-	1	許容値：1～999999999
77			layout	レイアウト設定	yes	object	-	1	
78				itemLayoutId	商品ページレイアウト	yes	number	-	1	・1：テンプレートA
・2：テンプレートB
・3：テンプレートC
・4：テンプレートD
・5：テンプレートE
・6：テンプレートF
・8：テンプレートG
79				navigationId	ヘッダー・フッター・レフトナビのテンプレートID	yes	number	-	1	
80				layoutSequenceId	表示項目の並び順テンプレートID	yes	number	-	1	
81				smallDescriptionId	共通説明文(小)テンプレートID	yes	number	-	1	
82				largeDescriptionId	共通説明文(大)テンプレートID	yes	number	-	1	
83				showcaseId	目玉商品テンプレートID	yes	number	-	1	
84			variantSelectors	バリエーション項目	no	List<variantSelectors>	-	0..6	商品ページ上の表示はリクエストの順番と同一。
85				key	バリエーション項目キー	no	string	-	1	バリエーション項目名の識別子。
86				displayName	バリエーション項目名	no	string	32 	1	
87				values	バリエーション選択肢リスト	no	List<selectorValues>	-	1..40	
88					displayValue	バリエーション選択肢	no	string	32	1	商品ページ上の表示はリクエストの順番と同一。
89			variants	SKU	yes	object	-	1..400	
90				{variantId}	SKU管理番号	no	string	32	1	以下の英数字、記号。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_" 
91					merchantDefinedSkuId	システム連携用SKU番号	no	string	96 	0,1	英数字または日本語の文字列。
92					selectorValues	SKU情報	no	object	-	0..6	
93						{key}	バリエーション項目キー・選択肢	no	string	-	1	variantSelectors.key: variantSelectors.values.displayValue の形式。
94					images	SKU画像	no	List<images>	-	0..1	
95						type	SKU画像タイプ	no	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
96						location	SKU画像パス	no	string	255 	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
97						alt	SKU画像名（ALT）	no	string	255 	0,1	
98					restockOnCancel	在庫戻しフラグ	no	boolean	-	1	・true：在庫戻しする
・false：在庫戻ししない
99					backOrderFlag	在庫切れ時の注文受付	no	boolean	-	1	・true：注文を受け付ける
・false：注文を受け付けない
100					normalDeliveryDateId	在庫あり時納期管理番号	no	number	-	0,1	
101					backOrderDeliveryDateId	在庫切れ時納期管理番号	no	number	-	0,1	
102					orderQuantityLimit	注文受付数	no	number	-	0,1	注文できる最大数量。
許容値：0～400

・0：非表示（最大個数1個）
・n （1～400）：最大購入数を設定
・null： 自由入力
103					referencePrice	表示価格情報	no	object	-	0,1	
104						displayType	表示価格種別	no	enum	-	1	・REFERENCE_PRICE：選択した表示価格文言
・SHOP_SETTING：店舗設定に従う
・OPEN_PRICE：メーカー希望小売価格 オープン価格
105						type	表示価格文言	no	number	-	0,1	・1：当店通常価格
・2：メーカー希望小売価格
・4：商品価格ナビのデータ参照
106						value	表示価格	no	string	-	0,1	許容値：1～999999999
107					features	その他設定	no	object	-	0,1	
108						restockNotification	再入荷お知らせボタン	no	boolean	-	1	・true：表示
・false：非表示
109						noshi	のし対応	no	boolean	-	1	・true：対応する
・false：対応しない
110					hidden	SKU倉庫設定	no	boolean	-	1	・true：倉庫
・false：販売中
111					standardPrice	販売価格	no	string	-	0,1	許容値：0～999999999
112					subscriptionPrice	定期購入販売価格設定・頒布会販売価格設定	no	object	-	0,1	
113						basePrice	定期購入販売価格・頒布会販売価格	no	string	-	0,1	許容値：1～999999999
114						individualPrices	個別価格	no	object	-	0,1	
115							firstPrice	初回価格	no	string	-	0,1	許容値：1～999999999
116					articleNumberForSet	セット商品用カタログID	no	List<string>	30	0..20	通常商品かつカタログIDなしの理由に「セット商品」を指定した商品のみが対象。
セットの構成であるSKUのカタログID。
20個まで指定可能。
117					articleNumber	カタログID情報	no	object	-	0,1	
118						value	カタログID	no	string	30 	0,1	商品の標準製品コード。
英数字が利用可能。
119						exemptionReason	カタログIDなしの理由	no	number	-	0,1	・1：セット商品
・2：サービス商品
・3：店舗オリジナル商品
・4：項目選択肢在庫商品
・5：該当製品コードなし
・6：頒布会商品
120					shipping	送料情報	yes	object	-	0,1	
121						fee	個別送料	no	string	-	0,1	許容値：0～999999999
122						postageIncluded	送料無料フラグ	no	boolean	-	1	・true：送料無料
・false：送料別
123						shopAreaSoryoPatternId	地域別個別送料管理番号	no	number	-	0,1	許容値：1～20
124						shippingMethodGroup	配送方法セット管理番号	no	string	40 	0,1	配送方法セット管理番号に自動選択対象以外の設定がある場合のみ、この項目を返却します。

※配送方法セット管理番号は、以下より確認してください。

ShopAPI >shop.deliverySetInfo.get 
　4.2.6. Level 4: deliverySetInfo - deliverySetId
125						postageSegment	送料区分情報	no	object	-	0,1	
126							local	送料区分1（ローカル）	no	number	-	0,1	ローカルの送料区分番号。
127							overseas	送料区分2（海外）	no	number	-	0,1	海外の送料区分番号。
128						overseasDeliveryId	海外配送管理番号	no	number	-	0,1	許容値：1～5
129						singleItemShipping	単品配送設定	no	number	-	1	・0：設定なし
・1：産地直送の商品
・2：メーカー直送の商品
・3： ケース売りの商品
・4：長尺・異形の商品
・5：出荷地が異なる商品
・6：温度帯が異なる商品
130						okihaiSetting	置き配設定	yes	boolean	-	1	・true : 受け付ける
・false : 受け付けない
131					specs	属性情報自由入力行	no	List<object>	-	0..5	商品ページ上の「商品仕様」に追記できる任意項目。
132						label	属性情報自由入力行（項目）	no	string	40 	1	
133						value	属性情報自由入力行（値）	no	string	140 	1	
134					attributes	属性情報	no	List<object>	-	0..100	商品ページ上に「商品仕様」として表示される項目。
135						name	属性情報名	no	string	-	1	
136						values	属性情報（実値）	no	List<string>	-	1..n	フォーマットはNavigationAPI 2.0 の  genres.attributes.get あるいは genres.attributes.dictionaryValues.get の下記項目の値に準ずる。
　4.2.6. Level 3: attributes - dataType
137						unit	単位	no	string	-	0,1	属性情報の単位。
138			created	登録日時	yes	string	-	1	商品の登録日時。
フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、秒まで。
139			updated	更新日時	yes	string	-	1	商品の更新日時。
フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、秒まで。
140		category	カテゴリ情報	no	object	-	0,1	isCategoryIncluded=trueの時のみ返却。
141			categoryIds	カテゴリIDリスト	no	List<string>	-	1	商品に紐づくカテゴリIDのリスト。
142		review	レビュー情報	no	object	-	0,1	isReviewIncluded=trueの時のみ返却。
143			count	レビュー件数	no	int	-	1	
144			averageRating	レビュー平均点	no	float	-	1	
145		inventory	在庫情報	no	object	-	0,1	isInventoryIncluded=trueの時のみ返却。

※以下3項目のいずれかに値が設定されている場合にのみinventoryが返却されます。
  以下3項目すべてに明示的にリードタイムを設定しておらず、自動選択のリードタイムが適用されている場合にはinventoryは返却されません。
・operationLeadTime.normalDeliveryTimeId
・operationLeadTime.backOrderDeliveryTimeId
・shipFromIds
146			{variantId}	SKU管理番号	no	string	32	0..400	英数字または"-", "_"。
147				operationLeadTime	出荷リードタイム	no	object	-	0,1	
148					normalDeliveryTimeId	在庫あり時出荷リードタイムID	no	number	-	0,1	IDの値はShopAPIの operationLeadTime.get をご利用いただくことで、下記の項目から取得可能です。

Level 3: operationLeadTime - operationLeadTimeId
149					backOrderDeliveryTimeId	在庫切れ時出荷リードタイムID	no	number	-	0,1	IDの値はShopAPIの operationLeadTime.get をご利用いただくことで、下記の項目から取得可能です。

Level 3: operationLeadTime - operationLeadTimeId
150				shipFromIds	配送リードタイムIDのリスト	no	list<int>	-	0..1	IDの値はShopAPIの shipFrom.get をご利用いただくことで、下記の項目から取得可能です。

Level 3: shipFrom - shipFromId
151			created	登録日時	yes	string	-	1	在庫情報の登録日時。 フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、秒まで。
152			updated	更新日時	yes	string	-	1	在庫情報の更新日時。 フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、秒まで。

失敗した場合

No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
L1	L2
1	errors	エラー	yes	List<error>	-	1..n	エラーのリスト
2		code	コード	yes	string	-	1	エラーコード。詳細はこちら。
3		message	メッセージ	yes	string	-	1
Sample
成功した場合
クエリパラメータを設定していない場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 123456,
    "offset": 0,
    "results": [
        {
            "item": {
               "manageNumber": "torimesi",
               "itemType": "NORMAL",
               "itemNumber": "torimesi",
               "title": "水郷どり炊き込みご飯 2合用 鶏めし 鶏飯 お取り寄せグルメ テレビ とりめし 炊き込みご飯の素 釜めし 釜飯 釜飯の素 鶏肉",
               "tagline": "料亭の味をご家庭で・・・上品で繊細、それでいて鶏肉の旨みが凝縮されている逸品です。［鶏肉 炊き込みご飯の素 お取り寄せグルメ テレビ ］",
               "productDescription": {
                   "pc": "explanation for PC",
                   "sp": "explanation for SP"
               },
               "salesDescription": "salesexplanation for PC",
               "images": [
                   {
                       "type": "CABINET",
                       "location": "/01003752/torimesi.jpg",
                       "alt": "itemname"
                   }
               ],
               "whiteBgImage": {
                   "type": "GOLD",
                   "location": "/torimesi.jpg"
               },
               "video": {
                   "type": "HTML",
                   "parameters": {
                       "value": "<script src=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\" type=\"text/javascript\"></script>"
                   }
               },
               "genreId": "201198",
               "tags": [
                   7654321,
                   9000000
               ],
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "customizationOptions": [
                   {
                       "displayName": "ギフト包装",
                       "inputType": "SINGLE_SELECTION",
                       "required": true,
                       "selections": [
                           {
                               "displayValue": "はい"
                           }
                       ]
                   }
               ],
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "DISPLAY_LOW_STOCK",
                   "lowStockThreshold": 1,
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": false,
                   "taxRate": "0.1",
                   "cashOnDeliveryFeeIncluded": true
               },
               "pointCampaign": {
                   "applicablePeriod": {
                       "start": "2018-04-28T07:59:49+09:00",
                       "end": "2018-05-28T07:59:49+09:00"
                   },
                   "benefits": {
                       "pointRate": 15
                   },
                   "optimization": {
                       "maxPointRate": 20
                   }
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 10,
                   "layoutSequenceId": 20,
                   "smallDescriptionId": 30,
                   "largeDescriptionId": 40,
                   "showcaseId": 50
               },
               "variants": {
                   "normal-inventory": {
                       "restockOnCancel": false,
                       "normalDeliveryDateId":1,
                       "backOrderFlag": false,
                       "standardPrice":1000,
                       "articleNumber":{
                         "value":"0689640032932",
                       },
                       "attributes": [
                         {
                           "name": "ブランド名",
                           "values": [
                             "お米"
                           ]
                         },
                         {
                           "name": "シリーズ名",
                           "values": [
                             "鶏めし"
                           ]
                         },
                         {
                           "name": "原産国／製造国",
                           "values": [
                             "日本"
                           ]
                         },
                         {
                           "name": "総個数",
                           "values": [
                             "1"
                               ]
                         },
                         {
                           "name": "総重量",
                           "values": [
                              "10"
                            ],
                            "unit": "kg"
                         }
                      ]
                   }
               },
               "created": "2021-07-08T01:05:31+09:00",
               "updated": "2021-07-29T00:24:22+09:00"
            }
        },
        {
            "item": {
                "manageNumber": "pre-order-item",
                "itemType": "PRE_ORDER",
                "itemNumber": "itemnumber",
                "title": "予約商品の商品名",
                "tagline": "pcandspcatchcopy",
                "productDescription": {
                    "pc": "explanationforPC",
                    "sp": "explanationforSP"
                },
                "salesDescription": "salesexplanationforPC",
                "images": [
                    {
                        "type": "CABINET",
                        "location": "/01003752/dog_07.jpg",
                        "alt": "itemname"
                    }
                ],
                "whiteBgImage": {
                    "type": "GOLD",
                    "location": "/vegetable-blue-jp.jpg"
                },
                "video": {
                    "type": "HTML",
                    "parameters": {
                        "value": "<scriptsrc=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\"type=\"text/javascript\"></script>"
                    }
                },
                "genreId": "206878",
                "tags": [
                   7654321,
                   9000000
                ],
                "hideItem": false,
                "unlimitedInventoryFlag": false,
                "releaseDate": "2018-04-28",
                "customizationOptions": [
                    {
                        "displayName": "ギフト包装",
                        "inputType": "SINGLE_SELECTION",
                        "required": true,
                        "selections": [
                            {
                                "displayValue": "はい"
                            }
                        ]
                    }
                ],
                "features": {
                     "searchVisibility": "ALWAYS_VISIBLE",
                     "shopContact": true,
　　　　　  "review": "SHOP_SETTING",
                    "displayManufacturerContents": false,
                    "displayNormalCartButton": true,
                    "displaySubscriptionCartButton": false,
                    "inventoryDisplay": "HIDDEN_STOCK",
                    "lowStockThreshold": 1,
                    "socialGiftFlag": false
                },
                "payment": {
                    "taxIncluded": false,
                    "taxRate": "0.1",
                    "cashOnDeliveryFeeIncluded": true
                },
                "pointCampaign": {
                    "applicablePeriod": {
                        "start": "2018-04-28T07:59:49+09:00",
                        "end": "2018-05-28T07:59:49+09:00"
                    },
                    "benefits": {
                        "pointRate": 15
                    },
                    "optimization": {
                        "maxPointRate": 15
                    }
                },
                "itemDisplaySequence": 999999999,
                "layout": {
                    "itemLayoutId": 1,
                    "navigationId": 10,
                    "layoutSequenceId": 20,
                    "smallDescriptionId": 30,
                    "largeDescriptionId": 40,
                    "showcaseId": 50
                },
                "variantSelectors": [
                    {
                        "key": "size-key",
                        "displayName": "サイズ",
                        "values": [
                            {
                                "displayValue": "Sサイズ"
                            },
                            {
                                "displayValue": "Mサイズ"
                            }
                        ]
                    },
                    {
                        "key": "color-key",
                        "displayName": "カラー",
                        "values": [
                            {
                                "displayValue": "青色"
                            }
                        ]
                    }
                ],
                "variants": {
                    "sku-1": {
                        "merchantDefinedSkuId": "システム連携SKU商品番号",
                        "selectorValues": {
                            "color-key": "青色",
                            "size-key": "Sサイズ"
                        },
                        "images": [
                            {
                                "type": "CABINET",
                                "location": "/01003752/dog_15.jpg",
                                "alt": "sku-image"
                            }
                        ],
                        "restockOnCancel": true,
                        "backOrderFlag": false,
                        "normalDeliveryDateId": 1,
                        "backOrderDeliveryDateId": 2,
                        "articleNumber": {
                            "exemptionReason": 1
                        },
                        "articleNumberForSet": [
                            "4901777312067",
                            "w301628",
                            "JR-VT-CTAK-S20I-JPGY4A",
                            "pc-desk-hp-800g1-sf-02"
                        ],
                        "hidden": true,
                        "orderQuantityLimit": 3,
                        "purchasablePeriod": {
                            "start": "2021-07-11T15:00:00+09:00",
                            "end": "2021-07-31T14:59:59+09:00"
                        },
                        "features": {
                            "restockNotification": true,
                            "noshi": true
                        },
                        "standardPrice": "10000",
                        "referencePrice": {
                            "displayType": "REFERENCE_PRICE",
                            "type": 1,
                            "value": "15000"
                        },
                        "shipping": {
                            "fee": "1000",
                            "postageIncluded": true,
                            "shopAreaSoryoPatternId": 2,
                            "shippingMethodGroup": "10",
                            "postageSegment": {
                                "local": 1,
                                "overseas": 2
                            },
                            "overseasDeliveryId": 3,
                            "singleItemShipping": 5,
                              "okihaiSetting": true
                        },
                        "specs": [
                            {
                                "label": "Countryoforigin",
                                "value": "Japan"
                            }
                        ],
                        "attributes": [
                            {
                                "name": "attributeName1",
                                "values": [
                                    "赤色",
                                    "100",
                                    "2021-10-15"
                                ]
                            },
                            {
                                "name": "attributeName20",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    },
                    "sku-2": {
                        "selectorValues": {
                            "color-key": "青色",
                            "size-key": "Mサイズ"
                        },
                        "standardPrice": "10000",
                        "articleNumber": {
                            "value": "4902780029294"
                        },
                        "restockOnCancel": false,
                        "backOrderFlag": false,
                        "attributes": [
                            {
                                "name": "attributeName1",
                                "values": [
                                    "赤色",
                                    "100",
                                    "2021-10-15"
                                ]
                            },
                            {
                                "name": "attributeName20",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    }
                },
                "created": "2021-07-08T01:05:31+09:00",
                "updated": "2021-07-29T00:24:22+09:00"
            }
        },
        {
            "item": {
                "manageNumber": "subscription-item",
                "itemType": "SUBSCRIPTION",
                "itemNumber": "VEGE-001-234",
                "title": "定期購入商品の商品名",
                "tagline": "PCブラウザ向けに最適化されたキャッチコピー的なフィールド",
                "productDescription": {
                    "pc": "<div>PCブラウザ向けに最適化された商品説明分(HTML)</div>",
                    "sp": "<div>携帯端末ブラウザ向けに最適化された商品説明分(HTML)</div>"
                },
                "salesDescription": "販売説明分人間用の新野菜",
                "images": [
                    {
                        "type": "CABINET",
                        "location": "/myfolder-1/myfolder-2/vegetable-red.jpg",
                        "alt": "vegetable-red"
                    },
                    {
                        "type": "GOLD",
                        "location": "/folder-1/folder-2/vegetable-blue.jpg",
                        "alt": "vegetable-blue"
                    },
                    {
                        "type": "ABSOLUTE",
                        "location": "https://image.books.rakuten.co.jp/vegetable-green.jpg",
                        "alt": "vegetable-green"
                    }
                ],
                "whiteBgImage": {
                    "type": "GOLD",
                    "location": "/vegetable-blue-jp.jpg"
                },
                "video": {
                    "type": "HTML",
                    "parameters": {
                        "value": "<scriptsrc=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\"type=\"text/javascript\"></script>"
                    }
                },
                "genreId": "558863",
                "tags": [
                   7654321,
                   9000000
                ],
                "hideItem": false,
                "customizationOptions": [
                    {
                        "displayName": "野菜にアレルギーの経験はありますか",
                        "inputType": "SINGLE_SELECTION",
                        "required": true,
                        "selections": [
                            {
                                "displayValue": "はい"
                            },
                            {
                                "displayValue": "いいえ"
                            }
                        ]
                    }
                ],
                "subscription": {
                    "shippingDateFlag": true,
                    "shippingIntervalFlag": true
                },
                "features": {
                    "searchVisibility": "ALWAYS_VISIBLE",
                    "displayNormalCartButton": false,
                    "displaySubscriptionCartButton": true,
                    "inventoryDisplay": "DISPLAY_LOW_STOCK",
                    "lowStockThreshold": 10,
                    "shopContact": true,
                    "review": "HIDDEN",
                    "displayManufacturerContents": true,
                    "socialGiftFlag": false
                },
                "payment": {
                    "taxIncluded": false,
                    "taxRate": "0.1",
                    "cashOnDeliveryFeeIncluded": true
                },
                "pointCampaign": {
                    "applicablePeriod": {
                        "start": "2018-04-28T07:59:49+09:00",
                        "end": "2018-05-28T07:59:49+09:00"
                    },
                    "benefits": {
                        "pointRate": 15
                    },
                    "optimization": {
                        "maxPointRate": 15
                    }
                },
                "itemDisplaySequence": 9999,
                "layout": {
                    "itemLayoutId": 1,
                    "navigationId": 2933,
                    "layoutSequenceId": 46272,
                    "smallDescriptionId": 2,
                    "largeDescriptionId": 566,
                    "showcaseId": 199
                },
                "variantSelectors": [
                    {
                        "key": "color-key",
                        "displayName": "カラー",
                        "values": [
                            {
                                "displayValue": "赤"
                            },
                            {
                                "displayValue": "青"
                            }
                        ]
                    },
                    {
                        "key": "size-key",
                        "displayName": "サイズ",
                        "values": [
                            {
                                "displayValue": "S"
                            },
                            {
                                "displayValue": "M"
                            }
                        ]
                    }
                ],
                "variants": {
                    "sku-001": {
                        "merchantDefinedSkuId": "システム連携SKU商品番号",
                        "selectorValues": {
                            "color-key": "赤",
                            "size-key": "S"
                        },
                        "images": [
                            {
                                "type": "CABINET",
                                "location": "/01003752/dog_15.jpg",
                                "alt": "sku-image"
                            }
                        ],
                        "restockOnCancel": true,
                        "backOrderFlag": false,
                        "normalDeliveryDateId": 1,
                        "backOrderDeliveryDateId": 2,
                        "hidden": false,
                        "orderQuantityLimit": 3,
                        "purchasablePeriod": {
                            "start": "2021-07-11T15:00:00+09:00",
                            "end": "2021-07-31T14:59:59+09:00"
                        },
                        "features": {
                            "restockNotification": false,
                            "noshi": true
                        },
                        "subscriptionPrice": {
                            "basePrice": "2000",
                            "individualPrices": {
                                "firstPrice": "1000"
                            }
                        },
                        "referencePrice": {
                            "displayType": "REFERENCE_PRICE",
                            "type": 1,
                            "value": "2000"
                        },
                        "shipping": {
                            "fee": "1000",
                            "postageIncluded": true,
                            "shopAreaSoryoPatternId": 2,
                            "shippingMethodGroup": "10",
                            "postageSegment": {
                                "local": 1,
                                "overseas": 2
                            },
                            "overseasDeliveryId": 3,
                            "singleItemShipping": 5,
                              "okihaiSetting": true
                        },
                        "specs": [
                            {
                                "label": "Countryoforigin",
                                "value": "Japan"
                            }
                        ],
                        "attributes": [
                            {
                                "name": "attributeName1",
                                "values": [
                                    "赤色",
                                    "100",
                                    "2021-10-15"
                                ]
                            },
                            {
                                "name": "attributeName20",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    },
                    "sku-002": {
                        "selectorValues": {
                            "color-key": "赤",
                            "size-key": "M"
                        },
                        "standardPrice": "10000",
                        "articleNumber": {
                            "value": "4902780029294"
                        },
                        "restockOnCancel": false,
                        "backOrderFlag": false,
                          "shipping": {
                              "okihaiSetting": true
                         },
                        "attributes": [
                            {
                                "name": "attributeName1",
                                "values": [
                                    "赤色",
                                    "100",
                                    "2021-10-15"
                                ]
                            },
                            {
                                "name": "attributeName20",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    }
                },
                "created": "2018-04-28T07:59:49+09:00",
                "updated": "2021-08-31T07:59:49+09:00"
            }
        },
...
        { 
            "item": {
               "manageNumber": "20220524",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            }
        }
    ]
}
クエリパラメータに何らかのフィールド値が指定されている場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search?itemType=NORMAL&isHiddenItem=false' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 100000,
    "offset": 0,
    "results": [
        {
            "item": {
               "manageNumber": "torimesi",
               "itemType": "NORMAL",
               "itemNumber": "torimesi",
               "title": "水郷どり炊き込みご飯 2合用 鶏めし 鶏飯 お取り寄せグルメ テレビ とりめし 炊き込みご飯の素 釜めし 釜飯 釜飯の素 鶏肉",
               "tagline": "料亭の味をご家庭で・・・上品で繊細、それでいて鶏肉の旨みが凝縮されている逸品です。［鶏肉 炊き込みご飯の素 お取り寄せグルメ テレビ ］",
               "productDescription": {
                   "pc": "explanation for PC",
                   "sp": "explanation for SP"
               },
               "salesDescription": "salesexplanation for PC",
               "images": [
                   {
                       "type": "CABINET",
                       "location": "/01003752/torimesi.jpg",
                       "alt": "itemname"
                   }
               ],
               "whiteBgImage": {
                   "type": "GOLD",
                   "location": "/torimesi.jpg"
               },
               "video": {
                   "type": "HTML",
                   "parameters": {
                       "value": "<script src=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\" type=\"text/javascript\"></script>"
                   }
               },
               "genreId": "201198",
               "tags": [
                   7654321,
                   9000000
               ],
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "customizationOptions": [
                   {
                       "displayName": "ギフト包装",
                       "inputType": "SINGLE_SELECTION",
                       "required": true,
                       "selections": [
                           {
                               "displayValue": "はい"
                           }
                       ]
                   }
               ],
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "DISPLAY_LOW_STOCK",
                   "lowStockThreshold": 1,
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": false,
                   "taxRate": "0.1",
                   "cashOnDeliveryFeeIncluded": true
               },
               "pointCampaign": {
                   "applicablePeriod": {
                       "start": "2018-04-28T07:59:49+09:00",
                       "end": "2018-05-28T07:59:49+09:00"
                   },
                   "benefits": {
                       "pointRate": 15
                   },
                   "optimization": {
                       "maxPointRate": 20
                   }
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 10,
                   "layoutSequenceId": 20,
                   "smallDescriptionId": 30,
                   "largeDescriptionId": 40,
                   "showcaseId": 50
               },
               "variants": {
                   "normal-inventory": {
                       "restockOnCancel": false,
                       "normalDeliveryDateId":1,
                       "backOrderFlag": false,
                       "standardPrice":1000,
                       "articleNumber":{
                         "value":"0689640032932",
                       },
                         "shipping": {
                             "okihaiSetting": true
                        },
                       "attributes": [
                         {
                           "name": "ブランド名",
                           "values": [
                             "お米"
                           ]
                         },
                         {
                           "name": "シリーズ名",
                           "values": [
                             "鶏めし"
                           ]
                         },
                         {
                           "name": "原産国／製造国",
                           "values": [
                             "日本"
                           ]
                         },
                         {
                           "name": "総個数",
                           "values": [
                             "1"
                               ]
                         },
                         {
                           "name": "総重量",
                           "values": [
                              "10"
                            ],
                            "unit": "kg"
                         }
                      ]
                   }
               },
               "created": "2021-07-08T01:05:31+09:00",
               "updated": "2021-07-29T00:24:22+09:00"
            }
        },
...
        { 
            "item": {
               "manageNumber": "20220524",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            }
        }
    ]
}
クエリパラメータにソート順が指定されている場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search?sortKey=manageNumber&sortOrder=asc' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 123456,
    "offset": 0,
    "results": [
        { 
            "item": {
               "manageNumber": "20220524",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            },
            "review": {
                "count": 5,
                "averageRating": 4.0
            }
        },
        { 
            "item": {
               "manageNumber": "20220530",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            },
            "review": {
                "count": 5,
                "averageRating": 4.0
            }
        },
...
       { 
            "item": {
               "manageNumber": "bcd",
               "itemType": "NORMAL",
               "title": "bcdsample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            },
            "review": {
                "count": 5,
                "averageRating": 4.0
            }
        }
    ]
}
クエリパラメータにisCategoryIncludedとisReviewIncludedが指定されている場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search?isCategoryIncluded=true&isReviewIncluded=true' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 123456,
    "offset": 0,
    "results": [
        {
            "item": {
               "manageNumber": "torimesi",
               "itemType": "NORMAL",
               "itemNumber": "torimesi",
               "title": "水郷どり炊き込みご飯 2合用 鶏めし 鶏飯 お取り寄せグルメ テレビ とりめし 炊き込みご飯の素 釜めし 釜飯 釜飯の素 鶏肉",
               "tagline": "料亭の味をご家庭で・・・上品で繊細、それでいて鶏肉の旨みが凝縮されている逸品です。［鶏肉 炊き込みご飯の素 お取り寄せグルメ テレビ ］",
               "productDescription": {
                   "pc": "explanation for PC",
                   "sp": "explanation for SP"
               },
               "salesDescription": "salesexplanation for PC",
               "images": [
                   {
                       "type": "CABINET",
                       "location": "/01003752/torimesi.jpg",
                       "alt": "itemname"
                   }
               ],
               "whiteBgImage": {
                   "type": "GOLD",
                   "location": "/torimesi.jpg"
               },
               "video": {
                   "type": "HTML",
                   "parameters": {
                       "value": "<script src=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\" type=\"text/javascript\"></script>"
                   }
               },
               "genreId": "201198",
               "tags": [
                   7654321,
                   9000000
               ],
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "customizationOptions": [
                   {
                       "displayName": "ギフト包装",
                       "inputType": "SINGLE_SELECTION",
                       "required": true,
                       "selections": [
                           {
                               "displayValue": "はい"
                           }
                       ]
                   }
               ],
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "DISPLAY_LOW_STOCK",
                   "lowStockThreshold": 1,
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": false,
                   "taxRate": "0.1",
                   "cashOnDeliveryFeeIncluded": true
               },
               "pointCampaign": {
                   "applicablePeriod": {
                       "start": "2018-04-28T07:59:49+09:00",
                       "end": "2018-05-28T07:59:49+09:00"
                   },
                   "benefits": {
                       "pointRate": 15
                   },
                   "optimization": {
                       "maxPointRate": 20
                   }
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 10,
                   "layoutSequenceId": 20,
                   "smallDescriptionId": 30,
                   "largeDescriptionId": 40,
                   "showcaseId": 50
               },
               "variants": {
                   "normal-inventory": {
                       "restockOnCancel": false,
                       "normalDeliveryDateId":1,
                       "backOrderFlag": false,
                       "standardPrice":1000,
                       "articleNumber":{
                         "value":"0689640032932",
                       },
                        "shipping": {
                            "okihaiSetting": true
                         },
                       "attributes": [
                         {
                           "name": "ブランド名",
                           "values": [
                             "お米"
                           ]
                         },
                         {
                           "name": "シリーズ名",
                           "values": [
                             "鶏めし"
                           ]
                         },
                         {
                           "name": "原産国／製造国",
                           "values": [
                             "日本"
                           ]
                         },
                         {
                           "name": "総個数",
                           "values": [
                             "1"
                               ]
                         },
                         {
                           "name": "総重量",
                           "values": [
                              "10"
                            ],
                            "unit": "kg"
                         }
                      ]
                   }
               },
               "created": "2021-07-08T01:05:31+09:00",
               "updated": "2021-07-29T00:24:22+09:00"
            },
            "review": {
                "count": 5,
                "averageRating": 4.0
            },
            "category": [10000000]
        },
        {
            "item": {
                "manageNumber": "pre-order-item",
                "itemType": "PRE_ORDER",
                "itemNumber": "itemnumber",
                "title": "予約商品の商品名",
                "tagline": "pcandspcatchcopy",
                "productDescription": {
                    "pc": "explanationforPC",
                    "sp": "explanationforSP"
                },
                "salesDescription": "salesexplanationforPC",
                "images": [
                    {
                        "type": "CABINET",
                        "location": "/01003752/dog_07.jpg",
                        "alt": "itemname"
                    }
                ],
                "whiteBgImage": {
                    "type": "GOLD",
                    "location": "/vegetable-blue-jp.jpg"
                },
                "video": {
                    "type": "HTML",
                    "parameters": {
                        "value": "<scriptsrc=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\"type=\"text/javascript\"></script>"
                    }
                },
                "genreId": "206878",
                "tags": [
                   7654321,
                   9000000
                ],
                "hideItem": false,
                "unlimitedInventoryFlag": false,
                "releaseDate": "2018-04-28",
                "customizationOptions": [
                    {
                        "displayName": "ギフト包装",
                        "inputType": "SINGLE_SELECTION",
                        "required": true,
                        "selections": [
                            {
                                "displayValue": "はい"
                            }
                        ]
                    }
                ],
                "features": {
                    "searchVisibility": "ALWAYS_VISIBLE",
                    "shopContact": true,
                    "review": "SHOP_SETTING",
                    "displayManufacturerContents": false,
                    "displayNormalCartButton": true,
                    "displaySubscriptionCartButton": false,
                    "inventoryDisplay": "HIDDEN_STOCK",
                    "lowStockThreshold": 1,
                    "socialGiftFlag": false
                },
                "payment": {
                    "taxIncluded": false,
                    "taxRate": "0.1",
                    "cashOnDeliveryFeeIncluded": true
                },
                "pointCampaign": {
                    "applicablePeriod": {
                        "start": "2018-04-28T07:59:49+09:00",
                        "end": "2018-05-28T07:59:49+09:00"
                    },
                    "benefits": {
                        "pointRate": 15
                    },
                    "optimization": {
                        "maxPointRate": 15
                    }
                },
                "itemDisplaySequence": 999999999,
                "layout": {
                    "itemLayoutId": 1,
                    "navigationId": 10,
                    "layoutSequenceId": 20,
                    "smallDescriptionId": 30,
                    "largeDescriptionId": 40,
                    "showcaseId": 50
                },
                "variantSelectors": [
                    {
                        "key": "size-key",
                        "displayName": "サイズ",
                        "values": [
                            {
                                "displayValue": "Sサイズ"
                            },
                            {
                                "displayValue": "Mサイズ"
                            }
                        ]
                    },
                    {
                        "key": "color-key",
                        "displayName": "カラー",
                        "values": [
                            {
                                "displayValue": "青色"
                            }
                        ]
                    }
                ],
                "variants": {
                    "sku-1": {
                        "merchantDefinedSkuId": "システム連携SKU商品番号",
                        "selectorValues": {
                            "color-key": "青色",
                            "size-key": "Sサイズ"
                        },
                        "images": [
                            {
                                "type": "CABINET",
                                "location": "/01003752/dog_15.jpg",
                                "alt": "sku-image"
                            }
                        ],
                        "restockOnCancel": true,
                        "backOrderFlag": false,
                        "normalDeliveryDateId": 1,
                        "backOrderDeliveryDateId": 2,
                        "articleNumber": {
                            "value": "4902780029294",
                            "exemptionReason": 1
                        },
                        "articleNumberForSet": [
                            "4901777312067",
                            "w301628",
                            "JR-VT-CTAK-S20I-JPGY4A",
                            "pc-desk-hp-800g1-sf-02"
                        ],
                        "hidden": true,
                        "orderQuantityLimit": 3,
                        "purchasablePeriod": {
                            "start": "2021-07-11T15:00:00+09:00",
                            "end": "2021-07-31T14:59:59+09:00"
                        },
                        "features": {
                            "restockNotification": true,
                            "noshi": true
                        },
                        "standardPrice": "10000",
                        "referencePrice": {
                            "displayType": "REFERENCE_PRICE",
                            "type": 1,
                            "value": "15000"
                        },
                        "shipping": {
                            "fee": "1000",
                            "postageIncluded": true,
                            "shopAreaSoryoPatternId": 2,
                            "shippingMethodGroup": "10",
                            "postageSegment": {
                                "local": 1,
                                "overseas": 2
                            },
                            "overseasDeliveryId": 3,
                            "singleItemShipping": 5,
                              "okihaiSetting": true
                        },
                        "specs": [
                            {
                                "label": "Countryoforigin",
                                "value": "Japan"
                            }
                        ],
                        "attributes": [
                            {
                                "name": "attributeName1",
                                "values": [
                                    "赤色",
                                    "100",
                                    "2021-10-15"
                                ]
                            },
                            {
                                "name": "attributeName20",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    },
                    "sku-002": {
                        "selectorValues": {
                            "color-key": "赤",
                            "size-key": "M"
                        },
                        "standardPrice": "10000",
                        "articleNumber": {
                            "value": "4902780029294"
                        },
                        "restockOnCancel": false,
                        "backOrderFlag": false,
                          "shipping": {
                              "okihaiSetting": true
                          },
                         "attributes": [
                            {
                                "name": "attributeName1",
                                "values": [
                                    "赤色",
                                    "100",
                                    "2021-10-15"
                                ]
                            },
                            {
                                "name": "attributeName20",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    }
                },
                "created": "2021-07-08T01:05:31+09:00",
                "updated": "2021-07-29T00:24:22+09:00"
            },
            "review": {
                "count": 5,
                "averageRating": 4.0
            },
            "category": [10000000]
        },
        {
            "item": {
                "manageNumber": "subscription-item",
                "itemType": "SUBSCRIPTION",
                "itemNumber": "VEGE-001-234",
                "title": "定期購入商品の商品名",
                "tagline": "PCブラウザ向けに最適化されたキャッチコピー的なフィールド",
                "productDescription": {
                    "pc": "<div>PCブラウザ向けに最適化された商品説明分(HTML)</div>",
                    "sp": "<div>携帯端末ブラウザ向けに最適化された商品説明分(HTML)</div>"
                },
                "salesDescription": "販売説明分人間用の新野菜",
                "images": [
                    {
                        "type": "CABINET",
                        "location": "/myfolder-1/myfolder-2/vegetable-red.jpg",
                        "alt": "vegetable-red"
                    },
                    {
                        "type": "GOLD",
                        "location": "/folder-1/folder-2/vegetable-blue.jpg",
                        "alt": "vegetable-blue"
                    },
                    {
                        "type": "ABSOLUTE",
                        "location": "https://image.books.rakuten.co.jp/vegetable-green.jpg",
                        "alt": "vegetable-green"
                    }
                ],
                "whiteBgImage": {
                    "type": "GOLD",
                    "location": "/vegetable-blue-jp.jpg"
                },
                "video": {
                    "type": "HTML",
                    "parameters": {
                        "value": "<scriptsrc=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\"type=\"text/javascript\"></script>"
                    }
                },
                "genreId": "558863",
                "tags": [
                   7654321,
                   9000000
                ],
                "hideItem": false,
                "customizationOptions": [
                    {
                        "displayName": "野菜にアレルギーの経験はありますか",
                        "inputType": "SINGLE_SELECTION",
                        "required": true,
                        "selections": [
                            {
                                "displayValue": "はい"
                            },
                            {
                                "displayValue": "いいえ"
                            }
                        ]
                    }
                ],
                "subscription": {
                    "shippingDateFlag": true,
                    "shippingIntervalFlag": true
                },
                "features": {
                    "searchVisibility": "ALWAYS_VISIBLE",
                    "displayNormalCartButton": false,
                    "displaySubscriptionCartButton": true,
                    "inventoryDisplay": "DISPLAY_LOW_STOCK",
                    "lowStockThreshold": 10,
                    "shopContact": true,
                    "review": "HIDDEN",
                    "displayManufacturerContents": true,
                    "socialGiftFlag": false
                },
                "payment": {
                    "taxIncluded": false,
                    "taxRate": "0.1",
                    "cashOnDeliveryFeeIncluded": true
                },
                "pointCampaign": {
                    "applicablePeriod": {
                        "start": "2018-04-28T07:59:49+09:00",
                        "end": "2018-05-28T07:59:49+09:00"
                    },
                    "benefits": {
                        "pointRate": 15
                    },
                    "optimization": {
                        "maxPointRate": 15
                    }
                },
                "itemDisplaySequence": 9999,
                "layout": {
                    "itemLayoutId": 1,
                    "navigationId": 2933,
                    "layoutSequenceId": 46272,
                    "smallDescriptionId": 2,
                    "largeDescriptionId": 566,
                    "showcaseId": 199
                },
                "variantSelectors": [
                    {
                        "key": "color-key",
                        "displayName": "カラー",
                        "values": [
                            {
                                "displayValue": "赤"
                            },
                            {
                                "displayValue": "青"
                            }
                        ]
                    },
                    {
                        "key": "size-key",
                        "displayName": "サイズ",
                        "values": [
                            {
                                "displayValue": "S"
                            },
                            {
                                "displayValue": "M"
                            }
                        ]
                    }
                ],
                "variants": {
                    "sku-001": {
                        "merchantDefinedSkuId": "システム連携SKU商品番号",
                        "selectorValues": {
                            "color-key": "赤",
                            "size-key": "S"
                        },
                        "images": [
                            {
                                "type": "CABINET",
                                "location": "/01003752/dog_15.jpg",
                                "alt": "sku-image"
                            }
                        ],
                        "restockOnCancel": true,
                        "backOrderFlag": false,
                        "normalDeliveryDateId": 1,
                        "backOrderDeliveryDateId": 2,
                        "hidden": false,
                        "orderQuantityLimit": 3,
                        "purchasablePeriod": {
                            "start": "2021-07-11T15:00:00+09:00",
                            "end": "2021-07-31T14:59:59+09:00"
                        },
                        "features": {
                            "restockNotification": false,
                            "noshi": true
                        },
                        "subscriptionPrice": {
                            "basePrice": "2000",
                            "individualPrices": {
                                "firstPrice": "1000"
                            }
                        },
                        "referencePrice": {
                            "displayType": "REFERENCE_PRICE",
                            "type": 1,
                            "value": "2000"
                        },
                        "shipping": {
                            "fee": "1000",
                            "postageIncluded": true,
                            "shopAreaSoryoPatternId": 2,
                            "shippingMethodGroup": "10",
                            "postageSegment": {
                                "local": 1,
                                "overseas": 2
                            },
                            "overseasDeliveryId": 3,
                            "singleItemShipping": 5,
                              "okihaiSetting": true
                        },
                        "specs": [
                            {
                                "label": "Countryoforigin",
                                "value": "Japan"
                            }
                        ],
                        "attributes": [
                            {
                                "name": "attributeName1",
                                "values": [
                                    "赤色",
                                    "100",
                                    "2021-10-15"
                                ]
                            },
                            {
                                "name": "attributeName20",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    },
                    "sku-002": {
                        "selectorValues": {
                            "color-key": "赤",
                            "size-key": "M"
                        },
                        "standardPrice": "10000",
                        "articleNumber": {
                            "value": "4902780029294"
                        },
                        "restockOnCancel": false,
                        "backOrderFlag": false,
                          "shipping": {
                              "okihaiSetting": true
                         },
                        "attributes": [
                            {
                                "name": "attributeName1",
                                "values": [
                                    "赤色",
                                    "100",
                                    "2021-10-15"
                                ]
                            },
                            {
                                "name": "attributeName20",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    }
                },
                "created": "2018-04-28T07:59:49+09:00",
                "updated": "2021-08-31T07:59:49+09:00"
            },
            "review": {
                "count": 5,
                "averageRating": 4.0
            },
            "category": [10000000]
        },
...
        { 
            "item": {
               "manageNumber": "20220524",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            },
            "review": {
                "count": 5,
                "averageRating": 4.0
            },
            "category": ["1"]
        }
    ]
}
クエリパラメータにisInventoryIncludedが指定されている場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search?isInventoryIncluded=true' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 123456,
    "offset": 0,
    "results": [
        {
            "item": {
                "manageNumber": "torimesi",
                "itemType": "NORMAL",
                "itemNumber": "torimesi",
                "title": "水郷どり炊き込みご飯 2合用 鶏めし 鶏飯 お取り寄せグルメ テレビ とりめし 炊き込みご飯の素 釜めし 釜飯 釜飯の素 鶏肉",
                "tagline": "料亭の味をご家庭で・・・上品で繊細、それでいて鶏肉の旨みが凝縮されている逸品です。［鶏肉 炊き込みご飯の素 お取り寄せグルメ テレビ ］",
                "productDescription": {
                    "pc": "explanation for PC",
                    "sp": "explanation for SP"
                },
                "salesDescription": "salesexplanation for PC",
                "images": [
                    {
                        "type": "CABINET",
                        "location": "/01003752/torimesi.jpg",
                        "alt": "itemname"
                    }
                ],
                "whiteBgImage": {
                    "type": "GOLD",
                    "location": "/torimesi.jpg"
                },
                "video": {
                    "type": "HTML",
                    "parameters": {
                        "value": "<script src=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\" type=\"text/javascript\"></script>"
                    }
                },
                "genreId": "201198",
                "tags": [
                    7654321,
                    9000000
                ],
                "hideItem": false,
                "unlimitedInventoryFlag": false,
                "customizationOptions": [
                    {
                        "displayName": "ギフト包装",
                        "inputType": "SINGLE_SELECTION",
                        "required": true,
                        "selections": [
                            {
                                "displayValue": "はい"
                            }
                        ]
                    }
                ],
                "features": {
                    "searchVisibility": "ALWAYS_VISIBLE",
                    "shopContact": true,
                    "review": "SHOP_SETTING",
                    "displayManufacturerContents": false,
                    "displayNormalCartButton": true,
                    "displaySubscriptionCartButton": false,
                    "inventoryDisplay": "DISPLAY_LOW_STOCK",
                    "lowStockThreshold": 1,
                    "socialGiftFlag": false
                },
                "payment": {
                    "taxIncluded": false,
                    "taxRate": "0.1",
                    "cashOnDeliveryFeeIncluded": true
                },
                "pointCampaign": {
                    "applicablePeriod": {
                        "start": "2018-04-28T07:59:49+09:00",
                        "end": "2018-05-28T07:59:49+09:00"
                    },
                    "benefits": {
                        "pointRate": 15
                    },
                    "optimization": {
                        "maxPointRate": 20
                    }
                },
                "itemDisplaySequence": 999999999,
                "layout": {
                    "itemLayoutId": 1,
                    "navigationId": 10,
                    "layoutSequenceId": 20,
                    "smallDescriptionId": 30,
                    "largeDescriptionId": 40,
                    "showcaseId": 50
                },
                "variants": {
                    "sku-mng-number": {
                        "restockOnCancel": false,
                        "normalDeliveryDateId": 1,
                        "backOrderFlag": false,
                        "standardPrice": 1000,
                        "articleNumber": {
                            "value": "0689640032932",
                        },
                          "shipping": {
                              "okihaiSetting": true
                          },
                       "attributes": [
                            {
                                "name": "ブランド名",
                                "values": [
                                    "お米"
                                ]
                            },
                            {
                                "name": "シリーズ名",
                                "values": [
                                    "鶏めし"
                                ]
                            },
                            {
                                "name": "原産国／製造国",
                                "values": [
                                    "日本"
                                ]
                            },
                            {
                                "name": "総個数",
                                "values": [
                                    "1"
                                ]
                            },
                            {
                                "name": "総重量",
                                "values": [
                                    "10"
                                ],
                                "unit": "kg"
                            }
                        ]
                    }
                },
                "created": "2021-07-08T01:05:31+09:00",
                "updated": "2021-07-29T00:24:22+09:00"
            },
            "inventory": {
                "sku-mng-number": {
                    "operationLeadTime": {
                        "normalDeliveryTimeId": 1,
                        "backOrderDeliveryTimeId": 2
                    },
                    "shipFromIds": [
                        3
                    ]
                },
                "created": "2022-07-05T07:29:50.262Z",
                "updated": "2022-07-08T02:18:45.111Z"
            }
        }
    ]
}
商品が存在しない場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 0,
    "offset": 0,
    "results": []
}
商品が削除されて、まだ検索情報に反映されない場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 1,
    "offset": 0,
    "results": [
        {
            "item": {
                "manageNumber": "test-50000"
            }
        }
    ]
}
商品をhit数の上限(100件)以上取得したい場合
クエリパラメータにOFFSETを指定
ソート順を指定して商品を取得したい場合はoffsetを変更しながら複数回リクエストしてください。ただし、offsetは最大10000まで指定できます。

Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search?offset=1000' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 123456,
    "offset": 1000,
    "results": [
        { 
            "item": {
               "manageNumber": "general1",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            }
        },
        { 
            "item": {
               "manageNumber": "general2",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            }
        },
...
       { 
            "item": {
               "manageNumber": "general30",
               "itemType": "NORMAL",
               "title": "bcdsample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            }
        }
    ]
}
クエリパラメータにCURSORMARKを指定
ソート順は気にせず全商品を取得したい場合はcursorMarkを変更しながら複数回リクエストしてください。
終了条件は指定したcursorMark=nextCursorMarkとなることです。


Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search?cursorMark=*' \
--header 'Authorization: ESA xxx'
Response (status: 200 OK)
{
    "numFound": 123456,
    "offset": 1000,
    "results": [
        { 
            "item": {
               "manageNumber": "general1",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            }
        },
        { 
            "item": {
               "manageNumber": "general2",
               "itemType": "NORMAL",
               "title": "202205sample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            }
        },
...
       { 
            "item": {
               "manageNumber": "general30",
               "itemType": "NORMAL",
               "title": "bcdsample",
               "genreId": "563339",
               "hideItem": false,
               "unlimitedInventoryFlag": false,
               "features": {
                   "searchVisibility": "ALWAYS_VISIBLE",
                   "shopContact": true,
                   "review": "SHOP_SETTING",
                   "displayManufacturerContents": false,
                   "displayNormalCartButton": true,
                   "displaySubscriptionCartButton": false,
                   "inventoryDisplay": "HIDDEN_STOCK",
                   "socialGiftFlag": false
               },
               "payment": {
                   "taxIncluded": true,
                   "cashOnDeliveryFeeIncluded": false
               },
               "itemDisplaySequence": 999999999,
               "layout": {
                   "itemLayoutId": 1,
                   "navigationId": 0,
                   "layoutSequenceId": 0,
                   "smallDescriptionId": 0,
                   "largeDescriptionId": 0,
                   "showcaseId": 0
               },
               "variants": {
                   "variant_id_4": {
                       "restockOnCancel": false,
                       "backOrderFlag": false,
                       "articleNumber": {
                           "exemptionReason": 5
                       },
                       "standardPrice": "1000",
                       "shipping": {
                           "postageIncluded": false,
                           "singleItemShipping": 0,
                             "okihaiSetting": true
                       },
                       "hidden": false,
                       "features": {
                           "restockNotification": false,
                           "noshi": false
                        }
                     }
                 },
                "created": "2022-05-25T15:48:51+09:00",
                "updated": "2022-05-27T07:56:29+09:00"
            }
        }
    ],
  "nextCursorMark": "abc"
}
失敗した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/search?itemType=UNKNOWNTAG' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0007",
            "message": "Invalid choice selected for itemType."
        }
    ]
}
