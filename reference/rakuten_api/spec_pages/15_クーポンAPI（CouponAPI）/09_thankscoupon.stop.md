RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/couponapi/thankscouponstop
サービス: クーポンAPI（CouponAPI）

サービス一覧へ戻る / CouponAPI

RMS WEB SERVICE : thankscoupon.stop

 

この機能を利用すると、サンキュークーポンを停止することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method


https://api.rms.rakuten.co.jp/es/1.0/thankscoupon/{thanksCouponId}/issuestatus/stop

	PUT
Request
HTTP Header
No	Key	Value	Mandatory	 Note
1	

Authorization

	ESA Base64(serviceSecret:licenseKey)	○	





2	Accept	application/xml	
	

Query parameters

 None

Path parameters
No	Parameter	Description	Type	Mandatory	Note
1	thanksCouponId	サンキュークーポンID	int	○	

HTTP Body

  None

Request Sample


request example (normal case)
Authorization: ESA UHl3VDJIcU9JSEZQaFJETjpKTm9oeVloMTBhVjNveUpj
Accept: application/xml
https://{server}/{context}/1.0/thankscoupon/18493/issuestatus/stop



Response
HTTP Header
No	Key	Value
1	Content-Type	application/xml
2	Status	200 (OK) → 通常ケース
400 (BAD REQUEST) → リクエストパラメータエラー
401 (AUTH ERROR) → 認証エラー
403 (MAX_QPS_OVER, MAX_QPM_OVER, MAX_CONNECTION_OVER) → リクエスト閾値エラー
404 (NOT FOUND) → データが存在しないエラー
405 (METHOD NOT ALLOWED) → 許可されていないHTTPメソッドエラー
500 (INTERNAL SERVER ERROR) → 予期せぬエラー
503 (API MAINTENANCE) → システムエラー

HTTP Body
XML:result
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	result.errors	エラー情報リスト	XML:errors	-	0,1	エラー発生時のみ返却
2	result.thanksCoupon	サンキュークーポン情報	XML:thanksCoupon	-	0,1	

XML:errors
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	errors.error	エラー情報	XML:error	-	1..n	

XML:error
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	error.code	エラーコード	String	-	1	詳細は、 Thanks Coupon Response Codes Reference を参照
2	error.message	エラーメッセージ	String	-	1	詳細は、 Thanks Coupon Response Codes Reference を参照
XML:thanksCoupon
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	thanksCoupon.thanksCouponId	サンキュークーポンID	int	4	1	最大桁数：10
Response Sample


response example(normal case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <thanksCoupon>
        <thanksCouponId>20458</thanksCouponId>
    </thanksCoupon>
</result>





response example(error case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <errors>
        <error>
            <code>COUPON_EE100-002</code>
            <message>thanksCouponStop.over_term</message>
        </error>
    </errors>
</result>
