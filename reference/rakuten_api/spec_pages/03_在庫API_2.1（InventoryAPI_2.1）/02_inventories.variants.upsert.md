RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inventoryapi2_1/inventories_variants_upsert/
サービス: 在庫API 2.1（InventoryAPI 2.1）

サービス一覧へ戻る / InventoryAPI 2.1

RMS WEB SERVICE : inventories.variants.upsert
Overview
この機能を利用すると、商品管理番号とSKU管理番号を指定し、在庫数、出荷リードタイム、配送リードタイム関連の情報を登録・更新することができます。
部分更新の機能ではないため、リクエストに含まれない項目は値が削除されます。
存在しない商品管理番号や、存在する商品管理番号に紐づかないSKU管理番号を指定した場合でもエラーにはなりませんが、
在庫情報のみが存在する状態となります。

※機能の注意点
・存在しない商品管理番号を指定した場合
存在する商品管理番号と紐づかない在庫情報は、最終更新日から24時間以降に削除します。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.1/inventories/manage-numbers/{manageNumber}/variants/{variantId}	PUT
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/json
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	manageNumber	商品管理番号	yes	string	32	1	商品管理番号が存在する場合、更新。
商品管理番号が存在しない場合、存在しない商品管理番号を指定したことでエラーにはなりませんが、
在庫情報として設定される商品がないため、確認することはできません。また、定期的に削除されます。

以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0-9"
・"-", "_"
大文字は小文字に自動変換。
2	variantId	SKU管理番号	yes	string	32	1	SKU管理番号が存在する場合、更新。
SKU管理番号が存在しない場合、存在しないSKU管理番号を指定したことでエラーにはなりませんが、
在庫情報として設定される商品がないため、確認することはできません。また、定期的に削除されます。

以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0-9"
・"-", "_"
大文字・小文字は、異なる文字として扱う。
HTTP Body
Level 1: base
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	mode	更新モード	yes	enum	-	1	・ABSOLUTE: 絶対値指定
・RELATIVE: 相対値指定

新規登録時は必ず「ABSOLUTE」を指定。
2	quantity	在庫数	yes	number	99999	1	
3	operationLeadTime	出荷リードタイム	no	operationLeadTime	-	0..1	
4	shipFromIds	配送リードタイムIDのリスト	no	List<int>	-	0..1	配送リードタイムに自動選択対象の設定がある場合、未指定時には自動選択が適用されます。

IDの値はShopAPIの shop.shipFrom.get で取得可能。
　4.2.5. Level 3: shipFrom - shipFromId
Level 2: operationLeadTime
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	normalDeliveryTimeId	在庫あり時出荷リードタイムID	no	number	-	0..1	出荷リードタイムに自動選択対象の設定がある場合、未指定時には自動選択が適用されます。

IDの値はShopAPIの shop.operationLeadTime.get で取得可能。
　4.2.5. Level 3: operationLeadTime - operationLeadTimeId
2	backOrderDeliveryTimeId	在庫切れ時出荷リードタイムID	no	number	-	0..1	出荷リードタイムに自動選択対象の設定がある場合、未指定時には自動選択が適用されます。

IDの値はShopAPIの shop.operationLeadTime.get で取得可能。
　4.2.5. Level 3: operationLeadTime - operationLeadTimeId
Response
HTTP Header
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合
None

失敗した場合

Level 1: base
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	errors	エラー	yes	List<error>	1	エラーのリスト。
Level 2: error
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	code	コード	yes	string	1	メッセージコードの一覧はこちら。
2	message	メッセージ	yes	string	1
3	metadata	メタデータ	no	object	1	エラーの補足情報。
Level 3: metadata
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	propertyPath	属性パス	no	string	1	発生したエラーの位置。
Sample
成功した場合
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.1/inventories/manage-numbers/mng1234/variants/sku1' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "mode": "ABSOLUTE",
    "quantity": 3,
    "operationLeadTime": {
        "normalDeliveryTimeId": 4,
        "backOrderDeliveryTimeId": 5
    },
    "shipFromIds": [
        3
    ]
}'
Response (Status: 204 No Content)
失敗した場合
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.1/inventories/manage-numbers/mng1234/variants/sku1' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "mode": "ABSOLUTE",
    "quantity": "a",
    "operationLeadTime": {
        "normalDeliveryTimeId": 4,
        "backOrderDeliveryTimeId": 5
    },
    "shipFromIds": [
        3
    ]
}'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0002",
            "message": "quantity has an invalid value : a.",
            "metadata": {
                "propertyPath": "quantity"
            }
        }
    ]
}
