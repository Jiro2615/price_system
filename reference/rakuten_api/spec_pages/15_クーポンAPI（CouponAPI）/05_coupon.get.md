RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/couponapi/couponget
サービス: クーポンAPI（CouponAPI）

サービス一覧へ戻る / CouponAPI

RMS WEB SERVICE : coupon.get
この機能を利用すると、クーポンコードを指定して該当するクーポン情報を取得することができます。



Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/coupon/get		GET
Request
HTTP Header
No	Key	Value	Note
1	Authorization	ESA Base64(serviceSecret:licenseKey)	
Query parameters
No	Parameter	Description	Type	Mandatory	Multiplicity	Note
1	couponCode	クーポンコード	String	○	1	
HTTP Body
None

Response
HTTP Header
No	Key	Value
1	Content-Type	text/xml
HTTP Body
XML: result
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	result.status	ステータス情報	XML:status	-	1	interfaceId = coupon.get
2	result.errors	エラー情報リスト	XML:errors	-	0,1	エラー発生時のみ返却されます
3	result.coupon	クーポン情報	XML:coupon	-	0,1	
XML: errors
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	errors.error	エラー情報	XML:error	-	1..n	
XML: error
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	error.code	エラーコード	String	-	1	詳細は、 CouponAPI Response Codes Reference を参照してください。
2	error.message	エラーメッセージ	String	-	1	詳細は、 CouponAPI Response Codes Reference を参照してください。
XML: coupon
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	coupon.couponCode	クーポンコード	String	19	1	
2	coupon.couponName	クーポン名	String	60	1	
3	coupon.couponCaption	クーポン詳細説明文	String	200	0,1	
4	coupon.couponStartDate	クーポン有効期間（開始日時）	dateTime	-	1	YYYY-MM-DDThh:mm:ss+09:00
5	coupon.couponEndDate	クーポン有効期間（終了日時）	dateTime	-	1	YYYY-MM-DDThh:mm:ss+09:00
6	coupon.shopId	店舗ID	String	20	1	
7	coupon.shopUrl	店舗URL	String	20	1	
8	coupon.shopName	店舗名	String	765	1	
9	coupon.couponImage	クーポン画像	String	-	1	
10	coupon.pcGetUrl	取得URL (PC)	String	-	1	
11	coupon.issueCount	クーポンの全利用回数上限	int	4	1	
12	coupon.availCount	利用数	int	4	1	
13	coupon.itemType	商品タイプ	int	4	1	1： 単一商品
3： 複数商品
4： 受注
5： 送料無料
14	coupon.discountType	値引きプラン	int	4	1	1： 定額値引き
2： 定率値引き
4： 送料無料
15	coupon.discountFactor	割引因子	int	4	1	discountTypeによって、値が異なります。



discountType	discountFactor
1	1 ～ 999999999： 値引き額
2	1 ～ 99： 値引き率
4	1： 送料無料




16	coupon.memberAvailMaxCount	1ユーザあたりの利用回数上限	int	4	1	
17	coupon.purchaseHistoryCond	購入履歴条件	XML:purchaseHistoryCond	-	1	
18	coupon.multiRankCond	複数会員ランク条件	XML:multiRankCond	-	1	
19	coupon.genderCond	性別条件	String	32	1	NONE: 指定なし
MALE: 男性
FEMALE: 女性
20	coupon.ageRangeCond	年齢条件	XML:ageRangeCond	-	1	
21	coupon.birthmonthCond	誕生月条件	int	4	1	0: 指定なし
1 - 12: 誕生月
22	coupon.multiPrefectureCond	居住地条件	List<XML:multiPrefectureCond>	-	1	
23	coupon.pcRedirectUrl	リダイレクトURL（PC）	String	-	1	
24	coupon.combineFlag	併用可否フラグ	int	4	1	0： 併用不可
1： 併用可
25	coupon.displayFlag	公開設定フラグ	int	4	1	0： 限定公開（クーポン獲得URLを配布）
1： 全ユーザに公開
26	coupon.couponStatus	クーポンステータス	int	4	1	3： 本発行
6： 終了
27	coupon.regDate	登録日時	dateTime	-	1	
28	coupon.lastUpdateDate	最終更新日時	dateTime	-	1	
29	coupon.items	対象商品リスト	XML:items	-	0,1	
30	coupon.otherConditions	その他条件リスト	XML:otherConditions	-	1	
XML: multiRankCond
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	multiRankCond.couponCode	会員ランク条件	int	4	1..5	0： 条件なし
1： レギュラー
2： シルバー
3： ゴールド
4： プラチナ
5： ダイヤモンド
XML: purchaseHistoryCond
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	purchaseHistoryCond.type	購入履歴条件の種別	int	4	1	0: 指定なし
1: 購入履歴なし
2: 購入履歴あり
2	purchaseHistoryCond.dynamicPeriod	購入履歴期間の月数	int	4	0..1	1, 3, 6, 12, 24
3	purchaseHistoryCond.purchaseCount	購入回数	XML: purchaseCount	-	0..1	
XML: purchaseCount
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	purchaseCount.minimum	購入回数の下限値	int	4	0..1	1-10: 購入回数の下限
2	purchaseCount.maximum	購入回数の上限値	int	4	0..1	0: 購入回数の上限なし
1-10: 購入回数の上限
XML: ageRangeCond
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	ageRangeCond.lowerBound	年齢の下限値	int	4	1	0: 指定なし
10 - 100: 年齢の下限値
2	ageRangeCond.upperBound	年齢の上限値	int	4	1	0: 指定なし
10 - 100: 年齢の上限値
XML: multiPrefectureCond
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	multiPrefectureCond.prefectureCond	都道府県名	String	32	1..47	NONE: 指定なし

・HOKKAIDO
・AOMORI
・IWATE
・MIYAGI
・AKITA
・YAMAGATA
・FUKUSHIMA
・IBARAKI
・TOCHIGI
・GUNMA
・SAITAMA
・CHIBA
・TOKYO
・KANAGAWA
・NIIGATA
・TOYAMA
・ISHIKAWA
・FUKUI
・YAMANASHI
・NAGANO
・GIFU
・SHIZUOKA
・AICHI
・MIE
・SHIGA
・KYOTO
・OSAKA
・HYOGO
・NARA
・WAKAYAMA
・TOTTORI
・SHIMANE
・OKAYAMA
・HIROSHIMA
・YAMAGUCHI
・TOKUSHIMA
・KAGAWA
・EHIME
・KOCHI
・FUKUOKA
・SAGA
・NAGASAKI
・KUMAMOTO
・OITA
・MIYAZAKI
・KAGOSHIMA
・OKINAWA
XML: items
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	items.item	対象商品	XML:item	-	0..n	
XML: item
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	item.itemUrl	商品管理番号	String	32	1	
2	item.itemName	商品名称	String	255	1	
3	item.itemPageUrl	商品ページURL	String	-	1	https: で始まる
XML: otherConditions
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	otherConditions.otherCondition	その他条件	XML:otherCondition	-	1..n	
XML: otherCondition
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	otherCondition.conditionTypeCode	その他条件コード	String	20	1	RS001： デバイス指定
RS002： 販売方法
RS003： 利用金額
RS004： 利用個数
RS006： 対象楽天特別会員プログラム
2	otherCondition.startValue	開始値	String	60	1	conditionTypeCodeによって、値が異なります。



conditionTypeCode	startValue
RS001	0： PC 
1： モバイル
RS002	0： 通常購入
1： 定期購入
99： 通常＆定期購入
RS003	0 ～ 999999999： 金額
RS004	0 ～ 999999999： 個数
RS006	1 : 楽天学割会員限定
2 : 楽天プレミアム会員限定


Response Sample
response example (normal case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
  <status>
    <interfaceId>coupon.get</interfaceId>
    <systemStatus>OK</systemStatus>
    <message>OK</message>
    <requestId>c1cf24e6-9c59-4830-97fe-9812d933aaa1</requestId>
    <requests>
      <couponCode>FOTN-EKXX-68T2-CXZV</couponCode>
    </requests>
  </status>
  <coupon>
    <couponCode>FOTN-EKXX-68T2-CXZV</couponCode>
    <couponName>normal coupon test</couponName>
    <couponCaption>キャプションテスト</couponCaption>
    <couponStartDate>2017-08-15T00:00:00+09:00</couponStartDate>
    <couponEndDate>2017-08-15T00:00:59+09:00</couponEndDate>
    <shopId>500300</shopId>
    <shopUrl>https://www.rakuten.co.jp/demoshop_001/</shopUrl>
    <shopName>デモショップ_001</shopName>
    <couponImage>https://image.rakuten.co.jp/demoshop_001/cabinet/logo.jpg</couponImage>
    <pcGetUrl>https://coupon.rakuten.co.jp/getCoupon?getkey=RUtYWC1GT1ROLTY4VDItQ1haVg--&amp;rt=</pcGetUrl>
    <issueCount>1</issueCount>
    <availCount>0</availCount>
    <itemType>1</itemType>
    <discountType>2</discountType>
    <discountFactor>1</discountFactor>
    <memberAvailMaxCount>0</memberAvailMaxCount>
    <purchaseHistoryCond>
      <type>0</type>
    </purchaseHistoryCond>
    <multiRankCond>
      <rankCond>2</rankCond>
      <rankCond>3</rankCond>
      <rankCond>5</rankCond>
    </multiRankCond>
    <ageRangeCond>
      <lowerBound>0</lowerBound>
      <upperBound>0</upperBound>
    </ageRangeCond>
    <birthmonthCond>0</birthmonthCond>
    <multiPrefectureCond>
      <prefectureCond>HOKKAIDO</prefectureCond>
    </multiPrefectureCond>
    <pcRedirectUrl>https://item.rakuten.co.jp/demoshop_001/item_sample/</pcRedirectUrl>
    <combineFlag>0</combineFlag>
    <displayFlag>1</displayFlag>
    <couponStatus>3</couponStatus>
    <regDate>2017-07-27T13:43:04+09:00</regDate>
    <lastUpdateDate>2017-07-28T17:19:14+09:00</lastUpdateDate>
    <items>
      <item>
        <itemUrl>item_sample</itemUrl>
        <itemName>test12</itemName>
        <itemPageUrl>https://item.rakuten.co.jp/demoshop_001/item_sample/</itemPageUrl>
      </item>
    </items>
    <otherConditions>
      <otherCondition>
        <conditionTypeCode>RS001</conditionTypeCode>
        <startValue>0</startValue>
      </otherCondition>
      <otherCondition>
        <conditionTypeCode>RS001</conditionTypeCode>
        <startValue>1</startValue>
      </otherCondition>
      <otherCondition>
        <conditionTypeCode>RS002</conditionTypeCode>
        <startValue>0</startValue>
      </otherCondition>
      <otherCondition>
        <conditionTypeCode>RS006</conditionTypeCode>
        <startValue>2</startValue>
      </otherCondition>
    </otherConditions>
  </coupon>
</result>
response example (error case)
<?xml version="1.0" encoding="UTF-8"?>
<result>
     <status>
        <interfaceId>coupon.get</interfaceId>
        <systemStatus>OK</systemStatus>
        <message>OK</message>
        <requestId>714a4983-555f-42d9-aeea-89dae89f2f55</requestId>
        <requests>
            <couponCode/>
        </requests>
    </status>
    <errors>
        <error>
            <code>COUPON_E030-002</code>
            <message>couponCode.out_of_bounds</message>
        </error>
    </errors>
</result>
