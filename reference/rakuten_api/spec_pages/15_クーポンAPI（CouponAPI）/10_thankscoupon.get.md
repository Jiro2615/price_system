RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/couponapi/thankscouponget
サービス: クーポンAPI（CouponAPI）

サービス一覧へ戻る / CouponAPI

RMS WEB SERVICE : thankscoupon.get
この機能を利用すると、サンキュークーポンIDを指定して該当するサンキュークーポン情報を取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/thankscoupon/{thanksCouponId}	GET
Request
HTTP Header
No	Key	Value	Mandatory	Note
1	Authorization	ESA Base64(serviceSecret:licenseKey)	○	
2	Accept	application/xml		
Query parameters
None

Path parameters
No	Parameter	Description	Type	Mandatory	Note
1	thanksCouponId	サンキュークーポンID	int	○	
HTTP Body
None

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
1	error.code	エラーコード	String	-	1	詳細は、Thanks Coupon Response Codes Referenceを参照
2	error.message	エラーメッセージ	String	-	1	詳細は、Thanks Coupon Response Codes Referenceを参照
XML:thanksCoupon
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	thanksCoupon.thanksCouponId	サンキュークーポンID	int	4	1	最大桁数：10
2	thanksCoupon.shopId	店舗ID	String	20	1	
3	thanksCoupon.shopName	店舗名	String	765	1	
4	thanksCoupon.shopUrl	店舗URL	String	20	1	
5	thanksCoupon.couponImage	サンキュークーポン画像	String	-	1	
6	thanksCoupon.couponName	サンキュークーポン名	String	60	1	
7	thanksCoupon.couponCaption	サンキュークーポン詳細説明文	String	200	0,1	
8	thanksCoupon.discountType	値引きプラン	int	4	1	1： 定額値引き
2： 定率値引き
9	thanksCoupon.discountFactor	割引因子	int	4	1	discountTypeによって、値が異なります。

discountType	discountFactor
1	1 ～ 999999999： 割引額
2	1 ～ 99： 割引率


10	thanksCoupon.couponUnavailableTerm	サンキュークーポンが有効になるまでの期間	int	4	1	10~30(日数）
11	thanksCoupon.couponTerm	サンキュークーポン有効期間	int	4	1	1~3(月数）
12	thanksCoupon.pcRedirectUrl	リダイレクトURL（PC）	String	-	1	
13	thanksCoupon.memberAvailMaxCount	1ユーザあたりの利用回数上限	int	4	1	最大桁数：6
14	thanksCoupon.combineFlag	併用可否フラグ	int	4	1	0： 併用不可
1： 併用可
15	thanksCoupon.issueStatus	獲得ステータス	int	4	1	3: 期間前
4: 期間中
5: 停止
6: 終了
16	thanksCoupon.regDate	登録日時	dateTime	-	1	
17	thanksCoupon.lastUpdateDate	最終更新日時	dateTime	-	1	
18	thanksCoupon.thanksOtherConditions	サンキュークーポンその他条件リスト	XML:thanksOtherConditions	-	1	
19	thanksCoupon.thanksAutoGetConditions	サンキュークーポン獲得条件リスト	XML:thanksAutoGetConditions	-	1	
XML:thanksOtherConditions
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	thanksOtherConditions.thanksOtherCondition	サンキュークーポンその他条件	XML:thanksOtherCondition	-	1..n	
XML:thanksOtherCondition
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	thanksOtherCondition.conditionTypeCode	その他条件コード	String	-	1	RS002： 販売方法
RS003： 利用金額
2	thanksOtherCondition.startValue	開始値	String	-	1	conditionTypeCodeによって、値が異なります。

conditionTypeCode	startValue
RS002	0： 通常購入
1： 定期購入
99： 通常＆定期購入
RS003	1 ～ 999999999： 利用金額


XML:thanksAutoGetConditions
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	thanksAutoGetConditions.thanksAutoGetCondition	サンキュークーポン獲得条件	XML:thanksAutoGetCondition	-	2,3	
XML:thanksAutoGetCondition
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	thanksAutoGetCondition.getCondCd	条件タイプ	String	-	1	totalPrice： クーポン獲得金額条件
grantTerm： クーポン獲得期間
serviceUseHistory： 初回購入ユーザー限定
2	thanksAutoGetCondition.startValue	開始値	String	-	1	getCondCdがtotalPriceの場合、クーポン獲得金額
getCondCdがgrantTermの場合、クーポン獲得期間の開始日時
getCondCdがserviceUseHistoryの場合、1
3	thanksAutoGetCondition.endValue	終了値	String	-	0,1	getCondCdがgrantTermの場合、クーポン獲得期間の終了日時
getCondCdがserviceUseHistoryの場合、0
4	thanksAutoGetCondition.compOperatorCd	比較演算子コード	int	4	1	getCondCdがtotalPriceの場合、1
getCondCdがgrantTermの場合、1
getCondCdがserviceUseHistoryの場合、0
※1　リクエスト結果が存在しない場合は「404 Not Found」がHeaderのStatusに返却されます。
※2　useCountとgetCountはレスポンスに含まれません。これらはthanksCoupon.searchでのみ表示される値です。
※3　couponCaption等の任意項目が空の場合はレスポンスに含まれません。

Response Sample
response example (normal case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <thanksCoupon>
        <thanksCouponId>20494</thanksCouponId>
        <shopId>500300</shopId>
        <shopName>デモショップ_001</shopName>
        <shopUrl>https://www.rakuten.co.jp/demoshop_001</shopUrl>
        <couponImage>https://image.rakuten.co.jp/demoshop_001/logo/logo1.jpg</couponImage>
        <couponName>test thanks coupon August</couponName>
        <discountType>1</discountType>
        <discountFactor>2000</discountFactor>
        <couponUnavailableTerm>10</couponUnavailableTerm>
        <couponTerm>1</couponTerm>
        <pcRedirectUrl>https://www.rakuten.co.jp/demoshop_001</pcRedirectUrl>
        <memberAvailMaxCount>1</memberAvailMaxCount>
        <combineFlag>1</combineFlag>
        <issueStatus>3</issueStatus>
        <regDate>2017-07-19T09:22:08+09:00</regDate>
        <lastUpdateDate>2017-07-19T09:22:08+09:00</lastUpdateDate>
        <thanksOtherConditions>
            <thanksOtherCondition>
                <conditionTypeCode>RS002</conditionTypeCode>
                <startValue>99</startValue>
            </thanksOtherCondition>
        </thanksOtherConditions>
        <thanksAutoGetConditions>
            <thanksAutoGetCondition>
                <getCondCd>grantTerm</getCondCd>
                <startValue>2017-10-25 19:00:00</startValue>
                <endValue>2017-10-26 23:59:59</endValue>
                <compOperatorCd>1</compOperatorCd>
            </thanksAutoGetCondition>
            <thanksAutoGetCondition>
                <getCondCd>serviceUseHistory</getCondCd>
                <startValue>1</startValue>
                <endValue>0</endValue>
                <compOperatorCd>0</compOperatorCd>
            </thanksAutoGetCondition>
            <thanksAutoGetCondition>
                <getCondCd>totalPrice</getCondCd>
                <startValue>2000</startValue>
                <compOperatorCd>1</compOperatorCd>
            </thanksAutoGetCondition>
        </thanksAutoGetConditions>
    </thanksCoupon>
</result>
