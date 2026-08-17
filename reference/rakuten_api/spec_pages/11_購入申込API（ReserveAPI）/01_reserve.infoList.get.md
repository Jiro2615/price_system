RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/reserveapi/reserveinfolistget/
サービス: 購入申込API（ReserveAPI）

サービス一覧へ戻る / ReserveAPI

RMS WEB SERVICE : reserve.infoList.get
Overview
この機能を利用すると、指定した条件に一致する申込情報を取得することができます。

SKUプロジェクトにて追加・修正となる項目は背景色を緑に変更しています。

※機能の注意点

・取得可能な情報の範囲及び並び順について
当機能では、注文確定前の申込情報を申込番号単位で取得します。
申込情報一覧は、申込日時、申込番号の降順でソートされます。
1件の申込番号内の申込明細情報については、お届け回の昇順で取得します。
注文確定保留中のお届け回は申込明細情報に出力されません。

・取得件数について
レスポンス内の「取得件数（limit）」は、申込番号の件数であり、申込明細情報の件数ではありません。
システム利用状況により、取得時タイムアウトが発生する可能性があります。再度お試しいただくか、条件を絞って検索してください。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/reserve/reserveInfoList	GET
Request
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameters
No	Parameter Name	Description	Required	Multiple	Type	Default	Note	Sample
1	dateType	期間指定種類	yes	no	number	-	以下のいずれか

1：申込日
2：お届け予定日
3：注文確定日	1
2	reserveType	商品種別	no	yes	number	-	以下より複数指定可能

1：定期購入
2：頒布会
3：予約	1
3	keywordType	検索方法	no	no	number	-	以下のみ指定可能
1: 商品管理番号で検索

こちらを指定した場合、「商品管理番号」が必須になります。 	1
4	keyword	商品管理番号 	条件付き必須	no	string	-	「検索方法」を設定した場合、必須になります。
「商品管理番号」のみ指定があり、「検索方法」の指定が 1 でない場合、エラーが発生します。	100000004

5	startDate	開始日	no	no	date	現在の日付	最大検索期間：前年の本日より来年本日の前日までの2年間

例：本日が2019-06-01の場合は設定できる最大検索期間は
・startDate：2018-06-01
・endDate ：2020-05-31	2019-06-01
6	endDate	終了日	no	no	date	現在の日付
7	reserveStatusName	申込ステータス名	no	no	string	-	各店舗で利用している申込ステータスを参照し、完全一致の名称を指定してください。	申込中
8	deviceCode	利用端末	no	yes	number	-	以下より複数指定可能

1 : PC
2 : モバイル
3 : スマートフォン
4 : タブレット	3
9	settlementName	支払方法	no	no	string	-	各店舗で利用している決済方法を参照し、完全一致の名称を指定してください。	クレジットカード決済
10	deliveryName	配送方法	no	no	string	-	基本情報設定の配送方法・送料設定ページにある「配送方法」と「配送キャリア」を完全一致で指定してください。
フォーマット：配送方法(配送キャリア)	宅配便(ヤマト運輸)
11	modifyFlag	申込履歴修正有無フラグ	no	no	number	-	以下のいずれか

0：申込履歴からの修正なし
1：申込履歴からの修正あり	0
12	limit	取得件数	no	no	number	100	一回のリクエストで取得する件数です。
条件に一致する申込件数が多い場合、処理のパフォーマンスを向上するために、limit設定することがおすすめです。

指定なしの場合先頭100件のみ取得対象となります。
値の範囲: 1 - 1000	100
13	offset	取得位置	no	no	number	-	特定の部分のデータを取得するために設定する値です。
パラメーターが設定されていないまたは0の場合、全てのデータが検索対象になります。
limitと同様、処理のパフォーマンスを向上するために設定することがおすすめです。

例：1000件データのうちの501件目～700件目の200件のみ取得したい場合、limit=200&offset=500で設定します。	200
Response
Response Header
Key	Value
Content-Type	application/json;charset=utf-8
Response Body
Level 1: base
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	resultCodeInt 	処理結果	number	yes	Response Code Reference の一覧はこちら	0
2	resultCode	処理結果コード	string	yes	N00-000
3	resultMessage	処理結果メッセージ	string	yes	正常終了しました
4	responseDatetime	レスポンス日時	date	yes	yyyy-MM-ddTHH:mm:ssZ	2019-12-18T10:52:20+0900
5	totalCount	検索条件に一致したデータの総数	number	yes		3000
6	resultCount	limit の設定により、実際に取得したデータの件数	number	yes	値の範囲: 1 - 1000	1
7	limit	取得件数	number	yes	リクエストの値が設定されます。
エラーの発生するタイミングにより、0で設定される場合があります。	0
8	offset	取得位置	number	yes	リクエストの値が設定されます。
エラーの発生するタイミングにより、0で設定される場合があります。	0
9	publicReserveModelList	申込情報リスト	List<reserveModel>	no	申込情報一覧	
Level 2: reserveModel
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	shopId	店舗ID	number	yes		503204
2	reserveNumber	申込番号	string	yes		503204-20191204-262709-r
3	reserveStatus	申込ステータス	number	yes	1 : 申込中
101～ : 店舗のオリジナルステータス

※店舗は10個までオリジナルステータスを持つことができます。	1
4	reserveStatusName	申込ステータス名	string	yes	店舗各自申込ステータス参照	申込中
5	reserveType	申込種別	number	yes	以下のいずれか

1：定期購入
2：頒布会
3：予約	1
6	shippingCycle	お届けサイクル	string	no		毎月1日にお届け
7	rakutenMemberFlag	楽天会員フラグ	number	yes	以下のいずれか

0: 楽天会員ではない
1: 楽天会員である	1
8	reserveDatetime	申込日	date	yes	yyyy-MM-ddTHH:mm:ssZ	2019-12-04T16:04:35+0900
9	memo	ひとことメモ	string	no		メモ
10	carrierCode	利用端末	number	yes	以下のいずれか

0：PC (Windows系のスマートフォン、タブレットを含む)
1：モバイル(docomo) フィーチャーフォン
2：モバイル(KDDI) フィーチャーフォン
3：モバイル(Softbank) フィーチャーフォン
5：モバイル(WILLCOM) フィーチャーフォン
11：スマートフォン（iPhone系）
12：スマートフォン（Android系）
19：スマートフォン（その他）
21：タブレット（iPad系）
22：タブレット（Android系）
29：タブレット（その他）
99：その他　不明な場合も含む	0
11	emailCarrierCode	メールキャリアコード	number	yes	以下のいずれか

0：PC ("@i.softbank.jp"を含む)
1：DoCoMo
2：au
3：SoftBank
5：WILLCOM
99：その他	0
12	reserveItem	申込商品情報	reserveItem	yes		
13	reserveOrderer	申込者情報	reserveOrderer	yes		
14	reserveSender	送付先情報	reserveSender	yes		
15	reserveDetails	申込明細情報	List<reserveDetails>	yes		
Level 3: reserveItem
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	itemId	商品ID	number	yes		10000315
2	itemName	商品名	string	yes		定期商品
3	itemNumber	商品番号	string	no	[SKU対応リリース後]
商品番号
※SKU対応は2023年2月12日(日)のリリースを予定しております。

[SKU対応リリース前]
商品番号＋項目選択肢ID（横軸）＋項目選択肢ID（縦軸）	1110123
4	url	商品URL	string	yes		/_rakuten001/teiki_0005/
5	price	価格	number	yes		1000
6	firstPrice	商品単価 初回	number	no		780
7	lastPrice	商品単価 最終回	number	no		1500
8	units	個数	number	yes		1
9	includePostageFlag	送料込別	number	yes	以下のいずれか

0：送料別
1：送料込みもしくは送料無料	1
10	includeTaxFlag	税込別	number	yes	以下のいずれか

0：税別
1：税込	1
11	taxRate	税率	number	yes		0.08
12	includeCodFeeFlag	代引手数料込別	number	yes	以下のいずれか

0：代引手数料別
1：代引手数料込み	1
13	selectedChoice	項目・選択肢	string	no	HTMLタグ除去済み。
SKU移行前後で設定値が変わります。

[SKU移行後店舗]
項目選択肢
形式は「項目名:選択肢」

[SKU移行前店舗]
項目選択肢別在庫および項目選択肢
形式は
・「横軸項目名:横軸選択肢 縦軸項目名:縦軸選択肢」（項目選択肢別在庫）
・「項目名:選択肢」（項目選択肢）	[SKU移行後店舗]
簡易包装のみ:了解した

[SKU移行前店舗]
SIZE:M
COLOR:Green
簡易包装のみ:了解した
14	pointRate	ポイント倍率	number	yes	ポイントレート	1
15	pointType	ポイントタイプ	number	yes	以下のいずれか

0：変倍なし
1：店舗別変倍
2：商品別変倍
-99：エラー時無効値	0
16	inventoryType	在庫タイプ	number	yes	以下のいずれか

0：在庫設定なし
1：通常在庫設定
2：項目選択肢在庫設定	1
17	singleItemShippingFlag	単品配送フラグ	number	yes	以下のいずれか

0：単品配送ではない
1：単品配送である

※「共通の送料込みライン」の導入より値が取得できるようになります。それ以前はnull値が入ります。	0
18	variantId	SKU管理番号	string	yes		12345678
19	merchantDefinedSkuId	システム連携用SKU番号	string	no		BLK0100
20	skuInfo	SKU情報	string	no	形式は、「バリエーション:選択肢」
※シングルSKUの場合は空白	色:黒
サイズ:M
Level 3: reserveOrderer
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	differentSenderAddressFlag	異なる送付先フラグ	number	yes	以下のいずれか

0：注文者と同じ住所の送付先
1：注文者と異なる住所の送付先	0
2	zipCode1	注文者郵便番号1	string	yes		158
3	zipCode2	注文者郵便番号2	string	yes		0094
4	prefecture	注文者住所：都道府県	string	yes		東京都
5	city	注文者住所：都市区	string	yes		世田谷区
6	subAddress	注文者住所：町以降	string	yes		玉川
7	familyName	注文者名字	string	yes		楽天
8	firstName	注文者名前	string	yes		太郎
9	familyNameKana	注文者名字フリガナ	string	yes		ラクテン
10	firstNameKana	注文者名前フリガナ	string	yes		タロウ
11	phoneNumber1	注文者電話番号1	string	yes	電話番号の1,2,3の内、nullは１つまで許可	090
12	phoneNumber2	注文者電話番号2	string	1234
13	phoneNumber3	注文者電話番号3	string	5678
14	emailAddress	メールアドレス	string	yes	メールアドレスはマスキングされています。	815db15ff6ee7c02@pc.fw.rakuten.ne.jp
15	sex	注文者性別	string	yes		男
16	birthday	注文者誕生日	string	no	以下のいずれか

・2000年1月1日生の場合、2000-01-01で表示する（yyyy-MM-dd）
・-年-月-日生の場合、nullで表示する	2000-01-01
17	deliveryName	配送方法	string	no		宅配便(ヤマト運輸)
18	comment	コメント	string	no	注文フォームカスタマイズで設定したタイトルおよび、お客様が入力した内容。
形式は「[注文フォームタイトル:]ユーザー入力内容」。	[メッセージカードの内容をご記入ください。:]
ご卒業おめでとうございます。
Level 3: reserveSender
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	familyName	送付先名字	string	yes		楽天
2	firstName	送付先名前	string	yes		太郎
3	familyNameKana	送付先名字フリガナ	string	yes		ラクテン
4	firstNameKana	送付先名前フリガナ	string	yes		タロウ
5	zipCode1	送付先郵便番号1	string	yes		158
6	zipCode2	送付先郵便番号2	string	yes		0094
7	prefecture	送付先住所：都道府県	string	yes		東京都
8	city	送付先住所：都市区	string	yes		世田谷区
9	subAddress	送付先住所：町以降	string	yes		玉川
10	phoneNumber1	送付先電話番号1	string	yes	電話番号の1,2,3の内、nullは１つまで許可	090
11	phoneNumber2	送付先電話番号2	string	1234
12	phoneNumber3	送付先電話番号3	string	5678
13	shippingNumber	お荷物伝票番号	string	no		111-22-334
14	isolatedIslandFlag	離島フラグ	number	yes	以下のいずれか

0：送付先に離島が含まれていない
1：送付先に離島が含まれている

※2020年3月15日より値が取得できるようになります。それ以前はnull値が入ります。	0
Level 3: reserveDetails
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	detailId	お届け回（詳細ID）	number	yes		1
2	shippingDate	お届け日	date	yes	yyyy-MM-dd	2019-12-31
3	commitDate	注文確定日	date	yes	yyyy-MM-dd	2019-12-30
4	releaseDate	発売日	date	no	yyyy-MM-dd	2019-11-30
5	itemDetailName	商品内訳	string	no		null
6	shippingStatus	お届けステータス	number	yes	1: 申込中	1
7	earlyFlag	早期注文確定フラグ	number	yes	以下いずれか

0：通常
1：早期注文確定	0
8	totalAmount	合計金額	number	yes	商品金額 + 消費税 + 送料 + 決済手数料

※決済手数料には代引手数料、楽天バンク決済手数料、後払い決済手数料が入ります。
※消費税、送料、代引手数料のいずれかが未確定の場合、-9999になります。	2100
9	reserveSettlement	申込決済情報	reserveSettlement	yes		
10	reserveAmount	申込請求金額情報	reserveAmount	yes		
Level 4: reserveSettlement
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	settlementName	支払方法	string	yes		銀行振込
2	cardName	カード会社	string	no	支払方法が「クレジットカード」の場合のみ値があります。	VISA
3	cardOwner	カード名義人	string	no	支払方法が「クレジットカード」の場合のみ値があります。	TARO RAKUTEN
4	cardInstallmentType	クレジットカード分割選択	string	no	以下のいずれか

0：一括払い
1：リボ払い
2：分割払い
3：その他払い
4：ボーナス一括払い

支払方法が「クレジットカード」の場合のみ値があります。	2
5	cardInstallmentDesc	クレジットカード分割備考	string	no	以下のいずれか

103：3回払い
105：5回払い
106：6回払い
110：10回払い
112：12回払い
115：15回払い
118：18回払い
120：20回払い
124：24回払い

支払方法が「クレジットカード」、かつ、「クレジットカード分割選択」が「2: 分割払い」の場合のみ値があります。	105
Level 4: reserveAmount
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	taxAmount	消費税	number	no	税込み商品の場合は0が取得されます。
※未確定の場合、-9999になります。	100
2	postageAmount	送料	number	no	※未確定の場合、-9999になります。	1000
3	codFeeAmount	代引料	number	no	代引手数料が掛からない決済手段の場合は、0になります。
※未確定の場合、-9999になります。	0
Sample
申込情報一覧が取得できた場合
Request (curl コマンドを使った例)
curl -v -H 'Authorization:ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' -X GET
https://api.rms.rakuten.co.jp/es/1.0/reserve/reserveInfoList?dateType=1&startDate=2019-12-04'
Response (Status: 200 OK)
{
    "resultCodeInt": 0,
    "resultCode": "N00-000",
    "resultMessage": "正常終了しました",
    "responseDatetime": "2019-12-23T16:53:17+0900",
    "totalCount": 1,
    "resultCount": 1,
    "limit": 100,
    "offset": 0,
    "publicReserveModelList": [
        {
            "shopId": 123456,
            "reserveNumber": "123456-20191204-262709-r",
            "reserveStatus": 1,
            "reserveStatusName": "申込中",
            "reserveType": 1,
            "shippingCycle": "毎月1日にお届け",
            "rakutenMemberFlag": 1,
            "reserveDatetime": "2019-12-04T16:04:35+0900",
            "memo": null,
            "carrierCode": 0,
            "emailCarrierCode": 0,
            "reserveItem": {
                "itemId": 10000315,
                "itemName": "CTAX_定期_店舗10%_商品8%_税別_送料別_代引別",
                "itemNumber": "1110123",
                "url": "/_misostgopp04/ctax_test_teiki_0005/",
                "price": 1000,
                "firstPrice": null,
                "lastPrice": null,
                "units": 1,
                "includePostageFlag": 1,
                "includeTaxFlag": 1,
                "taxRate": 0.08,
                "includeCodFeeFlag": 1,
                "selectedChoice": "簡易包装のみ:了解した",
                "pointRate": 1,
                "pointType": 0,
                "inventoryType": 1,
                "singleItemShippingFlag": null,
                "variantId": "12345678",
                "merchantDefinedSkuId": "BLK0100",
                "skuInfo": "色:黒\nサイズ:M"
             },
            "reserveOrderer": {
                "differentSenderAddressFlag": 0,
                "zipCode1": "460",
                "zipCode2": "0008",
                "prefecture": "愛知県",
                "city": "名古屋市中区",
                "subAddress": "栄1丁目12‐17",
                "familyName": "Gyoku",
                "firstName": "Test",
                "familyNameKana": "ー",
                "firstNameKana": "ー",
                "phoneNumber1": "090",
                "phoneNumber2": "1234",
                "phoneNumber3": "5678",
                "emailAddress": "xxx@xxx.xxx",
                "sex": "-",
                "birthday": null,
                "deliveryName": "宅配便(ヤマト運輸)",
                "comment": "[メッセージカードの内容をご記入ください。:]\nご卒業おめでとうございます。\n"
            },
            "reserveSender": {
                "familyName": "Gyoku",
                "firstName": "Test",
                "familyNameKana": "ー",
                "firstNameKana": "ー",
                "zipCode1": "460",
                "zipCode2": "0008",
                "prefecture": "愛知県",
                "city": "名古屋市中区",
                "subAddress": "栄1丁目12‐17",
                "phoneNumber1": "090",
                "phoneNumber2": "1234",
                "phoneNumber3": "5678",
                "shippingNumber": null,
                "isolatedIslandFlag": null
            },
            "reserveDetails": [
                {
                    "detailId": 1,
                    "shippingDate": "2019-12-31",
                    "commitDate": "2019-12-30",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 2,
                    "shippingDate": "2020-01-31",
                    "commitDate": "2020-01-30",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 3,
                    "shippingDate": "2020-02-29",
                    "commitDate": "2020-02-28",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 4,
                    "shippingDate": "2020-03-31",
                    "commitDate": "2020-03-30",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 5,
                    "shippingDate": "2020-04-30",
                    "commitDate": "2020-04-29",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 6,
                    "shippingDate": "2020-05-31",
                    "commitDate": "2020-05-30",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 7,
                    "shippingDate": "2020-06-30",
                    "commitDate": "2020-06-29",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 8,
                    "shippingDate": "2020-07-31",
                    "commitDate": "2020-07-30",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 9,
                    "shippingDate": "2020-08-31",
                    "commitDate": "2020-08-30",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 10,
                    "shippingDate": "2020-09-30",
                    "commitDate": "2020-09-29",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 11,
                    "shippingDate": "2020-10-31",
                    "commitDate": "2020-10-30",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                },
                {
                    "detailId": 12,
                    "shippingDate": "2020-11-30",
                    "commitDate": "2020-11-29",
                    "releaseDate": null,
                    "itemDetailName": null,
                    "shippingStatus": 1,
                    "earlyFlag": 0,
                    "totalAmount": 2100,
                    "reserveSettlement": {
                        "settlementName": "銀行振込",
                        "cardName": null,
                        "cardOwner": null,
                        "cardInstallmentType": null,
                        "cardInstallmentDesc": null
                    },
                    "reserveAmount": {
                        "taxAmount": 100,
                        "postageAmount": 1000,
                        "codFeeAmount": 0
                    }
                }
            ]
        }
    ]
}
条件に一致する申込情報一覧がない場合
Request (curl コマンドを使った例)
curl -v -H 'Authorization:ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' -X GET
https://api.rms.rakuten.co.jp/es/1.0/reserve/reserveInfoList?dateType=3&reserveType=2'
Response (Status: 200 OK)
{
    "resultCodeInt": 1,
    "resultCode": "N00-001",
    "resultMessage": "検索結果が0件です",
    "responseDatetime": "2019-12-23T16:54:20+0900",
    "totalCount": 0,
    "resultCount": 0,
    "limit": 100,
    "offset": 0,
    "publicReserveModelList": null
}
startDate と endDate の時系列が逆だった場合
Request (curl コマンドを使った例)
curl -v -H 'Authorization:ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' -X GET
https://api.rms.rakuten.co.jp/es/1.0/reserve/reserveInfoList?dateType=1&startDate=2020-02-03&endDate=2019-12-06&deviceCode=4&limit=20'
Response (Status: 200 OK)
{
    "resultCodeInt": 2,
    "resultCode": "E01-005",
    "resultMessage": "期間指定の終了日は開始日より前になっています",
    "responseDatetime": "2019-12-13T15:56:46+0900",
    "totalCount": 0,
    "resultCount": 0,
    "limit": 0,
    "offset": 0,
    "publicReserveModelList": null
}
