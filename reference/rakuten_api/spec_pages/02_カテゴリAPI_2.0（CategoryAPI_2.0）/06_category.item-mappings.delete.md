RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/categoryapi2/deleteitemmapping/
サービス: カテゴリAPI 2.0（CategoryAPI 2.0）

サービス一覧へ戻る / CategoryAPI 2.0

RMS WEB SERVICE : category.item-mappings.delete
Overview
この機能を利用すると、指定した商品管理番号を表示先カテゴリから削除することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/categories/item-mappings/manage-numbers/{manageNumber}	DELETE
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	manageNumber	商品管理番号	yes	string	32	1	以下の英数字、記号が使用可能。
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
None


失敗した場合
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
L1	L2
1	errors	エラー	yes	List<error>	1..n	エラーのリスト
2		code	コード	yes	string	1	メッセージコードの一覧はこちら
3		message	メッセージ	yes	string	1
Sample
成功した場合
Request (curl コマンドを使った例)
curl --location --request DELETE 'https://api.rms.rakuten.co.jp/es/2.0/categories/item-mappings/manage-numbers/mng123' \
--header 'Authorization: ESA xxx' --header 'Content-Type: application/json'
Response in JSON format (Status: 204 No Content)
失敗した場合
Request (curl コマンドを使った例)
curl --location --request DELETE 'https://api.rms.rakuten.co.jp/es/2.0/categories/item-mappings/manage-numbers/012345678901234567890123456789012' \
--header 'Authorization: ESA xxx' --header 'Content-Type: application/json'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0004",
            "message": "Max length of manageNumber must be within 32 bytes."
        }
    ]
}
