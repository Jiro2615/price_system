RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inventoryapi2_1/inventories_bulk_get/
サービス: 在庫API 2.1（InventoryAPI 2.1）

サービス一覧へ戻る / InventoryAPI 2.1

RMS WEB SERVICE : inventories.bulk.get
Overview
この機能を利用すると、商品管理番号とSKU管理番号を指定し、最大で1000件の在庫数、出荷リードタイム、配送リードタイム関連の情報を一括で取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-get	POST
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/json
Path Parameter
None

HTTP Body
Level 1: base
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	inventories	在庫情報	yes	List<inventory>	-	1..1000	在庫情報リスト
Level 2: inventory
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	manageNumber	商品管理番号	yes	string	32	1	以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_" 
大文字は小文字に自動変換
2	variantId	SKU管理番号	yes	string	32	1	以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_" 
大文字・小文字は、異なる文字として扱う
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
6	created	登録日時	yes	string 	1	在庫数の初回登録日時
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。
7	updated	更新日時	yes	string 	1	在庫数の更新日時
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。
Level 3: operationLeadTime
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
1	errors	エラー	yes	List<error>	1..n	エラーのリスト。
Level 2: error
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	code	コード	yes	string	1	メッセージコードの一覧はこちら
2	message	メッセージ	yes	string	1
2	metadata	メタデータ	no	object	1
LEVEL 3: METADATA
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	propertyPath	属性パス	no	string	1	発生したエラーの位置
Sample
成功した場合
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-get' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "inventories": [
        {
            "manageNumber": "mng1234",
            "variantId": "sku1"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5"
        }
    ]
}'
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
            "updated": "2022-02-01T19:30:00+09:00"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5",
            "quantity": 5,
            "created": "2022-01-03T19:00:00+09:00",
            "updated": "2022-02-04T19:30:00+09:00"
        }
    ]
}
失敗した場合
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.1/inventories/bulk-get' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "inventories": [
        {
            "manageNumber": "12345678901234567890123456789012345678901",
            "variantId": "sku1"
        },
        {
            "manageNumber": "mng1234",
            "variantId": "sku2"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5"
        }
    ]
}'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0004",
           "message": "Max length of manageNumber must be within 32 bytes.",
           "metadata": {
               "propertyPath": "inventories[0].manageNumber"
           }
        }
    ]
}
