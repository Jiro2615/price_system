RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/couponapi/coupondelete
サービス: クーポンAPI（CouponAPI）

サービス一覧へ戻る / CouponAPI


RMS WEB SERVICE : coupon.delete

 

この機能を利用すると、クーポン情報を削除することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/coupon/delete	POST
Request
HTTP Header
No	Key	Value	Note
1	Authorization	ESA Base64(serviceSecret:licenseKey)	
Query parameters

　None

HTTP Body
XML:request
No	Element	Description	Type	
Size(byte)
	
Mandatory
	
Multiplicity
	
Note　　　

1	request.couponDeleteRequest	クーポン情報削除要求	

XML:couponDeleteRequest

	-	○	1	
XML:couponDeleteRequest
No	Element	Description　　	Type　　	
Size(byte)
	Mandatory	Multiplicity	Note　　　
1	couponDeleteRequest.coupon	クーポン情報	

XML:coupon

	-	○	1	
XML:coupon
No	Element	Description	Type	
Size(byte)
	Mandatory	Multiplicity	Note
1	coupon.couponCode	クーポンコード	String	19	○	1	
Request Sample


request example (normal case)
<?xml version="1.0" encoding="UTF-8"?>
<request>
    <couponDeleteRequest>
        <coupon>
            <couponCode>CNHZ-FAFS-M7IA-8N9L</couponCode>
        </coupon>
    </couponDeleteRequest>
</request>


Response
HTTP Header
No	Key	Value
1	Content-Type	text/xml
HTTP Body
XML:result
No	Element	Description	Type	

Size(byte)

	

Multiplicity

	Note
1	

result.status

	ステータス	XML:status	-	1	

interfaceId = coupon.delete


2	

result.errors

	

エラー情報リスト

	XML:errors	-	0,1	

エラー発生時のみ返却されます


3	result.coupon	クーポン情報	XML:coupon	-
	0,1
	
XML:errors
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	errors.error	エラー情報	XML:error	-	1..n	
XML:error
No	Element	

Description　　　

	

Type    　　


	Size(byte)	

Multiplicity

	Note
1	error.code	エラーコード	String	-	1	詳細は、CouponAPI Response Codes Referenceを参照してください。
2	error.message	エラーメッセージ	String	-	1	詳細は、CouponAPI Response Codes Referenceを参照してください。
XML:coupon
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	coupon.couponCode	クーポンコード	String	19	1	
Response Sample


response example (normal case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <status>
        <interfaceId>coupon.delete</interfaceId>
        <systemStatus>OK</systemStatus>
        <message>OK</message>
        <requestId>714a4983-555f-42d9-aeea-89dae89f2f55</requestId>
    </status>
    <coupon>
        <couponCode>CNHZ-FAFS-M7IA-8N9L</couponCode>
    </coupon>
</result>
response example (error case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
     <status>
        <interfaceId>coupon.delete</interfaceId>
        <systemStatus>OK</systemStatus>
        <message>OK</message>
        <requestId>714a4983-555f-42d9-aeea-89dae89f2f55</requestId>
    </status>
    <errors>
        <error>
            <code>COUPON_E030-002</code>
            <message>couponCode.out_of_bounds</message>
        </error>
    </errors>
</result>
