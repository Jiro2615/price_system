RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/shopapi/shopstatusget/
サービス: 店舗情報API（ShopAPI）

サービス一覧へ戻る / ShopAPI

RMS WEB SERVICE : shop.shopStatus.get
Overview
この機能を利用すると、特定機能の移行状況や利用状況を確認することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/shop/shopStatus/{statusKey}	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/xml; charset=UTF-8
Path Parameters
No	Key	Value
1	statusKey	socialGiftParticipation: ソーシャルギフト利用申込
Query Parameters
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
3	result	取得データ本体	topDisplayBizModel	-	No	
Level 2: resultMessageList
No	Element	Description	Type	Max Byte	Not Null	Note
1	resultMessage	メッセージ	resultMessage	-	Yes	
Level 3: resultMessage
No	Element	Description	Type	Max Byte	Not Null	Note
1	code	コード	String	4	Yes	詳細は、ShopAPI Response Codes Referenceを参照してください。
2	message	メッセージ	String	-	Yes
Level 2: shopStatusBizModel
No	Element	Description	Type	Max Byte	Not Null	Note
1	shopStatus	店舗ステータス	shopStatus	-	Yes	
Level 3: shopStatus
No	Element	Description	Type	Max Byte	Not Null	Note
1	statusKey	店舗ステータスのキー	String	-	Yes	socialGiftParticipation: ソーシャルギフト利用申込
2	statusValue	店舗ステータスの値	String	-	Yes	



statusKey	statusValue
socialGiftParticipation	・NOT_USE: 未申込み
・IN_USE: 利用中
・UNAVAILABLE: 利用不可



※店舗ステータスの変更が反映されるまで10分程度かかる場合があります。
3	statusUpdateTime	店舗ステータス更新日時	Date	-	No	ISO 8601（YYYY-MM-DDThh:mm:ss±hh:mm）形式です。
"statusKey"に"socialGiftParticipation"が指定されている場合は、この項目自体がレスポンスされません。
4	startTime	開始日時	Date	-	No	ISO 8601（YYYY-MM-DDThh:mm:ss±hh:mm）形式です。
"statusKey"に"socialGiftParticipation"が指定されている場合は、この項目自体がレスポンスされません。
Response Sample
response example (statusKey is socialGiftParticipation and statusValue is NOT_USE)
<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse
  xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
  <resultCode>N000</resultCode>
  <resultMessageList>
    <resultMessage>
      <code>N000</code>
      <message>Succeeded.</message>
    </resultMessage>
  </resultMessageList>
  <result xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="shopbiz:shopStatusBizModel">
    <shopStatus>
        <statusKey>socialGiftParticipation</statusKey>
        <statusValue>NOT_USE</statusValue>
      </shopStatus>
  </result>
</shopbiz:shopBizApiResponse>
response example (statusKey is socialGiftParticipation and statusValue is IN_USE)
<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse
  xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
  <resultCode>N000</resultCode>
  <resultMessageList>
    <resultMessage>
      <code>N000</code>
      <message>Succeeded.</message>
    </resultMessage>
  </resultMessageList>
  <result xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="shopbiz:shopStatusBizModel">
    <shopStatus>
        <statusKey>socialGiftParticipation</statusKey>
        <statusValue>IN_USE</statusValue>
      </shopStatus>
  </result>
</shopbiz:shopBizApiResponse>
response example (statusKey is invalid)
<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse 
  xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
  <resultCode>C003</resultCode>
  <resultMessageList>
    <resultMessage>
      <code>C003</code>
      <message>Requested resource is not found.</message>
    </resultMessage>
  </resultMessageList>
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
