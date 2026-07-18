RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inventoryapi2/upsertbulkinventories
サービス: 在庫API 2.0（InventoryAPI 2.0）

サービス一覧へ戻る / InventoryAPI 2.0

RMS WEB SERVICE : inventories.bulk.upsert
Overview
この機能を利用すると、商品管理番号とSKU管理番号を指定し、最大で400件の在庫数を一括で登録・更新することができます。
存在しない商品管理番号や、存在する商品管理番号に紐づかないSKU管理番号を指定した場合でもエラーにはなりませんが、
在庫情報のみが存在する状態となります。

※機能の注意点
・存在しない商品管理番号を指定した場合
商品管理番号と紐づかない在庫情報は、最終更新日から24時間以降に削除します。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/inventories/bulk-upsert	POST
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
1	inventories	在庫情報	yes	List<inventory>	-	1..400	在庫情報リスト
Level 2: inventory
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
大文字は小文字に自動変換。
3	mode	更新モード	yes	enum	-	1	・ABSOLUTE：絶対値指定
・RELATIVE：相対値指定

新規登録時は必ず「ABSOLUTE」を指定
4	quantity	在庫数	yes	number	99999	1	
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
1	errors	エラー	yes	List<error>	1..n	エラーのリスト
Level2: error
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	code	コード	yes	string	1	メッセージコードの一覧はこちら
2	message	メッセージ	yes	string	1
3	metadata	メタデータ	no	object	1	エラーの補足情報
LEVEL 3: METADATA
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	propertyPath	属性パス	no	string	1	発生したエラーの位置
Sample
成功した場合
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/inventories/bulk-upsert' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "inventories": [
        {
            "manageNumber": "mng1234",
            "variantId": "sku1",
            "mode": "ABSOLUTE",
            "quantity": 70
        },
        {
            "manageNumber": "mng1234",
            "variantId": "sku2",
            "mode": "RELATIVE",
            "quantity": 3
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5",
            "mode": "RELATIVE",
            "quantity": -2
        }
    ]
}'
Response (Status: 204 No Content)
失敗した場合
Request (curl コマンドを使った例)
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/inventories/bulk-upsert' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "inventories": [
        {
            "manageNumber": "12345678901234567890123456789012345678901",
            "variantId": "sku3",
            "mode": "ABSOLUTE",
            "quantity": 70
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
