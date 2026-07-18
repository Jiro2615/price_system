RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inventoryapi2/deleteinventory
サービス: 在庫API 2.0（InventoryAPI 2.0）

サービス一覧へ戻る / InventoryAPI 2.0

RMS WEB SERVICE : inventories.variants.delete
Overview
この機能を利用すると、商品管理番号とSKU管理番号を指定し、在庫情報を削除することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/inventories/manage-numbers/{manageNumber}/variants/{variantId}	DELETE
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	manageNumber	商品管理番号	yes	string	32	1	以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0-9"
・"-", "_"
大文字は小文字に自動変換。
2	variantId	SKU管理番号	yes	string	32	1	以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0-9"
・"-", "_"
大文字・小文字は、異なる文字として扱う。
HTTP Body
なし

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
Level 2: error
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
1	code	コード	yes	string	1	メッセージコードの一覧はこちら
2	message	メッセージ	yes	string	1
Sample
成功した場合
Request (curl コマンドを使った例)
curl --location --request DELETE 'https://api.rms.rakuten.co.jp/es/2.0/inventories/manage-numbers/mng1234/variants/sku1' \
--header 'Authorization: ESA xxx' --header 'Content-Type: application/json'
Response (Status: 204 No Content)
失敗した場合
Request (curl コマンドを使った例)
curl --location --request DELETE 'https://api.rms.rakuten.co.jp/es/2.0/inventories/manage-numbers/mng1234/variants/sku2' \
--header 'Authorization: ESA xxx'--header 'Content-Type: application/json'
Response in JSON format (Status: 404 Not Found)
{
    "errors": [
        {
            "code": "GE0014",
            "message": "Not found for inputs; manageNumber=mng123, variantId=sku2"
        }
    ]
}
