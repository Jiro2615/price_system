RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/purchaseitemapi/getorderitem/
サービス: 購入商品API（PurchaseItemAPI）

サービス一覧へ戻る / PurchaseItemAPI

RMS WEB SERVICE : getOrderItem
Overview
この機能を利用すると、「購入された商品に関連する情報の取得」を行うことができます。こちらは同期処理となります。

SKUプロジェクトにて追加・修正となる項目は背景色を緑に変更しています。

Endpoint
Endpoint
https://api.rms.rakuten.co.jp/es/2.0/purchaseItem/getOrderItem/
Request
Request Method
Method
POST
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
Level 1: base
No	Logical Name	Parameter Name	Required	Type	Max Byte	Default	Description	Sample
1	注文番号リスト	orderNumberList	yes	List <String>	4096	-	最大 100 件まで指定可能

過去 730 日(2年)以内の注文を取得可能	["123456-20220518-00006701","123456-20220518-0000670258"]
Response
HTTP Status
Code	Status	Description
200	OK	リクエストが成功した。
400	Bad Request	リクエストが不正である。
404	Not Found	Request-URI に一致するものを見つけられなかった。
405	Method Not Allowed	許可されていないメソッドを使用しようとした。
500	Internal Server Error	サーバ内部にエラーが発生した。
503	Service Unavailable	サービスが一時的に過負荷やメンテナンスで使用不可能である。
Response Header
Key	Value
Content-Type	application/json;charset=utf-8
Response Parameter
Level 1: base
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	メッセージモデルリスト	MessageModelList	yes	List <MessageModel>	-	-		
2	受注情報モデルリスト	OrderModelList	no	List <OrderModel>	-	-		
Level 2: MessageModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	メッセージ種別	messageType	yes	String	16	-	以下のいずれか

・INFO
・ERROR
・WARNING	INFO
2	メッセージコード	messageCode	yes	String	128	-	メッセージコードの一覧はこちら	MESSAGE_CODE_SAMPLE
3	メッセージ	message	yes	String	1024	-	メッセージサンプル
4	注文番号	orderNumber	no	String	382	-		123456-20220518-00006701
Level 2: OrderModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	注文番号	orderNumber	yes	String	382	-		123456-20220518-00006701
2	ステータス	orderProgress	yes	Number	10	-	以下のいずれか

100: 注文確認待ち
200: 楽天処理中
300: 発送待ち
400: 変更確定待ち
500: 発送済
600: 支払手続き中
700: 支払手続き済
800: キャンセル確定待ち
900: キャンセル確定	200
3	サブステータスID	subStatusId	no	Number	10	-		1101
4	注文日時	orderDatetime	yes	Datetime	32	-	YYYY-MM-DDThh:mm:ss+09:00	2022-05-02T20:03:43+0900
5	注文確認日時	shopOrderCfmDatetime	no	Datetime	32	-	YYYY-MM-DDThh:mm:ss+09:00	2022-05-02T20:03:43+0900
6	注文確定日時	orderFixDatetime	no	Datetime	32	-	YYYY-MM-DDThh:mm:ss+09:00	2022-05-02T20:36:07+0900
7	発送指示日時	shippingInstDatetime	no	Datetime	32	-	YYYY-MM-DDThh:mm:ss+09:00	2022-05-02T20:36:07+0900
8	発送完了報告日時	shippingCmplRptDatetime	no	Datetime	32	-	YYYY-MM-DDThh:mm:ss+09:00	2022-05-02T00:05:06+0900
9	お届け日指定	deliveryDate	no	Date	10	-	YYYY-MM-DD	2022-05-29
10	お届け時間帯	shippingTerm	no	Number	10	-	以下のいずれか

0: なし
1: 午前
2: 午後
9: その他

h1h2: h1時-h2時 (h1は7～24まで任意で数値指定可能。h2は07～24まで任意で数値指定可能)	708
2324
11	ギフト配送希望フラグ	giftCheckFlag	yes	Number	1	-	以下のいずれか

0: ギフト注文ではない
1: ギフト注文である	1
12	ソーシャルギフト注文フラグ	socialGiftFlag	yes	Number	1	-	以下のいずれか

0: ソーシャルギフト注文ではない
1: ソーシャルギフト注文である	1
13	離島フラグ	isolatedIslandFlag	yes	Number	1	-	以下のいずれか

0: 送付先に離島が含まれていない
1: 送付先に離島が含まれている	1
14	注文種別	orderType	yes	Number	10	-	以下のいずれか

1: 通常購入
4: 定期購入
5: 頒布会
6: 予約商品	1
15	申込番号	reserveNumber	no	String	382	-	定期購入、予約、頒布会の申込番号	123456-20211027-00003701-r
16	申込お届け回数	reserveDeliveryCount	no	Number	5	-	予約は常に１、定期購入、頒布会は確定した回数	6
17	商品合計金額	goodsPrice	yes	Number	10	-9999	商品金額 + ラッピング料	1000
18	送料合計	postagePrice	yes	Number	10	-9999	対象受注に紐付く送料（送付先毎の送料の合計）

※未確定の場合、-9999になります。	100
19	代引料合計	deliveryPrice	yes	Number	10	-9999	※代引手数料が掛からない決済手段の場合は、0になります。
※未確定の場合、-9999になります。	50
20	決済手数料合計	paymentCharge	yes	Number	10	-9999	※決済手数料が掛からない決済手段の場合は、0になります。
※未確定の場合、-9999になります。
※決済手数料については、こちらをご確認ください。	250
21	決済手続税率	paymentChargeTaxRate	yes	Number	-	-		0.1
22	合計金額	totalPrice	yes	Number	10	-9999	商品金額 + 送料 + ラッピング料
※未確定の場合、-9999になります。	1230
23	請求金額	requestPrice	yes	Number	10	-9999	商品金額 + 送料 + ラッピング料 + 決済手数料 + 注文者負担金 - クーポン利用総額 - ポイント利用額
※未確定の場合、-9999になります。	1000
24	クーポン利用総額	couponAllTotalPrice	yes	Number	10	-	クーポンの総額	100
25	店舗発行クーポン利用額	couponShopPrice	yes	Number	10	-	クーポン原資コードが「1」のクーポンの総額

※未確定の場合、-9999になります。	70
26	楽天発行クーポン利用額	couponOtherPrice	yes	Number	10	-	クーポン原資コードが「1」以外のクーポンの総額

※未確定の場合、-9999になります。	30
27	注文者負担金合計	additionalFeeOccurAmountToUser	yes	Number	10	-9999	※注文者が支払う負担金の合計
負担金がない場合は、0になります。
※負担金はRMS画面やマニュアル上では、後払い利用手数料と表記されています。
※未確定の場合、-9999になります。	250
28	店舗負担金合計	additionalFeeOccurAmountToShop	yes	Number	10	-9999	※店舗様が支払う負担金の合計
負担金がない場合は、0になります。
※負担金はRMS画面やマニュアル上では、後払い利用手数料と表記されています。
※未確定の場合、-9999になります。	250
29	あす楽希望フラグ	asurakuFlag	yes	Number	1	-	以下のいずれか

0: あす楽希望無し注文
1: あす楽希望有り注文		0
30	医薬品受注フラグ	drugFlag	yes	Number	1	-	以下のいずれか

0: 医薬品を含む注文ではない
1: 医薬品を含む注文である	0
31	楽天スーパーDEAL商品受注フラグ	dealFlag	yes	Number	1	-	以下のいずれか

0: 楽天スーパーDEAL商品を含む受注ではない
1: 楽天スーパーDEAL商品を含む受注である	1
32	注文者モデル	OrdererModel	yes	OrdererModel	-	-		
33	支払方法モデル	SettlementModel	no	SettlementModel	-	-		
34	配送方法モデル	DeliveryModel	yes	DeliveryModel	-	-		
35	ポイントモデル	PointModel	no	PointModel	-	-		
36	ラッピングモデル1	WrappingModel1	no	WrappingModel	-	-		
37	ラッピングモデル2	WrappingModel2	no	WrappingModel	-	-		
38	送付先モデルリスト	PackageModelList	yes	List <PackageModel>	-	-		
39	税情報モデルリスト	TaxSummaryModelList	no	List <TaxSummaryModel>	-	-		
40	最強翌日配送フラグ	deliveryCertPrgFlag	yes	Number	1	-	以下のいずれか
0: 最強翌日配送対象外注文
1: 最強翌日配送対象注文
※購入時に遅延補償対象となった注文です。補償対象外となった場合でもフラグは変更されません。
※2024年11月20日（水）のサービス名称変更（「最強配送」から「最強翌日配送」に変更）に伴いLogical Nameのみ変更。	1
41	当日出荷フラグ	oneDayOperationFlag	yes	Number	1	-	以下のいずれか
0: 1営業日以内出荷ではない注文
1: 1営業日以内出荷の注文
※購入時に最短お届け可能日が指定された注文、またはソーシャルギフト注文において受取情報入力時に最短お届け可能日が指定された注文です。	1
Level 3: OrdererModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	都道府県	prefecture	yes	String	382	-		東京都
Level 3: SettlementModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	支払方法コード	settlementMethodCode	yes	Number	6	-	以下のいずれか

1: クレジットカード
2: 代金引換
4: ショッピングクレジット／ローン
5: オートローン
6: リース
7: 請求書払い
8: ポイント
9: 銀行振込
12: Apple Pay
13: セブンイレブン（前払）
14: ローソン、郵便局ATM等（前払）、または、ファミリーマート、ローソン等（前払）※
16: Alipay
17: PayPal
21: 後払い決済
27: Alipay（支付宝）

※2026年1月22日（木）の支払方法名変更に伴い、新旧名称どちらの注文もコードは14となります。	1
Level 3: DeliveryModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	配送方法	deliveryName	yes	String	382	-	店舗設定で設定した配送方法。	宅配便
2	配送区分	deliveryClass	no	Number	10	-	0: 選択なし
1: 普通
2: 冷蔵
3: 冷凍
4: その他１
5: その他２
6: その他３
7: その他４
8: その他５	0
Level 3: PointModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	ポイント利用額	usedPoint	yes	Number	10	-	支払いに利用されたポイント数	100
Level 3: WrappingModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	ラッピングタイトル	title	yes	Number	5	-	以下のいずれか

1: 包装紙
2: リボン	1
2	ラッピング名	name	yes	String	396	-	ラッピングの名称	ラッピング名
3	料金	price	no	Number	10	-	ラッピングの金額	100
4	税込別	includeTaxFlag	yes	Number	1	0	以下のいずれか

0: 税別
1: 税込	1
5	ラッピング税率	taxRate	yes	Number	-	-	ラッピングに対する税率	0.1
6	ラッピング税額	taxPrice	yes	Number	10	-	※税込/税抜に関わらず、値が設定されます。	10
Level 3: PackageModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	送付先ID	basketId	yes	Number	10	-		10631675
2	送料	postagePrice	yes	Number	10	-9999	送付先に紐付く送料 （R-StoreFrontで指定した送料設定に準拠）

※未設定の場合、-9999になります。	100
3	送料税率	postageTaxRate	yes	Number	-	-		0.1
4	代引料	deliveryPrice	yes	Number	10	-9999	※未設定の場合、-9999になります	0
5	代引料税率	deliveryTaxRate	yes	Number	-	-		0.1
6	商品合計金額	goodsPrice	yes	Number	10	-9999	送付先に紐付く
商品金額 + ラッピング料	10000
7	合計金額	totalPrice	yes	Number	10	-9999	送付先に紐付く
商品金額 + 送料 + ラッピング料

※代引手数料は含まれません。
※未確定の場合、-9999になります。	10100
8	商品モデルリスト	ItemModelList	yes	List <ItemModel>	-	-		
9	購入時配送会社	defaultDeliveryCompanyCode	yes	String	382	-	以下のいずれか

1000: その他
1001: ヤマト運輸
1002: 佐川急便
1003: 日本郵便
1004: 西濃運輸
1005: セイノースーパーエクスプレス
1006: 福山通運
1007: 名鉄運輸
1008: トナミ運輸
1009: 第一貨物
1010: 新潟運輸
1011: 中越運送
1012: 岡山県貨物運送
1013: 久留米運送
1014: 山陽自動車運送
1015: NXトランスポート
1016: エコ配
1017: EMS
1018: DHL
1019: FedEx
1020: UPS
1021: 日本通運
1022: TNT
1023: OCS
1024: USPS
1025: SFエクスプレス
1026: Aramex
1027: SGHグローバル・ジャパン
1028: Rakuten EXPRESS
1029: 日本郵便 楽天倉庫出荷
1030: ヤマト運輸 クロネコゆうパケット
1031: 名鉄NX運輸	1001
Level 4: ItemModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	商品明細ID	itemDetailId	yes	Number	10	-		10631675
2	商品名	itemName	yes	String	3072	-		商品名
3	商品ID	itemId	yes	Number	10	-		10000119
4	商品番号	itemNumber	no	String	382	-	項目選択肢別在庫が指定された商品の場合、以下のルールで値が表示されます

SKU移行前注文：商品番号（店舗様が登録した番号）＋項目選択肢ID（横軸）＋項目選択肢ID（縦軸）
SKU移行後注文：商品番号（店舗様が登録した番号）	商品番号mgreen
5	商品管理番号	manageNumber	yes	String	382	-		mikan
6	単価	price	yes	Number	10	-		100
7	個数	units	yes	Number	10	-		2
8	送料込別	includePostageFlag	yes	Number	1	-	以下のいずれか

0: 送料別
1: 送料込みもしくは送料無料	1
9	税込別	includeTaxFlag	yes	Number	1	-	以下のいずれか

0: 税別
1: 税込み	0
10	代引手数料込別	includeCashOnDeliveryPostageFlag	yes	Number	1	-	以下のいずれか

0: 代引手数料別
1: 代引手数料込み	1
11	項目・選択肢	selectedChoice	no	String	12000	-	HTMLタグ除去済み

注文種別が｢1：通常購入 4：定期購入 5：頒布会 6：予約商品｣の場合、参照可能

※SKU移行後注文の場合、Level 5: skuModel > skuInfo を参照してください。	項目選択肢A:A選択肢１
項目選択肢B:B選択肢２
14	在庫タイプ	inventoryType	yes	Number	5	-	以下のいずれか

0: 在庫設定なし
1: 通常在庫設定
2: 項目選択肢在庫設定	2
15	楽天スーパーDEAL商品フラグ	dealFlag	yes	Number	1	-	以下のいずれか

0: 楽天スーパーDEAL商品ではない
1: 楽天スーパーDEAL商品である	0
16	医薬品フラグ	drugFlag	yes	Number	1	-	以下のいずれか

0: 医薬品ではない
1: 医薬品である	1
17	商品税率	taxRate	yes	Number	-	-		0.1
18	商品毎税込価格	priceTaxIncl	yes	Number	10	-	・税込商品の場合：
商品単価＝商品毎税込価格
・税別商品の場合：
商品単価＝税別価格
商品毎税込単価＝税込価格（商品単価 * (1+税率））
端数処理は、店舗設定に準ずる	1100
19	単品配送フラグ	isSingleItemShipping	yes	Number	1	-	以下のいずれか

0: 単品配送ではない
1: 単品配送である	0
20	SKUモデルリスト	SkuModelList	yes	List <skuModel>	-	-	-	
Level 3: TaxSummaryModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	税率	taxRate	yes	Number	-	-		0.1
2	請求金額	reqPrice	yes	Number	10	-9999	税率ごとの請求金額（税込）

※以下の場合、-9999になります。
・送料未確定
・代引手数料未確定

<楽天ポイントに係る消費税の課税処理および税込金額表示対応>に伴い、注文日が2022年4月1日（金）以降のデータから計算方法が変更。

注文日が2022年3月31日（木）以前のデータ：商品金額 + 送料 + ラッピング料 + 決済手数料 + 注文者負担金 - クーポン割引額 - 利用ポイント数
注文日が2022年4月1日（金）以降のデータ：商品金額 + 送料 + ラッピング料 + 決済手数料 + 注文者負担金 - クーポン割引額
※利用ポイント数を減算する前に計算
<適格請求書等保存方式（インボイス制度）対応>に伴い、2023年9月14日（木）以降に初回決済確定・発送完了となった注文より、後払い手数料（追加）分が含まれなくなります。	1000
3	請求額に対する税額	reqPriceTax	yes	Number	10	-9999	請求額に対する税額
※以下の場合、-9999になります。
・送料未確定
・代引手数料未確定

<楽天ポイントに係る消費税の課税処理および税込金額表示対応>に伴い、注文日が2022年4月1日（金）以降のデータから計算方法が変更。
注文日が2022年3月31日（木）以前のデータ：（商品金額 + 送料 + ラッピング料 + 決済手数料 + 注文者負担金 - クーポン割引額 - 利用ポイント数）に対する税額
注文日が2022年4月1日（金）以降のデータ：（商品金額 + 送料 + ラッピング料 + 決済手数料 + 注文者負担金 - クーポン割引額）に対する税額
※利用ポイント数を減算する前の各税額
<適格請求書等保存方式（インボイス制度）対応>に伴い、2023年9月14日（木）以降に初回決済確定・発送完了となった注文より、後払い手数料（追加）分が含まれなくなります。	100
4	合計金額	totalPrice	yes	Number	10	-9999	商品金額 + 送料 + ラッピング料

※送料未確定の場合、-9999になります。
※クーポン値引額、利用ポイント数、決済手数料、注文者負担金を含みません。	1250
5	決済手数料	paymentCharge	yes	Number	10	-9999	※代引手数料未確定の場合、-9999になります。	50
6	クーポン割引額	couponPrice	yes	Number	10	-9999	対象税率ごとのクーポン割引額	100
7	利用ポイント数	point	yes	Number	10	-9999	<楽天ポイントに係る消費税の課税処理および税込金額表示対応>に伴い、注文日が2022年4月1日（金）以降のデータから計算方法が変更。
注文日が2022年3月31日（木）以前のデータは対象税率ごとの利用ポイント数
注文日が2022年4月1日（金）以降のデータは常に0	150
Level 5: SkuModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	SKU管理番号	variantId	yes	String	40	-	SKU移行前の注文の場合、値は空になります。	17095519
2	システム連携用SKU番号	merchantDefinedSkuId	no	String	386	-	SKU移行前の注文の場合、値は空になります。	itemNumber-m-white
3	SKU情報	skuInfo	no	String	1600	-	SKU移行前の注文の場合、値は空になります。
1つのSKUに含まれる軸・選択肢などの情報が取得できます。	容量:560ml
本数:24本（1ケース）
ラベル:あり
商品種別	内容
シングルSKU	該当項目は無い為、データ無し
マルチSKU	バリエーション項目名とバリエーション選択肢。
下記のフォーマットで返却されます。
バリエーション項目名:バリエーション選択肢

Sample
検索結果が取得できた場合
Request (curl コマンドを使った例)
curl -X POST \
  https://api.rms.rakuten.co.jp/es/2.0/purchaseItem/getOrderItem/ \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "orderNumberList": ["504073-20230417-0207814266"]
}'
Response in JSON format (Status: 200 OK)
{
    "MessageModelList": [
        {
            "messageType": "INFO",
            "messageCode": "ORDER_EXT_API_GET_ORDER_INFO_101",
            "message": "受注情報取得に成功しました。(取得件数1件)"
        }
    ],
    "OrderModelList": [
        {
            "orderNumber": "123456-20230417-0207814266",
            "orderProgress": 100,
            "subStatusId": null,
            "orderDatetime": "2023-04-17T13:01:20+0900",
            "shopOrderCfmDatetime": null,
            "orderFixDatetime": null,
            "shippingInstDatetime": null,
            "shippingCmplRptDatetime": null,
            "deliveryDate": null,
            "shippingTerm": 1416,
            "giftCheckFlag": 0,
            "socialGiftFlag": 0,
            "isolatedIslandFlag": 0,
            "orderType": 1,
            "reserveNumber": null,
            "reserveDeliveryCount": null,
            "goodsPrice": 9150,
            "postagePrice": 0,
            "deliveryPrice": 0,
            "paymentCharge": 0,
            "paymentChargeTaxRate": 0.1,
            "totalPrice": 9150,
            "requestPrice": 8225,
            "couponAllTotalPrice": 915,
            "couponShopPrice": 915,
            "couponOtherPrice": 0,
            "additionalFeeOccurAmountToUser": 0,
            "additionalFeeOccurAmountToShop": 0,
            "asurakuFlag": 0,
            "drugFlag": 0,
            "dealFlag": 0,
            "OrdererModel": {
                "prefecture": "東京都"
            },
            "SettlementModel": {
                "settlementMethodCode": 1
            },
            "DeliveryModel": {
                "deliveryName": "宅配便",
                "deliveryClass": null
            },
            "PointModel": {
                "usedPoint": 10
            },
            "WrappingModel1": {
                "title": 1,
                "name": "シンプル",
                "price": 0,
                "includeTaxFlag": 1,
                "taxRate": 0.1,
                "taxPrice": 0
            },
            "WrappingModel2": {
                "title": 2,
                "name": "赤",
                "price": 0,
                "includeTaxFlag": 1,
                "taxRate": 0.1,
                "taxPrice": 0
            },
            "PackageModelList": [
                {
                    "basketId": 9501048,
                    "postagePrice": 0,
                    "postageTaxRate": 0.1,
                    "deliveryPrice": 0,
                    "deliveryTaxRate": 0.1,
                    "goodsPrice": 9150,
                    "totalPrice": 9150,
                    "defaultDeliveryCompanyCode": "1001",
                    "ItemModelList": [
                        {
                            "itemDetailId": 9501048,
                            "itemName": "Tシャツ （抗菌防臭/吸汗速乾）",
                            "itemId": 10000004,
                            "itemNumber": "c3ps390",
                            "manageNumber": "c3ps390",
                            "price": 1200,
                            "units": 1,
                            "includePostageFlag": 0,
                            "includeTaxFlag": 1,
                            "includeCashOnDeliveryPostageFlag": 0,
                            "selectedChoice": "領収書は同封されません:了承しました\n代金引換不可商品です:確認しました",
                            "inventoryType": 2,
                            "dealFlag": 0,
                            "drugFlag": 0,
                            "taxRate": 0.1,
                            "priceTaxIncl": 1200,
                            "isSingleItemShipping": 0,
                            "SkuModelList": [
                                {
                                    "variantId": "11",
                                    "merchantDefinedSkuId": "c3ps390M090",
                                    "skuInfo": "サイズ:M\nカラー:(090)ブラック"
                                }
                            ]
                        },
                        {
                            "itemDetailId": 9501049,
                            "itemName": "スニーカー（green）",
                            "itemId": 10000006,
                            "itemNumber": "s1gr050",
                            "manageNumber": "s1gr050",
                            "price": 6600,
                            "units": 1,
                            "includePostageFlag": 1,
                            "includeTaxFlag": 1,
                            "includeCashOnDeliveryPostageFlag": 0,
                            "selectedChoice": "領収書は同封されません:了承しました\n代金引換不可商品です:確認しました",
                            "inventoryType": 2,
                            "dealFlag": 0,
                            "drugFlag": 0,
                            "taxRate": 0.1,
                            "priceTaxIncl": 6600,
                            "isSingleItemShipping": 0,
                            "SkuModelList": [
                                {
                                    "variantId": "15",
                                    "merchantDefinedSkuId": "s1gr050sz8H",
                                    "skuInfo": "サイズ:26.5cm"
                                }
                            ]
                        },
                        {
                            "itemDetailId": 9501050,
                            "itemName": "靴下（スニーカーソックス）",
                            "itemId": 10000007,
                            "itemNumber": "tst1234",
                            "manageNumber": "tst1234",
                            "price": 1350,
                            "units": 1,
                            "includePostageFlag": 0,
                            "includeTaxFlag": 1,
                            "includeCashOnDeliveryPostageFlag": 0,
                            "selectedChoice": null,
                            "inventoryType": 1,
                            "dealFlag": 0,
                            "drugFlag": 0,
                            "taxRate": 0.1,
                            "priceTaxIncl": 1350,
                            "isSingleItemShipping": 0,
                            "SkuModelList": [
                                {
                                    "variantId": "tst1234",
                                    "merchantDefinedSkuId": null,
                                    "skuInfo": null
                                }
                            ]
                        }
                    ]
                }
            ],
            "TaxSummaryModelList": [
                {
                    "taxRate": 0.1,
                    "reqPrice": 8235,
                    "reqPriceTax": 749,
                    "totalPrice": 9150,
                    "paymentCharge": 0,
                    "couponPrice": 915,
                    "point": 0
                }
            ]
        }
    ]
}
結果がない場合
Request (curl コマンドを使った例)
curl -X POST \
  https://api.rms.rakuten.co.jp/es/2.0/purchaseItem/getOrderItem/ \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "orderNumberList": [
        "123456-20210101-10740985",
        "123456-20210101-10737896",
        "123456-20210101-10740988"
    ]
}'
Response in JSON format (Status: 200 OK)
{
    "MessageModelList": [
        {
            "messageType": "INFO",
            "messageCode": "ORDER_EXT_API_GET_ORDER_INFO_102",
            "message": "受注情報が取得できませんでした。",
            "orderNumber": "123456-20210101-10740985"
        },
        {
            "messageType": "INFO",
            "messageCode": "ORDER_EXT_API_GET_ORDER_INFO_102",
            "message": "受注情報が取得できませんでした。",
            "orderNumber": "123456-20210101-10737896"
        },
        {
            "messageType": "INFO",
            "messageCode": "ORDER_EXT_API_GET_ORDER_INFO_102",
            "message": "受注情報が取得できませんでした。",
            "orderNumber": "123456-20210101-10740988"
        }
    ],
    "OrderModelList": []
}
