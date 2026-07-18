RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/couponapi/thankscouponupdate
サービス: クーポンAPI（CouponAPI）

サービス一覧へ戻る / CouponAPI

RMS WEB SERVICE : thankscoupon.update
この機能を利用すると、サンキュークーポン情報を更新することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/thankscoupon/{thanksCouponId}	PUT
Request
HTTP Header
No	Key	Value	Mandatory	 Note
1	Authorization	ESA Base64(serviceSecret:licenseKey)	○	
2	Accept	application/xml		
Query parameters
None

Path parameters
No	Parameter	Description	Type	Mandatory	Note
1	thanksCouponId	サンキュークーポンID	int	○	
HTTP Body
XML:request
No	Parameter	Description	Type	Mandatory	Multiplicity	Note
1	request.thanksCoupon	サンキュークーポン情報	XML:thanksCoupon	○	1	
XML:thanksCoupon
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	thanksCoupon.couponImage	サンキュークーポン画像	String	-		0,1	画像のURLは
https://image.rakuten.co.jp/ +shopUrl+ /cabinet/ で始まり、
かつ
対応している画像URLの拡張子が jpg, jpeg, gif,pngの4つです。

文字列の前後にある全半角空白、タブの削除をして、半角カナを全角カナに変換します。

（クーポン画像はサンキュークーポンのみ更新可能。配信型クーポンでは更新不可）
2	thanksCoupon.couponName	サンキュークーポン名	String	60	○	1	不正な文字
　・半全角スペース、タブのみ
　・機種依存文字
　・EUC_JPの 補助漢字に入る 文字、もしくはUTF-8 -> EUC_JPに変換出来ない文字

文字列の前後にある全半角空白、タブの削除をして、半角カナを全角カナに変換します。
3	thanksCoupon.couponCaption	サンキュークーポン詳細説明文	String	200		0,1	不正な文字
　・機種依存文字

文字列の前後にある全半角空白、タブの削除をして、半角カナを全角カナに変換します。
4	thanksCoupon.discountType	値引きプラン	int	4	○	1	1： 定額値引き
2： 定率値引き

全角数字を自動的に半角数字に変換します。
5	thanksCoupon.discountFactor	割引因子	int	4	○	1	discountTypeによって、値が異なります。

discountType	discountFactor
1	1 ～ 999999999： 値引き額
2	1 ～ 99： 値引き率

全角数字を自動的に半角数字に変換します。
6	thanksCoupon.couponUnavailableTerm	サンキュークーポンが有効になるまでの期間	int	4	○	1	半角英数10~30(日数）まで

全角数字を自動的に半角数字に変換します。
7	thanksCoupon.couponTerm	サンキュークーポン有効期間	int	4	○	1	半角英数1~3まで(月数）

全角数字を自動的に半角数字に変換します。
8	thanksCoupon.memberAvailMaxCount	1ユーザあたりの利用回数上限	int	4	○	1	最大桁数：6

※0を指定した場合、無制限となります。

初回購入ユーザー限定指定の場合、1のみ設定可能。

全角数字を自動的に半角数字に変換します。
9	thanksCoupon.combineFlag	併用可否フラグ	int	4	○	1	0： 併用不可
1： 併用可﻿

全角数字を自動的に半角数字に変換します。
10	thanksCoupon.thanksOtherConditions	サンキュークーポンその他条件リスト	XML:thanksOtherConditions	-		0,1	
11	thanksCoupon.thanksAutoGetConditions	サンキュークーポン獲得条件リスト	XML:thanksAutoGetConditions	-	○	1	
XML:thanksOtherConditions
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	thanksOtherConditions.thanksOtherCondition	サンキュークーポンその他条件	XML:thanksOtherCondition	-		0,1	
XML:thanksOtherCondition
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	thanksOtherCondition.conditionTypeCode	その他条件コード	String	-	○	1	RS002： 販売方法（設定のない場合は自動的に設定される）
RS003： 利用金額
2	thanksOtherCondition.startValue	開始値	String	-	○	1	conditionTypeCodeによって、値が異なります。

conditionTypeCode	startValue
RS002	0： 通常購入
1： 定期購入
99： 通常＆定期購入（設定のない場合は自動的に設定される）
RS003	1 ～ 999999999： 利用金額


XML:thanksAutoGetConditions
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	thanksAutoGetConditions.thanksAutoGetCondition	サンキュークーポン獲得条件	XML:thanksAutoGetCondition	-	○	2,3	
XML:thanksAutoGetCondition
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	thanksAutoGetCondition.getCondCd	条件タイプ	String	-	○	1	totalPrice： クーポン獲得金額条件（必須項目）
grantTerm： クーポン獲得期間（必須項目）
serviceUseHistory： 初回購入ユーザー限定（任意項目）
2	thanksAutoGetCondition.startValue	開始値	String	-	○	1	getCondCdがtotalPriceの場合、クーポン獲得金額。半角数字9文字以内

getCondCdがgrantTermの場合、クーポン獲得期間の開始日時
・YYYY-MM-DD hh:mm:ss+09:00
・登録日から最短2日後以降指定可能
・登録日から最長6ヶ月以内指定可能
・日付、時間、分単位のみ考慮され、秒単位は無視される

getCondCdがserviceUseHistoryの場合、1のみ指定可能

「獲得対象ユーザ」の設定が同一の場合、獲得期間が重複したクーポンは登録できません。重複している場合は、登録済みクーポンを停止するか、獲得期間を変更してから、再度登録をおこなってください。
3	thanksAutoGetCondition.endValue	終了値	String	-		0,1	getCondCdがtotalPriceの場合、必要なし。値が入っていれば無視される

getCondCdがgrantTermの場合、クーポン獲得期間の終了日時
・YYYY-MM-DD hh:mm:ss+09:00
・クーポン獲得開始日時から最短5分後以降指定可能
・クーポン獲得開始日時から最長36ヶ月以内指定可能
・日付、時間、分単位のみ考慮され、秒単位は無視される

getCondCdがserviceUseHistoryの場合、0のみ指定可能

「獲得対象ユーザ」の設定が同一の場合、獲得期間が重複したクーポンは登録できません。重複している場合は、登録済みクーポンを停止するか、獲得期間を変更してから、再度登録をおこなってください。
4	thanksAutoGetCondition.compOperatorCd	比較演算子コード	int	4	○	1	getCondCdがtotalPriceの場合、1のみ指定可能
getCondCdがgrantTermの場合、1のみ指定可能
getCondCdがserviceUseHistoryの場合、0のみ指定可能

全角数字を自動的に半角数字に変換します。

Request Sample
request example (normal case)
<?xml version="1.0" encoding="UTF-8"?>
<request>
    <thanksCoupon>
        <couponName>test thanks coupon Oct 2</couponName>
        <discountType>1</discountType>
        <discountFactor>2000</discountFactor>
        <couponUnavailableTerm>10</couponUnavailableTerm>
        <couponTerm>1</couponTerm>
        <memberAvailMaxCount>1</memberAvailMaxCount>
        <combineFlag>1</combineFlag>
        <thanksOtherConditions>
            <thanksOtherCondition>
                <conditionTypeCode>RS003</conditionTypeCode>
                <startValue>10900</startValue>
            </thanksOtherCondition>
        </thanksOtherConditions>
        <thanksAutoGetConditions>
            <thanksAutoGetCondition>
                <getCondCd>grantTerm</getCondCd>
                <startValue>2017-10-01 19:00:00</startValue>
                <endValue>2017-10-02 23:59:59</endValue>
                <compOperatorCd>1</compOperatorCd>
            </thanksAutoGetCondition>
            <thanksAutoGetCondition>
                <getCondCd>totalPrice</getCondCd>
                <startValue>2000</startValue>
                <compOperatorCd>1</compOperatorCd>
            </thanksAutoGetCondition>
            <thanksAutoGetCondition>
                <getCondCd>serviceUseHistory</getCondCd>
                <startValue>1</startValue>
                <endValue>0</endValue>
                <compOperatorCd>0</compOperatorCd>
            </thanksAutoGetCondition>
        </thanksAutoGetConditions>
    </thanksCoupon>
</request>
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
1	error.code	エラーコード	String	-	1	詳細は、 Thanks Coupon Response Codes Reference を参照
2	error.message	エラーメッセージ	String	-	1	詳細は、 Thanks Coupon Response Codes Reference を参照
XML:thanksCoupon
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	thanksCoupon.thanksCouponId	サンキュークーポンID	int	4	1	最大桁数：10
Response Sample
response example (normal case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <thanksCoupon>
        <thanksCouponId>20496</thanksCouponId>
    </thanksCoupon>
</result>
response example (error case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <errors>
        <error>
            <code>COUPON_EE101_001</code>
            <message>thanksOtherConditions.invalid_value</message>
        </error>
    </errors>
</result>
