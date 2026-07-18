RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itemapi2_0/itemsbulkget/
サービス: 商品API 2.0（ItemAPI 2.0）

サービス一覧へ戻る / ItemAPI 2.0

RMS WEB SERVICE : items.bulk.get
Overview
この機能を利用すると、商品管理番号を指定し、最大で50件の商品情報を一括で取得することができます。

※定期購入リニューアルにて追加・修正となる項目は背景色を緑に変更しています。
　定期購入リニューアルの概要は こちら をご確認ください。



Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/items/bulk-get
	POST
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/json
Path Parameter
None

HTTP Body
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	manageNumbers	商品管理番号リスト	yes	List<string>	-	1..50	
Response
HTTP Header
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合

No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
L1	L2	L3	L4	L5	L6
1	results	商品情報	yes	List<item>	-	0..50	商品情報リスト
2		manageNumber	商品管理番号	yes	string	32 	1	以下の英数字、記号。
・"a~z"
・"0~9"
・"-", "_"
3		itemNumber	商品番号	no	string	32 	0,1	
4		title	商品名	yes	string	255 	1	
5		tagline	キャッチコピー	no	string	174	0,1	
6		productDescription	商品説明文	no	object	-	0,1	
7			pc	PC用商品説明文	no	string	10240 	0,1	
8			sp	スマートフォン用商品説明文	no	string	10240 	0,1	
9		salesDescription	PC用販売説明文	no	string	10240 	0,1	
10		precautions	医薬品説明文・注意事項	no	object	-	0,1	
11			description	医薬品説明文	no	string	20480 	0,1	
12			agreement	医薬品注意事項	no	string	20480 	0,1	
13		itemType	商品種別	yes	enum	-	1	・NORMAL：通常商品
・PRE_ORDER：予約商品
・BUYING_CLUB：頒布会商品
14		images	商品画像	no	List<images>	-	0..20	商品画像のリスト
15			type	商品画像種別	no	enum	255	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
16			location	商品画像URL	no	string	255	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
17			alt	商品画像名（ALT）	no	string	255	0,1	商品レベルでの画像の代替テキスト。
18		whiteBgImage	白背景画像	no	object	-	0,1	
19			type	白背景画像種別	no	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
20			location	白背景画像URL	no	string	-	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
21		video	動画	no	object	-	0,1	
22			type	動画種別	no	enum	-	1	・HTML：HTML形式
23			parameters	動画パラメータ	no	object	-	1	
24				value	動画のURL	no	string	2048	1	フォーマット：
<script src="(https:)?//stream.cms.rakuten.co.jp/gate/play/[^\"]*" type="text/javascript"></script>
25		genreId	ジャンルID	yes	string	6 	1	6桁の数字：100000 ～ 999999
26		tags	非製品属性タグID	no	List<int>	-	0..32	商品の詳細属性情報。
7桁の数字：5000000～9999999
27		hideItem	倉庫指定	yes	boolean	-	1	・true：倉庫に入れる
・false：販売中
28		unlimitedInventoryFlag	在庫設定なし	yes	boolean	-	1	・true：在庫設定なし※
・false：在庫設定あり

※2016年9月20日以前に登録かつ、その後更新されていない商品のみ。
29		customizationOptions	商品オプション（項目選択肢）	no	List <customizationOptions>	-	0..20	
30			displayName	商品オプション（項目選択肢）項目名	no	string	255 	1	
31			inputType	商品オプション選択肢タイプ	no	enum	-	1	・SINGLE_SELECTION：セレクトボックス
・MULTIPLE_SELECTION：チェックボックス
・FREE_TEXT：フリーテキスト
32			required	商品オプション必須フラグ	no	boolean	-	1	・true：必須
・false：任意
33			selections	Select/Checkbox用選択肢リスト	no	List<selections>	-	0..n	範囲

・inputType=SINGLE_SELECTION：1～100
・inputType=MULTIPLE_SELECTION：1～40
34				displayValue	商品オプション選択肢名	no	string	32	1	
35		releaseDate	予約商品発売日	no	string	-	0,1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、日まで。
36		purchasablePeriod	販売期間指定	no	object	-	0,1	
37			start	販売開始日時	no	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）。
38			end	販売終了日時	no	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）。
39		subscription	定期購入商品設定	no	object	-	0,1	
40			shippingDateFlag	お届け日付指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可
41			shippingIntervalFlag	お届け間隔（曜日）指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可
42		buyingClub	頒布会商品設定	no	object	-	0,1	
43			numberOfDeliveries	お届け回数	no	number	-	1	許容値：2～12
44			displayItems	商品内訳情報の表示	no	boolean	-	1	
45			items	商品内訳情報	no	List<string>	127	0..12	
46			shippingDateFlag	お届け日付指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可
47			shippingIntervalFlag	お届け間隔（曜日）指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可
48		features	その他設定	yes	object	-	1	
49			searchVisibility	サーチ表示	yes	enum	-	1	・ALWAYS_VISIBLE：表示
・ALWAYS_HIDDEN：非表示
50			displayNormalCartButton	注文ボタン	yes	boolean	-	1	・true：表示
・false：非表示
51			displaySubscriptionCartButton	定期購入・頒布会ボタン	yes	boolean	-	1	・true：表示
・false：非表示
52			inventoryDisplay	在庫数表示	yes	enum	-	1	・DISPLAY_ABSOLUTE_STOCK_COUNT：表示
・HIDDEN_STOCK：非表示
・DISPLAY_LOW_STOCK：残り在庫数表示閾値より小さい場合、△を表示する
53			lowStockThreshold	残り在庫数表示閾値	no	number	-	0,1	許容値：1～20
54			shopContact	商品問い合わせボタン	yes	boolean	-	1	・true：表示
・false：非表示
55			review	レビュー本文表示	yes	enum	-	1	・SHOP_SETTING：店舗設定に従う
・VISIBLE：表示
・HIDDEN：非表示
56			displayManufacturerContents	メーカー提供情報表示	yes	boolean	-	1	・true：表示
・false：非表示
57			socialGiftFlag	ソーシャルギフトフラグ	yes	boolean	-	1	・true：対応する
・false：対応しない
58		accessControl	アクセスコントロール	no	object	-	1	
59			accessPassword	闇市パスワード	no	string	32	1	小文字で以下の英数字、記号。
・"a~z"
・"0-9"
・"-", "_"
60		payment	決済情報	yes	object	-	1	
61			taxIncluded	消費税込み	yes	boolean	-	1	・true：税込
・false：税別
62			taxRate	消費税税率	no	string	-	0,1	以下のいずれか
・0：非課税
・0.08：8%
・0.1：10%
・null：店舗設定に従う
63			cashOnDeliveryFeeIncluded	代引料	yes	boolean	-	1	・true：代引料込
・false：代引料別
64		pointCampaign	ポイント変倍情報	no	object	-	0,1	
65			applicablePeriod	ポイント変倍適用期間	no	object	-	1	
66				start	開始日時	no	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）。
67				end	終了日時	no	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）。
"9999-12-31T23:59:59+09:00"が設定されている場合は終了日時が設定されていないポイント変倍情報であることを示す。
68			benefits	ポイント情報	no	object	-	1	
69				pointRate	ポイント変倍率	no	number	-	1	許容値：1～20
70			optimization	運用型ポイント情報	no	object	-	0,1	運用型ポイント変倍サービスを申し込んだ店舗のみ返される。
71				maxPointRate	ポイント上限倍率	no	number	-	1	許容値：5～20
72		itemDisplaySequence	店舗内カテゴリでの表示順位	yes	number	-	1	許容値：1～999999999
73		layout	レイアウト設定	yes	object	-	1	
74			itemLayoutId	商品ページレイアウト	yes	number	-	1	・1：テンプレートA
・2：テンプレートB
・3：テンプレートC
・4：テンプレートD
・5：テンプレートE
・6：テンプレートF
・8：テンプレートG
75			navigationId	ヘッダー・フッター・レフトナビのテンプレートID	yes	number	-	1	
76			layoutSequenceId	表示項目の並び順テンプレートID	yes	number	-	1	
77			smallDescriptionId	共通説明文(小)テンプレートID	yes	number	-	1	
78			largeDescriptionId	共通説明文(大)テンプレートID	yes	number	-	1	
79			showcaseId	目玉商品テンプレートID	yes	number	-	1	
80		variantSelectors	バリエーション項目	no	List<variantSelectors>	-	0..6	商品ページ上の表示はリクエストの順番と同一。
81			key	バリエーション項目キー	no	string	-	1	バリエーション項目名の識別子。
82			displayName	バリエーション項目名	no	string	32 	1	
83			values	バリエーション選択肢リスト	no	List<selectorValues>	-	1..40	
84				displayValue	バリエーション選択肢	no	string	32	1	商品ページ上の表示はリクエストの順番と同一。
85		variants	SKU	yes	object	-	1..400	
86			{variantId}	SKU管理番号	no	string	32	1	以下の英数字、記号。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_"
87				merchantDefinedSkuId	システム連携用SKU番号	no	string	96 	0,1	英数字または日本語の文字列。
88				selectorValues	SKU情報	no	object	-	0..6	
89					{key}	バリエーション項目キー・選択肢	no	string	-	1	variantSelectors.key: variantSelectors.values.displayValue の形式。
90				images	SKU画像	no	List<images>	-	0..1	
91					type	SKU画像タイプ	no	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
92					location	SKU画像パス	no	string	255 	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
93					alt	SKU画像名（ALT）	no	string	255 	0,1	
94				restockOnCancel	在庫戻しフラグ	no	boolean	-	1	・true：在庫戻しする
・false：在庫戻ししない
95				backOrderFlag	在庫切れ時の注文受付	no	boolean	-	1	・true：注文を受け付ける
・false：注文を受け付けない
96				normalDeliveryDateId	在庫あり時納期管理番号	no	number	-	0,1	
97				backOrderDeliveryDateId	在庫切れ時納期管理番号	no	number	-	0,1	
98				orderQuantityLimit	注文受付数	no	number	-	0,1	許容値：0～400

・0：非表示（最大個数1個）
・n （1～400）：最大購入数を設定
・null： 自由入力
99				referencePrice	表示価格情報	no	object	-	0,1	
100					displayType	表示価格種別	no	enum	-	1	・REFERENCE_PRICE：選択した表示価格文言
・SHOP_SETTING：店舗設定に従う
・OPEN_PRICE：メーカー希望小売価格 オープン価格
101					type	表示価格文言	no	number	-	0,1	・1：当店通常価格
・2：メーカー希望小売価格
・4：商品価格ナビのデータ参照
102					value	表示価格	no	string	-	0,1	許容値：1～999999999
103				features	その他設定	no	object	-	0,1	
104					restockNotification	再入荷お知らせボタン	no	boolean	-	1	・true：表示
・false：非表示
105					noshi	のし対応	no	boolean	-	1	・true：対応する
・false：対応しない
106				hidden	SKU倉庫設定	no	boolean	-	1	・true：倉庫
・false：販売中
107				standardPrice	販売価格	no	string	-	0,1	許容値：0～999999999
108				subscriptionPrice	定期購入販売価格設定・頒布会販売価格設定	no	object	-	0,1	
109					basePrice	定期購入販売価格・頒布会販売価格	no	string	-	0,1	許容値：1～999999999
110					individualPrices	個別価格	no	object	-	0,1	
111						firstPrice	初回価格	no	string	-	0,1	許容値：1～999999999
112				articleNumberForSet	セット商品用カタログID	no	List<string>	30	0..20	通常商品かつカタログIDなしの理由に「セット商品」を指定した商品のみが対象。
セットの構成であるSKUのカタログID。
113				articleNumber	カタログID情報	no	object	-	0,1	
114					value	カタログID	no	string	30 	0,1	商品の標準製品コード。
115					exemptionReason	カタログIDなしの理由	no	number	-	0,1	・1：セット商品
・2：サービス商品
・3：店舗オリジナル商品
・4：項目選択肢在庫商品
・5：該当製品コードなし
・6：頒布会商品
116				shipping	送料情報	yes	object	-	0,1	
117					fee	個別送料	no	string	-	0,1	許容値：0～999999999
118					postageIncluded	送料無料フラグ	no	boolean	-	1	・true：送料無料
・false：送料別
119					shopAreaSoryoPatternId	地域別個別送料管理番号	no	number	-	0,1	許容値：1～20
120					shippingMethodGroup	配送方法セット管理番号	no	string	40 	0,1	配送方法セット管理番号に自動選択対象以外の設定がある場合のみ、この項目を返却します。
*配送方法セット管理番号は、以下より確認してください。
ShopAPI > shop.deliverySetInfo.getの下記項目から取得可能。
4.2.6. Level 4: deliverySetInfo - deliverySetId
121					postageSegment	送料区分情報	no	object	-	0,1	
122						local	送料区分1（ローカル）	no	number	-	0,1	ローカルの送料区分番号。
123						overseas	送料区分2（海外）	no	number	-	0,1	海外の送料区分番号。
124					overseasDeliveryId	海外配送管理番号	no	number	-	0,1	許容値：1～5
125					singleItemShipping	単品配送設定	no	number	-	1	・0：設定なし
・1：産地直送の商品
・2：メーカー直送の商品
・3： ケース売りの商品
・4：長尺・異形の商品
・5：出荷地が異なる商品
・6：温度帯が異なる商品
126					okihaiSetting	置き配設定	yes	boolean	-	1	・true : 受け付ける
・false : 受け付けない
127				specs	属性情報自由入力行	no	List<object>	-	0..5	商品ページ上の「商品仕様」に追記できる任意項目。
128					label	属性情報自由入力行（項目）	no	string	40 	1	
129					value	属性情報自由入力行（値）	no	string	140 	1	
130		created	登録日時	yes	string	-	1	商品の登録日時。
フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、秒まで。
131		updated	更新日時	yes	string	-	1	商品の更新日時。
フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、秒まで。
失敗した場合
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
L1	L2	L3
1	errors	エラー	yes	List<error>	1..n	エラーのリスト
2		code	コード	yes	string	1	メッセージコードの一覧はこちら
3		message	メッセージ	yes	string	1
4		metadata	メタデータ	no	object	1	エラーの補足情報
5		propertyPath	属性パス	no	string	1	発生したエラーの位置
Sample
成功した場合
全フィールドの例
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/items/bulk-get' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "manageNumbers": [
        "mng1234",
        "mng5678"
    ]
}'
Response in JSON format (Status: 200 OK)
{
   "results":[
      {
         "manageNumber":"mng1234",
         "itemNumber":"2100011223431",
         "title":"日本語",
         "tagline":"キャッチコピー",
         "productDescription":{
            "pc":"PC用商品説明文",
            "sp":"スマートフォン用商品説明文"
         },
         "salesDescription":"PC販売説明文",
         "precautions":{
            "description":"医薬品説明文",
            "agreement":"医薬品注意事項"
         },
         "itemType":"NORMAL",
         "images":[
            {
               "type":"CABINET",
               "location":"/myfolder-1/tv01.jpg",
               "alt":"l2_17-Inventory-Test"
            }
         ],
         "whiteBgImage":{
            "type":"CABINET",
            "location":"/harryporter.jpg"
         },
         "video":{
            "type":"HTML",
            "parameters":{
               "value":"<scriptsrc=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\"type=\"text/javascript\"></script>"
            }
         },
         "tags":[
            5000001,
            5000002
         ],
         "hideItem":false,
         "unlimitedInventoryFlag":false,
         "customizationOptions":[
            {
               "displayName":"ギフト目的",
               "inputType":"SINGLE_SELECTION",
               "required":false,
               "selections":{
                  "displayValue":"のし必要の方は必ずお選び下さい。"
               }
            }
         ],
         "releaseDate":"2021-07-14",
         "purchasablePeriod":{
            "start":"2021-07-11T15:00:00+09:00",
            "end":"2021-07-31T14:59:59+09:00"
         },
         "subscription":{
            "shippingDateFlag":true,
            "shippingIntervalFlag":false
         },
        "buyingClub": {
            "numberOfDeliveries": 2,
            "displayItems": true,
            "items": ["1回目 商品", "2回目 商品"],
            "shippingDateFlag": true,
            "shippingIntervalFlag": false
        },
         "features":{
            "searchVisibility":"ALWAYS_VISIBLE",
            "displayNormalCartButton":false,
            "displaySubscriptionCartButton":false,
            "inventoryDisplay":"DISPLAY_ABSOLUTE_STOCK_COUNT",
            "lowStockThreshold":5,
            "shopContact":false,
            "review":"SHOP_SETTING",
            "displayManufacturerContents":false,
            "socialGiftFlag": false
         },
         "payment":{
            "taxIncluded":false,
            "taxRate":0.08,
            "cashOnDeliveryFeeIncluded":false
         },
         "pointCampaign":{
            "applicablePeriod":{
               "start":"2021-10-13T04:07:08+09:00",
               "end":"2021-11-13T04:07:08+09:00"
            },
            "benefits":{
               "pointRate":6
            },
            "optimization":{
               "maxPointRate":6
            }
         },
         "itemDisplaySequence":999999999,
         "layout":{
            "itemLayoutId":1,
            "navigationId":0,
            "layoutSequenceId":0,
            "smallDescriptionId":0,
            "largeDescriptionId":0,
            "showcaseId":0
         },
         "variantSelectors":[
            {
               "key":"size-key",
               "displayName":"サイズ",
               "values":[
                  {
                     "displayValue":"Lサイズ"
                  }
               ]
            }
         ],
         "variants":{
            "pinot-noir":{
               "merchantDefinedSkuId":"112233",
               "selectorValues":{
                  "size-key":"Lサイズ"
               },
               "images":[
                  {
                     "type":"CABINET",
                     "location":"/myfolder-1/tv01.jpg",
                     "alt":"l2_17-Inventory-Test"
                  }
               ],
               "restockOnCancel":false,
               "backOrderFlag":false,
               "normalDeliveryDateId":1,
               "backOrderDeliveryDateId":2,
               "orderQuantityLimit":100,
               "referencePrice":{
                  "displayType":"REFERENCE_PRICE",
                  "type":1,
                  "value":1000
               },
               "features":{
                  "restockNotification":true,
                  "noshi":true
               },
               "hidden":false,
               "standardPrice":1000,
               "articleNumberForSet":[
                  "45000000000",
                  "45000000001"
               ],
               "articleNumber":{
                  "value":"0689640032932",
                  "exemptionReason":"1"
               },
               "shipping":{
                  "fee":1000,
                  "postageIncluded":false,
                  "shopAreaSoryoPatternId":1,
                  "shippingMethodGroup":2,
                  "postageSegment":{
                     "local":1,
                     "overseas":1
                  },
                  "overseasDeliveryId":1,
                  "singleItemShipping":1,
                  "okihaiSetting": true
               },
               "specs":{
                  "label":"スペック情報ラベル",
                  "value":"スペック情報内容"
               }
            }
         },
         "created":"2022-01-01T19:00:00+09:00",
         "updated":"2022-02-01T19:30:00+09:00",
         "genreId":"555555"
      },
      {
         "manageNumber":"mng5678",
         "itemNumber":"2100011223432",
         "title":"日本語",
         "tagline":"キャッチコピー",
         "productDescription":{
            "pc":"PC用商品説明文",
            "sp":"スマートフォン用商品説明文"
         },
         "salesDescription":"PC販売説明文",
         "precautions":{
            "description":"医薬品説明文",
            "agreement":"医薬品注意事項"
         },
         "itemType":"NORMAL",
         "images":[
            {
               "type":"CABINET",
               "location":"/myfolder-1/tv01.jpg",
               "alt":"l2_17-Inventory-Test"
            }
         ],
         "whiteBgImage":{
            "type":"CABINET",
            "location":"/harryporter.jpg"
         },
         "video":{
            "type":"HTML",
            "parameters":{
               "value":"<scriptsrc=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\"type=\"text/javascript\"></script>"
            }
         },
         "tags":[
            5000001,
            5000002
         ],
         "hideItem":false,
         "unlimitedInventoryFlag":false,
         "customizationOptions":[
            {
               "displayName":"ギフト目的",
               "inputType":"SINGLE_SELECTION",
               "required":false,
               "selections":{
                  "displayValue":"のし必要の方は必ずお選び下さい。"
               }
            }
         ],
         "releaseDate":"2021-07-14",
         "purchasablePeriod":{
            "start":"2021-07-11T15:00:00+09:00",
            "end":"2021-07-31T14:59:59+09:00"
         },
         "subscription":{
            "shippingDateFlag":true,
            "shippingIntervalFlag":false
         },
        "buyingClub": {
            "numberOfDeliveries": 2,
            "displayItems": true,
            "items": ["1回目 商品", "2回目 商品"],
            "shippingDateFlag": true,
            "shippingIntervalFlag": false
        },
         "features":{
            "searchVisibility":"ALWAYS_VISIBLE",
            "displayNormalCartButton":false,
            "displaySubscriptionCartButton":false,
            "inventoryDisplay":"DISPLAY_ABSOLUTE_STOCK_COUNT",
            "lowStockThreshold":5,
            "shopContact":false,
            "review":"SHOP_SETTING",
            "displayManufacturerContents":false,
            "socialGiftFlag": false
         },
         "payment":{
            "taxIncluded":false,
            "taxRate":0.08,
            "cashOnDeliveryFeeIncluded":false
         },
         "pointCampaign":{
            "applicablePeriod":{
               "start":"2021-10-13T04:07:08+09:00",
               "end":"2021-11-13T04:07:08+09:00"
            },
            "benefits":{
               "pointRate":6
            },
            "optimization":{
               "maxPointRate":6
            }
         },
         "itemDisplaySequence":999999999,
         "layout":{
            "itemLayoutId":1,
            "navigationId":0,
            "layoutSequenceId":0,
            "smallDescriptionId":0,
            "largeDescriptionId":0,
            "showcaseId":0
         },
         "variantSelectors":[
            {
               "key":"size-key",
               "displayName":"サイズ",
               "values":[
                  {
                     "displayValue":"Lサイズ"
                  }
               ]
            }
         ],
         "variants":{
            "pinot-noir":{
               "merchantDefinedSkuId":"112233",
               "selectorValues":{
                  "size-key":"Lサイズ"
               },
               "images":[
                  {
                     "type":"CABINET",
                     "location":"/myfolder-1/tv01.jpg",
                     "alt":"l2_17-Inventory-Test"
                  }
               ],
               "restockOnCancel":false,
               "backOrderFlag":false,
               "normalDeliveryDateId":1,
               "backOrderDeliveryDateId":2,
               "orderQuantityLimit":100,
               "referencePrice":{
                  "displayType":"REFERENCE_PRICE",
                  "type":1,
                  "value":1000
               },
               "v":{
                  "restockNotification":true,
                  "noshi":true
               },
               "hidden":false,
               "standardPrice":1000,
               "articleNumberForSet":[
                  "45000000000",
                  "45000000001"
               ],
               "articleNumber":{
                  "value":"0689640032932",
                  "exemptionReason":"1"
               },
               "shipping":{
                  "fee":1000,
                  "postageIncluded":false,
                  "shopAreaSoryoPatternId":1,
                  "shippingMethodGroup":2,
                  "postageSegment":{
                     "local":1,
                     "overseas":1
                  },
                  "overseasDeliveryId":1,
                  "singleItemShipping":1,
                  "okihaiSetting": true
               },
               "specs":{
                  "label":"スペック情報ラベル",
                  "value":"スペック情報内容"
               }
            }
         },
         "created":"2022-01-03T19:00:00+09:00",
         "updated":"2022-02-04T19:30:00+09:00",
         "genreId":"555555"
      }
   ]
}
指定した商品管理番号の商品が全て存在しない場合
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/items/bulk-get' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "manageNumbers": [
        "mng1235",
        "mng5679"
    ]
}'
Response in JSON format (Status: 200 OK)
{
   "results":[]
}
指定した商品管理番号の商品が一部存在しない場合
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/items/bulk-get' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "manageNumbers": [
        "mng1234",
        "mng5679"
    ]
}'
Response in JSON format (Status: 200 OK)
{
   "results":[
      {
         "manageNumber":"mng1234",
         "itemNumber":"2100011223431",
         "title":"日本語",
         "tagline":"キャッチコピー",
         "productDescription":{
            "pc":"PC用商品説明文",
            "sp":"スマートフォン用商品説明文"
         },
         "salesDescription":"PC販売説明文",
         "precautions":{
            "description":"医薬品説明文",
            "agreement":"医薬品注意事項"
         },
         "itemType":"NORMAL",
         "images":[
            {
               "type":"CABINET",
               "location":"/myfolder-1/tv01.jpg",
               "alt":"l2_17-Inventory-Test"
            }
         ],
         "whiteBgImage":{
            "type":"CABINET",
            "location":"/harryporter.jpg"
         },
         "video":{
            "type":"HTML",
            "parameters":{
               "value":"<scriptsrc=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\"type=\"text/javascript\"></script>"
            }
         },
         "tags":[
            5000001,
            5000002
         ],
         "hideItem":false,
         "unlimitedInventoryFlag":false,
         "customizationOptions":[
            {
               "displayName":"ギフト目的",
               "inputType":"SINGLE_SELECTION",
               "required":false,
               "selections":{
                  "displayValue":"のし必要の方は必ずお選び下さい。"
               }
            }
         ],
         "releaseDate":"2021-07-14",
         "purchasablePeriod":{
            "start":"2021-07-11T15:00:00+09:00",
            "end":"2021-07-31T14:59:59+09:00"
         },
         "subscription":{
            "shippingDateFlag":true,
            "shippingIntervalFlag":false
         },
         "features":{
            "searchVisibility":"ALWAYS_VISIBLE",
            "displayNormalCartButton":false,
            "displaySubscriptionCartButton":false,
            "inventoryDisplay":"DISPLAY_ABSOLUTE_STOCK_COUNT",
            "lowStockThreshold":5,
            "shopContact":false,
            "review":"SHOP_SETTING",
            "displayManufacturerContents":false,
            "socialGiftFlag": false
         },
         "payment":{
            "taxIncluded":false,
            "taxRate":0.08,
            "cashOnDeliveryFeeIncluded":false
         },
         "pointCampaign":{
            "applicablePeriod":{
               "start":"2021-10-13T04:07:08+09:00",
               "end":"2021-11-13T04:07:08+09:00"
            },
            "benefits":{
               "pointRate":6
            },
            "optimization":{
               "maxPointRate":6
            }
         },
         "itemDisplaySequence":999999999,
         "layout":{
            "itemLayoutId":1,
            "navigationId":0,
            "layoutSequenceId":0,
            "smallDescriptionId":0,
            "largeDescriptionId":0,
            "showcaseId":0
         },
         "variantSelectors":[
            {
               "key":"size-key",
               "displayName":"サイズ",
               "values":[
                  {
                     "displayValue":"Lサイズ"
                  }
               ]
            }
         ],
         "variants":{
            "pinot-noir":{
               "merchantDefinedSkuId":"112233",
               "selectorValues":{
                  "size-key":"Lサイズ"
               },
               "images":[
                  {
                     "type":"CABINET",
                     "location":"/myfolder-1/tv01.jpg",
                     "alt":"l2_17-Inventory-Test"
                  }
               ],
               "restockOnCancel":false,
               "backOrderFlag":false,
               "normalDeliveryDateId":1,
               "backOrderDeliveryDateId":2,
               "orderQuantityLimit":100,
               "referencePrice":{
                  "displayType":"REFERENCE_PRICE",
                  "type":1,
                  "value":1000
               },
               "features":{
                  "restockNotification":true,
                  "noshi":true
               },
               "hidden":false,
               "standardPrice":1000,
               "articleNumberForSet":[
                  "45000000000",
                  "45000000001"
               ],
               "articleNumber":{
                  "value":"0689640032932",
                  "exemptionReason":"1"
               },
               "shipping":{
                  "fee":1000,
                  "postageIncluded":false,
                  "shopAreaSoryoPatternId":1,
                  "shippingMethodGroup":2,
                  "postageSegment":{
                     "local":1,
                     "overseas":1
                  },
                  "overseasDeliveryId":1,
                  "singleItemShipping":1,
                   "okihaiSetting": true
               },
               "specs":{
                  "label":"スペック情報ラベル",
                  "value":"スペック情報内容"
               }
            }
         },
         "created":"2022-01-01T19:00:00+09:00",
         "updated":"2022-02-01T19:30:00+09:00",
         "genreId":"555555"
      }
   ]
}
失敗した場合
指定した商品管理番号が最大の長さを超えた場合
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/items/bulk-get' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "manageNumbers": [
        "12345678901234567890123456789012345678901",
        "mng1234",
        "mng5678"
    ]
}'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0004",
           "message": "Max length of manageNumber must be within 32 bytes.",
           "metadata": {
               "propertyPath": "manageNumbers[0]"
           }
        }
    ]
}
指定した商品管理番号が重複した場合
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/items/bulk-get' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "manageNumbers": [
        "mng1234",
        "mng1234",
        "mng5678"
    ]
}'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE1106",
           "message": "There are multiple occurrences of same manageNumber : mng1234",
           "metadata": {
               "propertyPath": "manageNumbers"
           }
        }
    ]
}
