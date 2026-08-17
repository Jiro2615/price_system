RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inventoryapi2_1/inventories_variant-lists_get/
サービス: 在庫API 2.1（InventoryAPI 2.1）

サービス一覧へ戻る / InventoryAPI 2.1

RMS WEB SERVICE : inventories.variant-lists.get
Overview
この機能を利用すると、商品管理番号を指定し、在庫情報として保持している全てのSKU管理番号を取得することができます。
※この機能は、2024年6月13日にリリース予定です。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.1/inventories/variant-lists/manage-numbers/{manageNumber}	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	manageNumber	商品管理番号	yes	string	32	1	1件のみ指定可能。
以下の英数字、記号が使用可能。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_" 
大文字は小文字に自動変換。
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
1	manageNumber	商品管理番号	yes	string	1	以下の英数字、記号。
・"a~z"
・"0~9"
・"-", "_" 
2	variantList	SKU管理番号のリスト	yes	list<string>	1..n	以下の英数字、記号。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_" 
3	created	登録日時	yes	string 	1	在庫情報の初回登録日時

フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。
4	updated	更新日時	yes	string	1	在庫情報の更新日時

フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。


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
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.1/inventories/variant-lists/manage-numbers/Mng1234' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "manageNumber": "mng1234",
    "variantList": [
        "sku-1",
        "sku-2",
        "sku-3",
    ],
    "created": "2024-02-21T10:00:00+09:00",
    "updated": "2024-03-01T10:30:00+09:00"
}
失敗した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.1/inventories/variant-lists/manage-numbers/mng_1234' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 404 Not Found)
{
    "errors": [
        {
            "code": "GE0014",
            "message": "Not found for inputs; manageNumber=mng_1234"
        }
    ]
}
