RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inventoryapi2_1/inventories_bulk_get_range/
サービス: 在庫API 2.1（InventoryAPI 2.1）

サービス一覧へ戻る / InventoryAPI 2.1

RMS WEB SERVICE : inventories.bulk.get.range
Overview
この機能を利用すると、在庫数の上限下限を指定し、商品管理番号、SKU管理番号、在庫数、出荷リードタイム、配送リードタイム、登録日時、更新日時を最大1000件取得することができます。
更新日時の降順で出力されます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-get/range	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Query Parameter
No	Parameter Name	Logical Name	Required	Type	Multiplicity	Description
1	minQuantity	最小在庫数	yes
いずれかが必須	number	0..1	※店舗内の商品情報が1000SKUを超える場合はエラー（上限エラー）。
2	maxQuantity		最大在庫数	number	0..1
HTTP Body
None

Response
HTTP Header
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合

Level 1: base
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	inventories	在庫情報	yes	List<inventories>	0..1000	在庫情報リスト
Level 2: inventories
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	manageNumber	商品管理番号	yes	string	1	以下の英数字、記号。
・"a~z"
・"0~9"
・"-", "_" 
2	variantId	SKU管理番号	yes	string	1	以下の英数字、記号。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_" 
3	quantity	在庫数	yes	number	1	商品の在庫数
4	operationLeadTime	出荷リードタイム	no	operationLeadTime	0..1	
5	shipFromIds	配送リードタイムIDのリスト	no	List<int>	0..1	配送リードタイムに自動選択対象以外の設定がある場合のみ、この項目を返却します。

※配送リードタイムIDは、以下より確認してください。
　ShopAPIの shop.shipFrom.get の下記項目から取得可能。
　4.2.5. Level 3: shipFrom - shipFromId
6	created	登録日時	yes	string	1	在庫数の初回登録日時。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。
7	updated	更新日時	yes	string 	1	在庫数の更新日時。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。
Level3: operationLeadTime
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	normalDeliveryTimeId	在庫あり時出荷リードタイムID	no	number	0..1	出荷リードタイムに自動選択対象以外の設定がある場合のみ、この項目を返却します。

※出荷リードタイムIDは、以下より確認してください。
　ShopAPIの shop.operationLeadTime.get の下記項目から取得可能。
　4.2.5. Level 3: operationLeadTime - operationLeadTimeId
2	backOrderDeliveryTimeId	在庫切れ時出荷リードタイムID	no	number	0..1	出荷リードタイムに自動選択対象以外の設定がある場合のみ、この項目を返却します。

※出荷リードタイムIDは、以下より確認してください。
　ShopAPIの shop.operationLeadTime.get の下記項目から取得可能。
　4.2.5. Level 3: operationLeadTime - operationLeadTimeId

失敗した場合

Level 1: base
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	errors	エラー	yes	List<error>	1..n	エラーのリスト
Level 2: errors
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	code	コード	yes	string	1	メッセージコードの一覧はこちら
2	message	メッセージ	yes	string	1
Sample
成功した場合
既存在庫情報
manageNumber	variantId	quantity	created	updated
mng1234	sku1	1	2022-01-01T19:00:00+09:00	2022-02-28T19:30:00+09:00
mng1234	sku2	2	2022-01-03T19:00:00+09:00	2022-02-10T19:30:00+09:00
mng1234	sku3	6	2022-01-01T19:00:00+09:00	2022-02-04T19:30:00+09:00
mng5678	sku4	5	2022-01-05T19:00:00+09:00	2022-02-13T19:30:00+09:00
mng5678	sku5	4	2022-01-04T19:00:00+09:00	2022-02-08T19:30:00+09:00
mng9012	sku6	3	2022-01-03T19:00:00+09:00	2022-02-04T19:30:00+09:00
mng9012	sku7	0	2022-01-01T19:00:00+09:00	2022-02-08T19:30:00+09:00
リクエスト
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-get/range?minQuantity=1&maxQuantity=5' \
 --header 'Authorization: ESA xxx'
Response (Status: 200 OK)
{
    "inventories": [
        {   "manageNumber": "mng1234",
            "variantId": "sku1",
            "quantity": 1,
            "operationLeadTime": {
                "normalDeliveryTimeId": 4,
                "backOrderDeliveryTimeId": 5
            },
            "shipFromIds": [
                3
            ],
            "created": "2022-01-01T19:00:00+09:00",
            "updated": "2022-02-28T19:30:00+09:00"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku4",
            "quantity": 5,
            "operationLeadTime": {
                "normalDeliveryTimeId": 4
            },
            "created": "2022-01-05T19:00:00+09:00",
            "updated": "2022-02-13T19:30:00+09:00"
        },
        {
            "manageNumber": "mng1234",
            "variantId": "sku2",
            "quantity": 2,
            "operationLeadTime": {
                "backOrderDeliveryTimeId": 5
            },
            "created": "2022-01-03T19:00:00+09:00",
            "updated": "2022-02-10T19:30:00+09:00"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5",
            "quantity": 4,
            "shipFromIds": [
                3
            ],
            "created": "2022-01-04T19:00:00+09:00",
            "updated": "2022-02-08T19:30:00+09:00"
        },
        {
            "manageNumber": "mng9012",
            "variantId": "sku6",
            "quantity": 3,
            "created": "2022-01-03T19:00:00+09:00",
            "updated": "2022-02-04T19:30:00+09:00"
        }
    ]
}
失敗した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-get/range?minQuantity=100000&maxQuantity=5000000' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0003",
            "message": "minQuantity must be between 0 and 99999."
        }
    ]
}
