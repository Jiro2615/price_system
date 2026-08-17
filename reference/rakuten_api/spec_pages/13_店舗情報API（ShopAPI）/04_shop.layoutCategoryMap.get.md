RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/shopapi/layoutcategorymapget/
サービス: 店舗情報API（ShopAPI）

サービス一覧へ戻る / ShopAPI

RMS WEB SERVICE : shop.layoutCategoryMap.get
Overview

この機能を利用すると、カテゴリページ表示項目並び順の情報を取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method


https://api.rms.rakuten.co.jp/es/1.0/shop/layoutCategoryMap

	GET
Request
HTTP Header
No	Key	Value
1	

Authorization

	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/xml; charset=UTF-8
Query Parameters
No	Parameter	Description	Type	Required	Note
1	categoryMapId	カテゴリページ並び順テンプレートID	Integer	No	指定した categoryMapId の情報を取得します。
指定しない場合はすべてのテンプレートを取得します。
HTTP Body

None

Response
HTTP Header
No	Key	Value
1	content-type	application/xml; charset=UTF-8
2	x-request-id	UUID形式
※API requestを特定する一意のIDです。問題発生時のお問い合わせの際にご連絡いただくと調査がスムーズになります。
3	Timestamp	アクセス時のタイムスタンプ
※問題発生時のお問い合わせの際にご連絡いただくと調査がスムーズになります。
HTTP Body
Level 1: shopBizApiResponse
No	Element	Description	Type	Max Byte	Not Null	Note
1	resultCode	結果コード	String	4	Yes	
2	resultMessageList	メッセージ一覧	resultMessageList	-	Yes	
3	result	取得データ本体	layoutCategoryMapBizModel	-	No	
Level 2: resultMessageList
No	Element	Description	Type	Max Byte	Not Null	Note
1	resultMessage	メッセージ	resultMessage	-	Yes	
Level 3: resultMessage
No	Element	Description	Type	Max Byte	Not Null	Note
1	code	コード	String	4	Yes	詳細は、ShopAPI Response Codes Referenceを参照してください。
2	message	メッセージ	String	-	Yes
Level 2: layoutCategoryMapBizModel
No	Element	Description	Type	Max Byte	Not Null	Note
1	layoutCategoryMapList	カテゴリページ表示項目並び順リスト	layoutCategoryMapList	-	Yes	
Level 3: layoutCategoryMapList
No	Element	Description	Type	Max Byte	Not Null	Note
1	layoutCategoryMap	カテゴリページ表示項目並び順	layoutCategoryMap	-	Yes	
Level 4: layoutCategoryMap
No	Element	Description	Type	Max Byte	Not Null	Note
1	categoryMapId	カテゴリページ並び順テンプレートID	Integer	10	No	
2	name	テンプレート名	String	90	No	
3	defaultFlag	テンプレート自動選択	Short	5	No	0: 自動選択しない
1: 自動選択対象
4	lastUpdate	更新日時	Date	-	No	
Response Sample
response example (normal case)
<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
    <resultCode>N000</resultCode>
    <resultMessageList>
        <resultMessage>
            <code>N000</code>
            <message>Succeeded.</message>
        </resultMessage>
    </resultMessageList>
    <result xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="shopbiz:layoutCategoryMapBizModel">
        <layoutCategoryMapList>
            <layoutCategoryMap>
                <categoryMapId>30740</categoryMapId>
                <name>カテゴリページの並び順01</name>
                <defaultFlag>1</defaultFlag>
                <lastUpdate>2016-10-13T11:40:12+09:00</lastUpdate>
            </layoutCategoryMap>
        </layoutCategoryMapList>
    </result>
</shopbiz:shopBizApiResponse>

 

 

response example (error case)
<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
    <resultCode>E999</resultCode>
    <resultMessageList>
        <resultMessage>
            <code>E999</code>
            <message>Unknown Execution error.</message>
        </resultMessage>
    </resultMessageList>
</shopbiz:shopBizApiResponse>
