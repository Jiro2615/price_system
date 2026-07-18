RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itemapi2_0/itemsupsert/
サービス: 商品API 2.0（ItemAPI 2.0）

サービス一覧へ戻る / ItemAPI 2.0

RMS WEB SERVICE : items.upsert
Overview
この機能を利用すると、商品管理番号を指定し、商品情報の登録・全項目の更新をすることができます。
部分更新の機能ではないため、リクエストに含まれない項目は値が削除されるか、デフォルト値で更新されます。

※okihaiSettingやsocialGiftFlagについては、フィールドがリクエストに含まれていない場合、その値は削除されず、デフォルト値に更新されません。
※定期購入リニューアルにて追加・修正となる項目は背景色を緑に変更しています。
定期購入リニューアルの概要はこちらをご確認ください。


Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/{manageNumber}	PUT
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/json
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Multiplicity	Description
1	manageNumber	商品管理番号	yes	string	1	1件のみ指定可能

以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_" 
大文字は小文字に自動変換。
HTTP Body
※1：上位のフィールドを使用する場合、このフィールドは必須となります。

No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
L1	L2	L3	L4	L5
1	itemNumber	商品番号	no	string	32	0,1	
2	title	商品名	yes	string	255	1	
3	tagline	キャッチコピー	no	string	174	0,1	
4	productDescription	商品説明文	no	object	-	0,1	
5		pc	PC用商品説明文	no	string	10240	0,1	
6		sp	スマートフォン用商品説明文	no	string	10240	0,1	
7	salesDescription	PC用販売説明文	no	string	10240	0,1	
8	precautions	医薬品説明文・注意事項	no	object	-	0,1	
9		description	医薬品説明文	no	string	20480	0,1	
10		agreement	医薬品注意事項	no	string	20480	0,1	
11	itemType	商品種別	yes	enum	-	1	・NORMAL：通常商品
・PRE_ORDER：予約商品
・BUYING_CLUB：頒布会商品

商品登録後、頒布会商品への変更不可。逆の場合も同様。
通常商品（定期購入設定ありの場合）から予約商品への変更は不可。
定期購入商品、もしくは頒布会商品の場合、displaySubscriptionCartButtonは"true"を指定。
12	images	商品画像	no	List<images>	-	0..20	商品画像のリスト。
13		type	商品画像種別	yes※1	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
14		location	商品画像URL	yes※1	string	255	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
例: "/myfolder-1/tv01.jpg"

拡張子がjpg, jpeg, png, gifの画像パスのみ使用可能。
画像パスに使用できる文字は以下の通り。
0-9、a-z、A-Z、- (U+002D)、. (U+002E)、/ (U+002F)、: (U+003A)、_ (U+005F)
15		alt	商品画像名(ALT)	no	string	255	0,1	商品レベルでの画像の代替テキスト。
"<", ">"とhtmlタグ以外のすべての文字列が利用可能。
16	whiteBgImage	白背景画像	no	object	-	0,1	
17		type	白背景画像種別	yes※1	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
18		location	白背景画像URL	yes※1	string	-	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
例: "/myfolder-1/tv01.jpg"

拡張子がjpg, jpeg, png, gifの画像パスのみ使用可能。
画像パスに使用できる文字は以下の通り。
0-9、a-z、A-Z、- (U+002D)、. (U+002E)、/ (U+002F)、: (U+003A)、_ (U+005F)
19	video	動画	no	object	-	0,1	
20		type	動画種別	yes※1	enum	-	1	・HTML：HTML形式
21		parameters	動画パラメータ	yes※1	object	-	1	
22			value	動画のURL	yes※1	string	2048	1	フォーマット：
<script src="(https:)?//stream.cms.rakuten.co.jp/gate/play/[^\"]*" type="text/javascript"></script>
23	genreId	ジャンルID	yes	string	6	1	6桁の数字：100000 ～ 999999
24	tags	非製品属性タグID	no	List<int>	-	0..32	商品の詳細属性情報。
7桁の数字：5000000～9999999

製品属性についてはattributesを参照。
25	hideItem	倉庫指定	no	boolean	-	1	倉庫に入れるかどうかを指定する

・true：倉庫に入れる
・false：販売中（デフォルト）
26	unlimitedInventoryFlag	在庫設定なし	no	boolean	-	1	・false：在庫設定あり（デフォルト）
27	customizationOptions	商品オプション（項目選択肢）	no	List<customizationOptions>	-	0..20	
28		displayName	商品オプション（項目選択肢）項目名	yes※1	string	255	1	
29		inputType	商品オプション選択肢タイプ	yes※1	enum	-	1	・SINGLE_SELECTION：セレクトボックス
・MULTIPLE_SELECTION：チェックボックス
・FREE_TEXT：フリーテキスト
30		required	商品オプション必須フラグ	no	boolean	-	1	・true：必須
・false：任意（デフォルト）
31		selections	Select/Checkbox用選択肢リスト	条件付き必須	List<selections>	-	0..n	inputTypeに「SINGLE_SELECTION」か「MULTIPLE_SELECTION」を設定した場合、必須。

「SINGLE_SELECTION」の場合、最大100。
「MULTIPLE_SELECTION」の場合、最大40。
32			displayValue	商品オプション選択肢名	yes※1	string	32	1	":", "<", ">"とhtmlタグ以外のすべての文字列が利用可能。
33	releaseDate	予約商品発売日	条件付き必須	string	-	0,1	商品種別を「PRE_ORDER」に設定した場合、必須。
フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、日まで。
頒布会商品の場合は設定不可。
34	purchasablePeriod	販売期間指定	no	object	-	0,1	
35		start	販売開始日時	yes※1	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、分まで。
00秒以外が指定された場合、自動的に00秒に変換。
36		end	販売終了日時	yes※1	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、分まで。
59秒以外が指定された場合、自動的に59秒に変換。
37	subscription	定期購入商品設定	条件付き必須	object	-	0,1	通常商品かつ、displaySubscriptionCartButtonを「true」に設定した場合、以下のいずれかの設定が必須。
・subscription.shippingDateFlag
・subscription.shippingIntervalFlag
38		shippingDateFlag	お届け日付指定フラグ	条件付き必須	boolean	-	1	・true：指定可能
・false：指定不可（デフォルト）
39		shippingIntervalFlag	お届け間隔（曜日）指定フラグ	条件付き必須	boolean	-	1	・true：指定可能
・false：指定不可（デフォルト）
40	buyingClub					頒布会商品設定	条件付き必須	object	-	0,1	商品種別を「BUYING_CLUB」に設定した場合、必須。
41		numberOfDeliveries				お届け回数	yes※1	number	-	1	許容値：2～12
42		displayItems				商品内訳情報の表示
（商品ページへの表示）	no	boolean	-	1	・true：表示（デフォルト）
・false：非表示
43		items				商品内訳情報	条件付き必須	List<string>	127	0..12	商品内訳情報の表示を「true」に設定した場合、必須。
44		shippingDateFlag				お届け日付指定フラグ	no	boolean	-	1	・true：指定可能
・false：指定不可（デフォルト）
45		shippingIntervalFlag				お届け間隔（曜日）指定フラグ	no	boolean	-	1	・true：指定可能（デフォルト）
・false：指定不可
46	features	その他設定	no	object	-	1	
47		searchVisibility	サーチ表示	no	enum	-	1	・ALWAYS_VISIBLE：表示（デフォルト）
・ALWAYS_HIDDEN：非表示
48		displayNormalCartButton	注文ボタン	no	boolean	-	1	・true：表示（デフォルト）
・false：非表示
頒布会商品の場合、trueは設定不可。
49		displaySubscriptionCartButton	定期購入・頒布会ボタン	no	boolean	-	1	・true：表示
・false：非表示
未指定の場合、itemTypeに準じた値が設定されます。
50		inventoryDisplay	在庫数表示	no	enum	-	1	・DISPLAY_ABSOLUTE_STOCK_COUNT：表示
・HIDDEN_STOCK：非表示（デフォルト）
・DISPLAY_LOW_STOCK：残り在庫数表示閾値より小さい場合、△を表示する
51		lowStockThreshold	残り在庫数表示閾値	条件付き必須	number	-	0,1	inventoryDisplayに「DISPLAY_LOW_STOCK」を設定した場合、必須。
許容値：1～20
52		shopContact	商品問い合わせボタン	no	boolean	-	1	・true：表示（デフォルト）
・false：非表示
53		review	レビュー本文表示	no	enum	-	1	・SHOP_SETTING：店舗設定に従う（デフォルト）
・VISIBLE：表示
・HIDDEN：非表示
54		displayManufacturerContents	メーカー提供情報表示	no	boolean	-	1	・true：表示
・false：非表示（デフォルト）
55		socialGiftFlag	ソーシャルギフトフラグ	no	boolean	-	1	すべての SKU に「送料無料」が設定されている場合、通常の商品に対してソーシャルギフトを利用できます。

・true：対応する 
・false：対応しない（デフォルト）

※itemTypeが「NORMAL：通常商品」のみ設定可能。ただし定期購入ではソーシャルギフトは適用されません。
※ソーシャルギフト商品の販売を開始するには、申込が必要です。
※socialGiftFlagについては、フィールドがリクエストに含まれていない場合、その値は削除されず、デフォルト値に更新されません。
56	accessControl	アクセスコントロール	no	object	-	1	
57		accessPassword	闇市パスワード	no	string	32	1	小文字で以下の英数字、記号のみ使用可能。

・"a~z"
・"0-9"
・"-", "_" 
58	payment	決済情報	no	object	-	1	
59		taxIncluded	消費税込み	no	boolean	-	1	・true：税込（デフォルト）
・false：税別
60		taxRate	消費税税率	no	string	-	0,1	以下のいずれか

・0：非課税
・0.08：8%
・0.1：10%
・null：店舗設定に従う
61		cashOnDeliveryFeeIncluded	代引料	no	boolean	-	1	・true：代引料込
・false：代引料別（デフォルト）
62	pointCampaign	ポイント変倍情報	no	object	-	0,1	
63		applicablePeriod	ポイント変倍適用期間	yes※1	object	-	1	
64			start	開始日時	yes※1	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、時まで。
00分00秒以外が指定された場合、自動的に00分00秒に変換。

許容値：現在時刻の最短2時間後から最長60日後まで
　例
　　現在時刻：08/01　16時03分
　　開始日時：（最短）08/01　19時00分　～　（最長）09/30　16時00分
65			end	終了日時	yes※1	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時（JST）、時まで。
59分59秒以外が指定された場合、自動的に59分59秒に変換。
終了日時を設定しないポイント変倍情報にする場合、"9999-12-31T23:59:59+09:00"を指定する。
適用期間開始後、終了日時が設定されていないポイント変倍情報は、一度だけ終了日時を期限がある状態に変更が可能。

許容値
・終了日を最初から登録する場合： 開始日時から最短59分59秒以降から最長59日23時間59分59秒後まで

　例
　　開始日時：08/01　19時00分
　　終了日時：（最短）08/01　19時59分　～　（最長）09/30　18時59分

・終了日時を設定しないポイント変倍情報を適用期間開始後に変更する場合： 現在時刻から最短2時間59分59秒以降から最長60日1時間59分59秒後まで

　例
　　現在時刻：08/01　19時00分
　　終了日時：（最短）08/01　21時59分　～　（最長）09/30　20時59分
66		benefits	ポイント情報	yes※1	object	-	1	
67			pointRate	ポイント変倍率	yes※1	number	-	1	許容値：1～20
68		optimization	運用型ポイント情報	no	object	-	0,1	頒布会商品の場合は設定不可。
69			maxPointRate	ポイント上限倍率	yes※1	number	-	1	許容値：5～20
70	itemDisplaySequence	店舗内カテゴリでの表示順位	no	number	-	1	許容値：1～999999999
デフォルト値：999999999
71	layout	レイアウト設定	no	object	-	1	
72		itemLayoutId	商品ページレイアウト	no	number	-	1	・1：テンプレートA（デフォルト）
・2：テンプレートB
・3：テンプレートC
・4：テンプレートD
・5：テンプレートE
・6：テンプレートF
・8：テンプレートG
73		navigationId	ヘッダー・フッター・レフトナビのテンプレートID	no	number	-	1	IDの値はShopAPIの shop.shopLayoutCommon.get の下記項目から取得可能。
　4.2.6. Level 4: shopLayoutCommon - layoutCommonId

デフォルト値：0
74		layoutSequenceId	表示項目の並び順テンプレートID	no	number	-	1	IDの値はShopAPIの shop.layoutItemMap.get の下記項目から取得可能。
　4.2.6. Level 4: layoutItemMap - itemMapId

デフォルト値：0
75		smallDescriptionId	共通説明文(小)テンプレートID	no	number	-	1	IDの値はShopAPIの shop.layoutTextSmall.get の下記項目から取得可能。
　4.2.6. Level 4: layoutTextSmall - textSmallId

デフォルト値：0
76		largeDescriptionId	共通説明文(大)テンプレートID	no	number	-	1	IDの値はShopAPIの shop.layoutTextLarge.get の下記項目から取得可能。
　4.2.6. Level 4: layoutTextLarge - textLargeId

デフォルト値：0
77		showcaseId	目玉商品テンプレートID	no	number	-	1	IDの値はShopAPIの shop.layoutLossLeader.get の下記項目から取得可能。
　4.2.6. Level 4: layoutLossLeader - lossLeaderId

デフォルト値：0
78	variantSelectors	バリエーション項目	no	List<variantSelectors>	-	0..6	商品ページ上の表示はリクエストの順番と同一。
79		key	バリエーション項目キー	yes※1	string	-	1	variantSelectors内での重複不可。
variants.{variantId}.selectorValues.{key}で使用する。
80		displayName	バリエーション項目名	yes※1	string	32	1	
81		values	バリエーション選択肢リスト	yes※1	List<selectorValues>	-	1..40	
82			displayValue	バリエーション選択肢	yes※1	string	32	1	商品ページ上の表示はリクエストの順番と同一。
variants.{variantId}.selectorValues.{key}のvalueで使用する。
83	variants	SKU	yes	object	-	1..400	
84		{variantId}	SKU管理番号	yes	string	32	1	同一商品管理番号内での重複不可。
以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0-9"
・"-", "_"
大文字・小文字は、異なる文字として扱う。
85			merchantDefinedSkuId	システム連携用SKU番号	no	string	96	0,1	商品番号と同様に利用可能な任意項目。
全角文字入力可。
86			selectorValues	SKU情報	条件付き必須	object	-	0..6	バリエーション項目を設定した場合、必須。
87				{key}	バリエーション項目キー・選択肢	yes※1	string	-	1	variantSelectors.key: variantSelectors.values.displayValue の形式。
88			images	SKU画像	no	List<images>	-	0..1	
89				type	SKU画像タイプ	yes※1	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
90				location	SKU画像パス	yes※1	string	255	1	画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
例: "/myfolder-1/tv01.jpg"

拡張子がjpg, jpeg, png, gifの画像パスのみ使用可能。
画像パスに使用できる文字は以下の通り。
0-9、a-z、A-Z、- (U+002D)、. (U+002E)、/ (U+002F)、: (U+003A)、_ (U+005F)
91				alt	SKU画像名（ALT）	no	string	255	0,1	"<", ">"とhtmlタグ以外のすべての文字列が利用可能。
92			restockOnCancel	在庫戻しフラグ	no	boolean	-	1	・true：在庫戻しする
・false：在庫戻ししない（デフォルト）
93			backOrderFlag	在庫切れ時の注文受付	no	boolean	-	1	・true：注文を受け付ける
・false：注文を受け付けない（デフォルト）
94			normalDeliveryDateId	在庫あり時納期管理番号	no	number	-	0,1	IDの値はShopAPIの shop.delvdateMaster.get の下記項目から取得可能。
　4.2.6. Level 4: delvdateMaseter - delvdateNumber
95			backOrderDeliveryDateId	在庫切れ時納期管理番号	条件付き必須	number	-	0,1	在庫切れ時の注文受付を「true」に設定した場合、必須。
IDの値はShopAPIの shop.delvdateMaster.get の下記項目から取得可能。
　4.2.6. Level 4: delvdateMaseter - delvdateNumber
96			orderQuantityLimit	注文受付数	no	number	-	0,1	許容値：0～400

・0：非表示（最大個数1個）
・n (1～400)：最大購入数を設定
・null： 自由入力
97			referencePrice	表示価格情報	no	object	-	0,1	
98				displayType	表示価格種別	yes※1	enum	-	1	・REFERENCE_PRICE：選択した表示価格文言
・SHOP_SETTING：店舗設定に従う
・OPEN_PRICE：メーカー希望小売価格 オープン価格
99				type	表示価格文言	条件付き必須	number	-	0,1	表示価格種別をREFERENCE_PRICEに設定した場合は必須。

・1：当店通常価格
・2：メーカー希望小売価格
・4：商品価格ナビのデータ参照
100				value	表示価格	条件付き必須	string	-	0,1	表示価格種別に「REFERENCE_PRICE」を設定し、かつ表示価格文言に「4：商品価格ナビのデータ参照」以外の値を設定した場合、必須。

許容値：1～999999999
101			features	その他設定	no	object	-	0,1	
102				restockNotification	再入荷お知らせボタン	no	boolean	-	1	・true：表示
・false：非表示（デフォルト）
103				noshi	のし対応	no	boolean	-	1	・true：対応する
・false：対応しない（デフォルト）
頒布会商品の場合、trueは設定不可
104			hidden	SKU倉庫設定	no	boolean	-	1	このSKUを倉庫に入れるかどうかを指定する。

・true：倉庫
・false：販売中（デフォルト）。
105			standardPrice	販売価格	条件付き必須	string	-	0,1	通常商品・予約商品の場合、必須。
頒布会商品の場合、設定不可。

許容値：0～999999999
106			subscriptionPrice	定期購入販売価格設定・頒布会販売価格設定	条件付き必須	object	-	0,1	
107				basePrice	定期購入販売価格・頒布会販売価格	yes※1	string	-	0,1	通常商品かつ、定期購入ボタンを「true」に設定した場合、条件付き必須。
頒布会商品の場合、必須。

許容値：1～999999999
108				individualPrices	個別価格	no	object	-	0,1	
109					firstPrice	初回価格	no	string	-	0,1	許容値：1～999999999
110			articleNumberForSet	セット商品用カタログID	no	List<string>	30	0..20	通常商品かつカタログIDなしの理由に「セット商品」を指定した商品のみが対象。
セットの構成であるSKUのカタログID。
111			articleNumber	カタログID情報	yes	object	-	0,1	以下のいずれかの設定が必須。

・articleNumber.value
・articleNumber.exceptionReason
112				value	カタログID	条件付き必須	string	30	0,1	商品の標準製品コード。
英数字が利用可能。
113				exemptionReason	カタログIDなしの理由	条件付き必須	number	-	0,1	・1：セット商品
・2：サービス商品
・3：店舗オリジナル商品
・4：項目選択肢在庫商品
・5：該当製品コードなし
・6：頒布会商品

必須商品属性の入力猶予期間終了後、「4：項目選択肢在庫商品」は指定できなくなります。
通常商品、予約商品の場合、「6：頒布会商品」は設定不可。
114			shipping	送料情報	no	object	-	0,1	
115				fee	個別送料	no	string	-	0,1	許容値：0～999999999
116				postageIncluded	送料無料フラグ	no	boolean	-	1	・true：送料無料
・false：送料別（デフォルト）
117				shopAreaSoryoPatternId	地域別個別送料管理番号	no	number	-	0,1	許容値：1～20

IDの値はShopAPIの shop.shopAreaSoryo.get の下記項目から取得可能。
　4.2.7. Level 5: shopAreaSoryoPattern - patternId
118				shippingMethodGroup	配送方法セット管理番号	no	string	40	0,1	配送方法セット管理番号に自動選択対象の設定がある場合、未指定時には自動選択が適用されます。

IDの値はShopAPIの shop.deliverySetInfo.get の下記項目から取得可能。
　4.2.6. Level 4: deliverySetInfo - deliverySetId
119				postageSegment	送料区分情報	no	object	-	0,1	
120					local	送料区分1(ローカル)	no	number	-	0,1	ローカルの送料区分番号。

IDの値はShopAPIの shop.soryoKbn.get の下記項目から取得可能。
　4.2.6. Level 4: soryoKbn - id
121					overseas	送料区分2(海外)	no	number	-	0,1	海外の送料区分番号。

IDの値はShopAPIの shop.soryoKbn.get の下記項目から取得可能。
　4.2.6. Level 4: soryoKbn - id
122				overseasDeliveryId	海外配送管理番号	no	number	-	0,1	許容値：1～5
123				singleItemShipping	単品配送設定	no	number	-	1	・0：設定なし（デフォルト）
・1：産地直送の商品
・2：メーカー直送の商品
・3：ケース売りの商品
・4：長尺・異形の商品
・5：出荷地が異なる商品
・6：温度帯が異なる商品
124				okihaiSetting	置き配設定	no	boolean	-	1	SKU毎に置き配のON/OFFの設定ができる

・true : 受け付ける (デフォルト）
・false : 受け付けない

※すべての商品種別(itemType)で設定可能です。
※置き配を申し込んでいない場合、この設定内容は無効です。
※okihaiSettingについては、フィールドがリクエストに含まれていない場合、その値は削除されず、デフォルト値に更新されません。
125			specs	属性情報自由入力行	no	List<object>	-	0..5	商品ページ上の「商品仕様」に追記できる任意項目。
126				label	属性情報自由入力行（項目）	yes※1	string	40	1	
127				value	属性情報自由入力行（値）	yes※1	string	140	1	
128			attributes	属性情報	yes	List<object>	-	0..100	商品ページ上に「商品仕様」として表示される項目。
129				name	属性情報名	yes※1	string	-	1	
130				values	属性情報（実値）	yes※1	List<string>	-	1..n	フォーマットはNavigationAPI 2.0 の genres.attributes.get
あるいは genres.attributes.dictionaryValues.get の下記項目の値に準ずる。
　4.2.6. Level 3: attributes - dataType
131				unit	単位	no	string	-	0,1	属性情報の単位。
Response
HTTP Header
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	manageNumber	商品管理番号	no	string	-	0,1	新規登録の場合のみ返される。


失敗した場合
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
L1	L2	L3
1	errors	エラー	yes	List<error>	-	1..n	エラーのリスト。
2		code	コード	yes	string	-	1	メッセージコードの一覧はこちら。
3		message	メッセージ	yes	string	-	1
4		metadata	メタデータ	no	object	-	0,1	エラーの補足情報。
5			propertyPath	属性パス	no	string	-	0,1	発生したエラーの位置。
Sample
成功した場合
全フィールドを含む例
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/mng123' \
--header 'Authorization: ESA xxx'
--data-raw '{
    "itemNumber":"2100011223431",
    "title": "日本語",
    "tagline": "キャッチコピー",
    "productDescription": {
      "pc": "PC用商品説明文",
      "sp": "スマートフォン用商品説明文"
    },
    "salesDescription": "PC販売説明文",
    "precautions": {
      "description": "医薬品説明文",
      "agreement": "医薬品注意事項"
    },
    "images": [
      {
        "type": "CABINET",
        "location": "/myfolder-1/tv01.jpg",
        "alt": "l2_17-Inventory-Test"
      }
    ],
    "whiteBgImage": {
        "type": "CABINET",
        "location": "/harryporter.jpg"
    },
    "video": {
            "type": "HTML",
            "parameters": {
                "value": "<script src=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\" type=\"text/javascript\"></script>"
            }
     },
    "tags": [
      5000001,
      5000002
    ],
    "unlimitedInventoryFlag": false,
    "customizationOptions": [
        {
            "displayName": "ギフト目的",
            "inputType": "SINGLE_SELECTION",
            "required":false,
            "selections": [
                {
                    "displayValue": "のし必要の方は必ずお選び下さい。"
                }
            ]
        }
    ],
    "releaseDate":"2021-07-14",
    "purchasablePeriod":{
        "start": "2021-07-11T15:00:00+09:00",
        "end": "2021-07-31T14:59:59+09:00"
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
    "itemDisplaySequence": 999999999,
    "layout": {
        "itemLayoutId": 1,
        "navigationId": 0,
        "layoutSequenceId": 0,
        "smallDescriptionId": 0,
        "largeDescriptionId": 0,
        "showcaseId": 0
    },
    "variantSelectors": [
        {
            "key":"size-key",
            "displayName":"サイズ",
            "values": [
                {
                    "displayValue":"L サイズ"
                }
            ]
        }
    ],
    "variants":{
      "pinot-noir":{
        "merchantDefinedSkuId":"112233",
        "selectorValues":{
          "size-key":"L サイズ"
        },
        "images":[{
          "type":"CABINET",
          "location":"/myfolder-1/tv01.jpg",
          "alt":"l2_17-Inventory-Test"
        }],
        "restockOnCancel":false,
        "backOrderFlag":false,
        "normalDeliveryDateId":1,
        "backOrderDeliveryDateId":2,
        "orderQuantityLimit":100,
        "referencePrice":{
          "displayType":"REFERENCE_PRICE ",
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
        "specs": [
            {
                "label":"スペック情報ラベル",
                "value":"スペック情報内容"
            }
        ],
        "attributes": [
            {
                "name":"attribute name",
                "values":["赤色","100"]
            }
        ]
      }
    },
    "itemType": "NORMAL",
    "genreId": "555555"
}'
Response in JSON format (Status: 201 Created)
{
    "manageNumber": "mng123"
}
Response in JSON format (Status: 204 No Content)
SKU在庫商品と通常在庫商品の例
SKU在庫商品
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/11829' \
--header 'Authorization: ESA xxx'
--data-raw '{
    "itemType": "NORMAL",
    "itemNumber": "11829",
    "title": "い・ろ・は・す ラベルレス(560ml*24本/48本入)【いろはす(I LOHAS)】",
    "tagline": "いろはす(I LOHAS) / い・ろ・は・す PET",
    "productDescription": {
        "pc": "explanation for PC",
        "sp": "explanation for SP"
    },
    "salesDescription": "salesexplanation for PC",
    "images": [
        {
            "type": "CABINET",
            "location": "/01003752/ilohas.jpg",
            "alt": "ilohas"
        }
    ],
    "whiteBgImage": {
        "type": "GOLD",
        "location": "/ilohas-white-bg.jpg"
    },
    "video": {
        "type": "HTML",
        "parameters": {
            "value": "<script src=\"//stream.cms.rakuten.co.jp/gate/play/?w=320&h=286&mid=1101692986&vid=5792214557001\" type=\"text/javascript\"></script>"
        }
    },
    "genreId": "206878",
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
    "purchasablePeriod": {
        "start": "2021-07-11T15:00:00+09:00",
        "end": "2021-07-31T14:59:59+09:00"
    },
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
            "key": "num-key",
            "displayName": "本数",
            "values": [
                {
                    "displayValue": "24本"
                },
                {
                    "displayValue": "48本"
                }
            ]
        }
    ],
    "variants": {
        "sku-1": {
            "merchantDefinedSkuId": "システム連携SKU商品番号",
            "selectorValues": {
                "num-key": "24本"
            },
            "images": [
                {
                    "type": "CABINET",
                    "location": "/01003752/ilohas_1.jpg",
                    "alt": "sku-image"
                }
            ],
            "restockOnCancel": true,
            "backOrderFlag": false,
            "normalDeliveryDateId": 1,
            "backOrderDeliveryDateId": 2,
            "articleNumber": {
                "value": "4902102091862"
            "hidden": true,
            "orderQuantityLimit": 3,
            "features": {
                "restockNotification": true,
                "noshi": true
            },
            "standardPrice": "2894",
            "referencePrice": {
                "displayType": "REFERENCE_PRICE",
                "type": 1,
                "value": "2894"
            },
            "shipping": {
                "postageIncluded": true,
                "shippingMethodGroup": "10",
                "singleItemShipping": 5,
                "okihaiSetting": true
            },
            "specs": [
                {
                    "label": "Country of origin",
                    "value": "Japan"
                }
            ],
            "attributes": [
                {
                    "name": "単位内容量",
                    "values": [
                        "560"
                    ],
                    "unit": "ml"
                }
            ]
        },
        "sku-2": {
            "selectorValues": {
                "num-key": "48本"
            },
           "articleNumber": {
                "value": "4902780029294"
           },
           "standardPrice": "6,220",
            "restockOnCancel": false,
            "backOrderFlag": false,
            "attributes": [
                {
                    "name": "単位内容量",
                    "values": [
                        "560"
                    ],
                    "unit": "ml"
                }
            ]
        }
    }
}'
Response in JSON format (Status: 201 Created)
{
    "manageNumber": "11829"
}
Response in JSON format (Status: 204 No Content)
通常在庫商品
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/torimesi' \
--header 'Authorization: ESA xxx'
--data-raw '{
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
        "lowStockThreshold": 1
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
    }
}'
Response in JSON format (Status: 201 Created)
{
    "manageNumber": "torimesi"
}
Response in JSON format (Status: 204 No Content)
商品種別ごとの例
通常商品（定期購入設定なし）
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/torimesi' \
--header 'Authorization: ESA xxx'
--data-raw '{
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
    "purchasablePeriod": {
        "start": "2021-07-11T15:00:00+09:00",
        "end": "2021-07-31T14:59:59+09:00"
    },
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
            },
            "hidden": true,
            "orderQuantityLimit": 3,
            "features": {
                "restockNotification": true,
                "noshi": true
            },
            "standardPrice": "810",
            "referencePrice": {
                "displayType": "REFERENCE_PRICE",
                "type": 1,
                "value": "15000"
            },
            "shipping": {
                "fee": "1000",
                "postageIncluded": false,
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
                    "label": "Country of origin",
                    "value": "Japan"
                }
            ],
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
        },
        "sku-2": {
            "selectorValues": {
                "color-key": "青色",
                "size-key": "Mサイズ"
            },
            "restockOnCancel": false,
            "backOrderFlag": false,
            "standardPrice": "810",
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
    }
}'
Response in JSON format (Status: 201 Created)
{
    "manageNumber": "torimesi"
}
Response in JSON format (Status: 204 No Content)
通常商品（定期購入設定あり）
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/mng123' \
--header 'Authorization: ESA xxx'
--data '{
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
    "purchasablePeriod": {
        "start": "2021-07-11T15:00:00+09:00",
        "end": "2021-07-31T14:59:59+09:00"
    },
    "subscription": {
        "shippingDateFlag": true,
        "shippingIntervalFlag": true
    },
    "features": {
        "searchVisibility": "ALWAYS_VISIBLE",
        "shopContact": true,
        "review": "SHOP_SETTING",
        "displayManufacturerContents": false,
        "displayNormalCartButton": true,
        "displaySubscriptionCartButton": true,
        "inventoryDisplay": "HIDDEN_STOCK",
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
                "value": "4902780029294"
            },
            "hidden": true,
            "orderQuantityLimit": 3,
            "features": {
                "restockNotification": true,
                "noshi": true
            },
            "standardPrice": "810",
            "subscriptionPrice": {
                "basePrice": "710",
                "individualPrices": {
                    "firstPrice": "700"
                }
            },
            "referencePrice": {
                "displayType": "REFERENCE_PRICE",
                "type": 1,
                "value": "15000"
            },
            "shipping": {
                "fee": "1000",
                "postageIncluded": false,
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
                    "label": "Country of origin",
                    "value": "Japan"
                }
            ],
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
        },
        "sku-2": {
            "selectorValues": {
                "color-key": "青色",
                "size-key": "Mサイズ"
            },
            "restockOnCancel": false,
            "backOrderFlag": false,
            "standardPrice": "810",
            "subscriptionPrice": {
                "basePrice": "710",
                "individualPrices": {
                    "firstPrice": "700"
                }
            },
            "articleNumber":{
              "value":"0689640032932"
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
    }
}'
Response in JSON format (Status: 201 Created)
{
    "manageNumber": "mng123"
}
Response in JSON format (Status: 204 No Content)
予約商品
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/mng123' \
--header 'Authorization: ESA xxx'
--data-raw '{
    "itemType": "PRE_ORDER",
    "itemNumber": "itemnumber",
    "title": "予約商品の商品名",
    "tagline": "pc and sp catchcopy",
    "productDescription": {
        "pc": "explanation for PC",
        "sp": "explanation for SP"
    },
    "salesDescription": "salesexplanation for PC",
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
    "releaseDate":"2021-07-14",
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
    "purchasablePeriod": {
        "start": "2021-07-11T15:00:00+09:00",
        "end": "2021-07-31T14:59:59+09:00"
    },
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
                "カラー": "青色",
                "サイズ": "Sサイズ"
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
                    "label": "Country of origin",
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
                "exemptionReason": 1
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
    }
}'
Response in JSON format (Status: 201 Created)
{
    "manageNumber": "mng123"
}
Response in JSON format (Status: 204 No Content)
頒布会商品
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/mng123' \
--header 'Authorization: ESA xxx'
--data '{
    "itemType": "BUYING_CLUB",
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
    "purchasablePeriod": {
        "start": "2021-07-11T15:00:00+09:00",
        "end": "2021-07-31T14:59:59+09:00"
    },
    "buyingClub": {
        "numberOfDeliveries": 2,
        "displayItems": true,
        "items": ["1回目 商品", "2回目 商品"],
        "shippingDateFlag": true,
        "shippingIntervalFlag": false
    },
    "features": {
        "searchVisibility": "ALWAYS_VISIBLE",
        "shopContact": true,
        "review": "SHOP_SETTING",
        "displayManufacturerContents": false,
        "displayNormalCartButton": false,
        "displaySubscriptionCartButton": true,
        "inventoryDisplay": "HIDDEN_STOCK",
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
            "restockOnCancel": false,
            "backOrderFlag": false,
            "articleNumber": {
                "value": "4902780029294"
            },
            "hidden": false,
            "orderQuantityLimit": 3,
            "features": {
                "restockNotification": false,
                "noshi": false
            },
            "subscriptionPrice": {
                "basePrice": "710",
                "individualPrices": {
                    "firstPrice": "700"
                }
            },
            "referencePrice": {
                "displayType": "REFERENCE_PRICE",
                "type": 1,
                "value": "15000"
            },
            "shipping": {
                "fee": "1000",
                "postageIncluded": false,
                "shippingMethodGroup": "10",
                "postageSegment": {
                    "local": 1,
                    "overseas": 2
                },
                "singleItemShipping": 5,
                "okihaiSetting": true
            },
            "specs": [
                {
                    "label": "Country of origin",
                    "value": "Japan"
                }
            ],
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
        },
        "sku-2": {
            "selectorValues": {
                "color-key": "青色",
                "size-key": "Mサイズ"
            },
            "restockOnCancel": false,
            "backOrderFlag": false,
            "subscriptionPrice": {
                "basePrice": "710",
                "individualPrices": {
                    "firstPrice": "700"
                }
            },
            "articleNumber":{
              "value":"0689640032932"
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
    }
}'
Response in JSON format (Status: 201 Created)
{
    "manageNumber": "mng123"
}
Response in JSON format (Status: 204 No Content)
SKU管理番号を変更せずバリエーション項目を追加したい場合
SKU管理番号を変更せず商品を更新する場合はバリエーション項目キーが同一である必要があります。SKU管理番号を変更せずに選択肢名の変更や選択肢の追加、削除はできません。
SKU管理番号を変更せずバリエーション項目を追加したい場合は、一度バリエーション項目キーを追加し、一時的なSKU管理番号を付与したのちに元のSKU管理番号を設定する必要があります。
以下は"カタチ"というバリエーション項目キーを既存のSKUに追加したい場合の例です。

変更前
variantSelectors

バリエーション項目キー	バリエーション選択肢1	バリエーション選択肢2	バリエーション選択肢3
色	黒	白	
サイズ	S	M	L

variants

SKU管理番号	バリエーション項目キー1の選択肢	バリエーション項目キー2の選択肢
SKU0001	黒	M
SKU0002	黒	L
SKU0003	白	S
SKU0004	白	M
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/6650' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 Success)
{
    "manageNumber": "6650",
    "itemType": "NORMAL",
    "title": "アイテム",
    "genreId": "555555",
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
    "variantSelectors": [
        {
            "key": "色",
            "displayName": "色(表示)",
            "values": [
                {
                    "displayValue": "黒"
                },
                {
                    "displayValue": "白"
                }
            ]
        },
        {
            "key": "サイズ",
            "displayName": "サイズ(表示)",
            "values": [
                {
                    "displayValue": "S"
                },
                {
                    "displayValue": "M"
                },
                {
                    "displayValue": "L"
                }
            ]
        }
    ],
    "variants": {
        "SKU0004": {
            "selectorValues": {
                "色": "白",
                "サイズ": "M"
            },
            "restockOnCancel": false,
            "backOrderFlag": false,
            "articleNumber": {
                "value": "4902505375347"
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
        },
        "SKU0003": {
            "selectorValues": {
                "色": "白",
                "サイズ": "S"
            },
            "restockOnCancel": false,
            "backOrderFlag": false,
            "articleNumber": {
                "value": "4902505375347"
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
        },
        "SKU0002": {
            "selectorValues": {
                "色": "黒",
                "サイズ": "L"
            },
            "restockOnCancel": false,
            "backOrderFlag": false,
            "articleNumber": {
                "value": "4902505375347"
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
        },
        "SKU0001": {
            "selectorValues": {
                "色": "黒",
                "サイズ": "M"
            },
            "restockOnCancel": false,
            "backOrderFlag": false,
            "articleNumber": {
                "value": "4902505375347"
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
    "created": "2022-08-01T16:12:50+09:00",
    "updated": "2022-08-01T16:12:50+09:00"
}
1回目の変更
バリエーション項目キーをvariantSelectorsに追加し、variantsにも対応するキー・選択肢を追加します。
SKU管理番号は一時的に以前のSKU管理番号とは別のものを設定してください。

variantSelectors

バリエーション項目キー	バリエーション選択肢1	バリエーション選択肢2	バリエーション選択肢3
色	黒	白	
サイズ	S	M	L
カタチ	○	△	□

variants

SKU管理番号	バリエーション項目キー1の選択肢	バリエーション項目キー2の選択肢	バリエーション項目キー3の選択肢
SKU0005	黒	M	○
SKU0006	黒	L	○
SKU0007	白	S	△
SKU0008	白	M	□
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/6650' \
--header 'Authorization: ESA xxx'
--data-raw '{
    "title": "アイテム",
    "genreId": "555555",
    "itemType": "NORMAL",
    "variantSelectors": [
        {
            "key": "色",
            "displayName": "色(表示)",
            "values": [
                {
                    "displayValue": "黒"
                },
                {
                    "displayValue": "白"
                }
            ]
        },
        {
            "key": "サイズ",
            "displayName": "サイズ(表示)",
            "values": [
                {
                    "displayValue": "S"
                },
                {
                    "displayValue": "M"
                },
                {
                    "displayValue": "L"
                }
            ]
        },
        {
            "key": "カタチ",
            "displayName": "カタチ(表示)",
            "values": [
                {
                    "displayValue": "○"
                },
                {
                    "displayValue": "△"
                },
                {
                    "displayValue": "□"
                }
            ]
        }
    ],
    "variants": {
        "SKU0005": {
            "selectorValues": {
                "色": "黒",
                "サイズ": "M",
                "カタチ": "○"
            },
            "articleNumber": {
                "value": "4902505375347"
            },
            "standardPrice": 1000
        },
        "SKU0006": {
            "selectorValues": {
                "色": "黒",
                "サイズ": "L",
                "カタチ": "○"
            },
            "articleNumber": {
                "value": "4902505375347"
            },
            "standardPrice": 1000
        },
        "SKU0007": {
            "selectorValues": {
                "色": "白",
                "サイズ": "S",
                "カタチ": "△"
            },
            "articleNumber": {
                "value": "4902505375347"
            },
            "standardPrice": 1000
        },
        "SKU0008": {
            "selectorValues": {
                "色": "白",
                "サイズ": "M",
                "カタチ": "□"
            },
            "articleNumber": {
                "value": "4902505375347"
            },
            "standardPrice": 1000
        }
    }
}'
Response in JSON format (Status: 204 No Content)
2回目の変更
SKU管理番号を以前のSKU管理番号に戻します。

variantSelectors

バリエーション項目キー	バリエーション選択肢1	バリエーション選択肢2	バリエーション選択肢3
色	黒	白	
サイズ	S	M	L
カタチ	○	△	□

variants

SKU管理番号	バリエーション項目キー1の選択肢	バリエーション項目キー2の選択肢	バリエーション項目キー3の選択肢
SKU0001	黒	M	○
SKU0002	黒	L	○
SKU0003	白	S	△
SKU0004	白	M	□
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/6650' \
--header 'Authorization: ESA xxx'
--data-raw '{
    "title": "アイテム",
    "genreId": "555555",
    "itemType": "NORMAL",
    "variantSelectors": [
        {
            "key": "色",
            "displayName": "色(表示)",
            "values": [
                {
                    "displayValue": "黒"
                },
                {
                    "displayValue": "白"
                }
            ]
        },
        {
            "key": "サイズ",
            "displayName": "サイズ(表示)",
            "values": [
                {
                    "displayValue": "S"
                },
                {
                    "displayValue": "M"
                },
                {
                    "displayValue": "L"
                }
            ]
        },
        {
            "key": "カタチ",
            "displayName": "カタチ(表示)",
            "values": [
                {
                    "displayValue": "○"
                },
                {
                    "displayValue": "△"
                },
                {
                    "displayValue": "□"
                }
            ]
        }
    ],
    "variants": {
        "SKU0001": {
            "selectorValues": {
                "色": "黒",
                "サイズ": "M",
                "カタチ": "○"
            },
            "articleNumber": {
                "value": "4902505375347"
            },
            "standardPrice": 1000
        },
        "SKU0002": {
            "selectorValues": {
                "色": "黒",
                "サイズ": "L",
                "カタチ": "○"
            },
            "articleNumber": {
                "value": "4902505375347"
            },
            "standardPrice": 1000
        },
        "SKU0003": {
            "selectorValues": {
                "色": "白",
                "サイズ": "S",
                "カタチ": "△"
            },
            "articleNumber": {
                "value": "4902505375347"
            },
            "standardPrice": 1000
        },
        "SKU0004": {
            "selectorValues": {
                "色": "白",
                "サイズ": "M",
                "カタチ": "□"
            },
            "articleNumber": {
                "value": "4902505375347"
            },
            "standardPrice": 1000
        }
    }
}'
Response in JSON format (Status: 204 No Content)
失敗した場合
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/items/manage-numbers/mng123' \
--header 'Authorization: ESA xxx'
--data-raw '{
    "itemType": "NORMAL",
    "itemNumber": "itemnumber",
    "title": "通常商品の商品名",
    "tagline": "pc and sp catchcopy",
    "productDescription": {
        "pc": "explanation for PC",
        "sp": "explanation for SP"
    },
    "salesDescription": "salesexplanation for PC",
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
    "genreId": "111111",
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
        "inventoryDisplay": "HIDDEN_STOCK",
        "lowStockThreshold": 1
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
    "variants": {
        "normal-inventory": {
            "restockOnCancel": false,
            "normalDeliveryDateId":1,
            "backOrderFlag": false
        }
    }
}'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0146",
            "message": "Failed to get the genre info.",
            "metadata": {
                "propertyPath": "genreId"
            }
        }
    ]
}
