RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itemapi2_0/itemsinventory-related-settingsget/
サービス: 商品API 2.0（ItemAPI 2.0）

サービス一覧へ戻る / ItemAPI 2.0

RMS WEB SERVICE : items.inventory-related-settings.get
Overview
この機能を利用すると、商品管理番号を指定し、納期に関する設定などを取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/items/inventory-related-settings/manage-numbers/{manageNumber}	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	manageNumber	商品管理番号	yes	string	32	1	1件のみ指定可能
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

成功した場合

No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
L1	L2	L3
1	unlimitedInventoryFlag	在庫設定なし	yes	boolean	-	1	・true：在庫設定なし
・false：在庫設定あり
2	features	その他設定	yes	object	-	1	
3		inventoryDisplay	在庫数表示	yes	enum	-	1	・DISPLAY_ABSOLUTE_STOCK_COUNT：表示
・HIDDEN_STOCK：非表示
・DISPLAY_LOW_STOCK：残り在庫数表示閾値より小さい場合、△を表示する
4		lowStockThreshold	残り在庫数表示閾値	no	number	-	0,1	許容値：1～20
5	variants	SKU	yes	object	-	1..400	
6		{variantId}	SKU管理番号	yes	string	32	1	以下の英数字、記号。
・"a~z"
・"A~Z"
・"0~9"
・"-", "_" 
7		restockOnCancel	在庫戻しフラグ	no	boolean	-	1	・true：在庫戻しする
・false：在庫戻ししない
8		backOrderFlag	在庫切れ時の注文受付	no	boolean	-	1	・true：注文を受け付ける
・false：注文を受け付けない
9		backOrderDeliveryDateId	在庫切れ時納期管理番号	no	number	-	0,1	
10		normalDeliveryDateId	在庫あり時納期管理番号	no	number	-	0,1	

失敗した場合

No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Decription
L1	L2
1	errors	エラー	yes	List<error>	-	1..n	エラーのリスト。
2		code	コード	yes	string	-	1	メッセージコードの一覧はこちら。
3		message	メッセージ	yes	string	-	1
Sample
成功した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/inventory-related-settings/manage-numbers/mng1234' \
--header 'Authorization: ESA xxx'
Response (Status: 200 OK)
{
    "unlimitedInventoryFlag": false,
    "features": {
        "inventoryDisplay": "DISPLAY_LOW_STOCK",
        "lowStockThreshold": 1
    },
    "variants": {
        "sku1": {
            "restockOnCancel": true,
            "backOrderFlag": false,
            "backOrderDeliveryDateId": 1,
            "normalDeliveryDateId": 1
        },
        "sku2": {
            "restockOnCancel": true,
            "backOrderFlag": false,
            "backOrderDeliveryDateId": 1,
            "normalDeliveryDateId": 1
        }
    }
}
失敗した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/items/inventory-related-settings/manage-numbers/mng123' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 404 Not Found)
{
    "errors": [
        {
            "code": "GE0014",
            "message": "Not found for inputs; manageNumber=mng123"
        }
    ]
}
