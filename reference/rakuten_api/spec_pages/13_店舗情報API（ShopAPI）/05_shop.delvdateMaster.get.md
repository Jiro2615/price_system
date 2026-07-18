RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/shopapi/delvdatemaster/
サービス: 店舗情報API（ShopAPI）

サービス一覧へ戻る / ShopAPI

RMS WEB SERVICE : shop.delvdateMaster.get
Overview
この機能を利用すると、納期情報設定の情報を取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/shop/delvdateMaster	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/xml; charset=UTF-8
Query Parameters
No	Parameter	Description	Type	Required	Note
1	delvdateNumber	納期管理番号		String	No	指定したdelvdateNumberの情報を取得します。指定しない場合はすべての納期情報設定の情報を取得します。
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
No	Element	Description	Type	Max byte	Not Null	Note
1	resultCode	結果コード	String	4	Yes	
2	resultMessageList	メッセージ一覧	resultMessageList	-	Yes	
3	result	取得データ本体	naviButtonInfoBizModel	-	No	
Level 2: resultMessageList
No	Element	Description	Type	Max byte	Not Null	Note
1	resultMessage	メッセージ	resultMessage	-	Yes	
Level 3: resultMessage
No	Element	Description	Type	Max byte	Not Null	Note
1	code	コード	String	4	Yes	詳細は、ShopAPI Response Codes Reference を参照してください。
2	message	メッセージ	String	-	Yes
Level 2: delvdateMasterBizModel
No	Element	Description	Type	Max byte	Not Null	Note
1	delvdateMasterList	納期情報設定リスト	delvdateMasterList	-	Yes	
Level 3: delvdateMasterList
No	Element	Description	Type	Max byte	Not Null	Note
1	delvdateMaster	納期情報設定	delvdateMaster	-	Yes	
Level 4: delvdateMaster
No	Element	Description	Type	Max byte	Not Null	Note
1	delvdateNumber	納期管理番号	String	30	Yes	
2	delvdateCaption	お届けの目安	String	96	Yes	
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
    <result xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="shopbiz:delvdateMasterBizModel">
        <delvdateMasterList>
            <delvdateMaster>
                <delvdateNumber>0</delvdateNumber>
                <delvdateCaption>testDateCaption</delvdateCaption>
            </delvdateMaster>
            <delvdateMaster>
                <delvdateNumber>1</delvdateNumber>
                <delvdateCaption>当日お届けします。</delvdateCaption>
            </delvdateMaster>
            <delvdateMaster>
                <delvdateNumber>1000</delvdateNumber>
                <delvdateCaption>1〜2日以内に発送予定（店舗休業日を除く）</delvdateCaption>
            </delvdateMaster>
            <delvdateMaster>
                <delvdateNumber>2</delvdateNumber>
                <delvdateCaption>３〜4日でのお届けとなります。</delvdateCaption>
            </delvdateMaster>
            <delvdateMaster>
                <delvdateNumber>3</delvdateNumber>
                <delvdateCaption>一週間前後でのお届けとなります。</delvdateCaption>
            </delvdateMaster>
        </delvdateMasterList>
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
