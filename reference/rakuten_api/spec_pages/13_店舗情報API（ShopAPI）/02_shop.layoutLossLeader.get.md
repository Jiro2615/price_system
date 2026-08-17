RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/shopapi/layoutlossleader/
サービス: 店舗情報API（ShopAPI）

サービス一覧へ戻る / ShopAPI

RMS WEB SERVICE : shop.layoutLossLeader.get
Overview

この機能を利用すると、目玉商品（PC）のテンプレート設定情報のみを取得することができます。

テンプレートに登録している商品情報は取得できません。

Endpoint / HTTP Method
Endpoint	HTTP Method


https://api.rms.rakuten.co.jp/es/1.0/shop/layoutLossLeader

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
1	lossLeaderId	目玉商品テンプレートID	Integer	No	指定した lossLeaderId の情報を取得します。
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
3	result	取得データ本体	layoutLossLeaderBizModel	-	No	
Level 2: resultMessageList
No	Element	Description	Type	Max Byte	Not Null	Note
1	resultMessage	メッセージ	resultMessage	-	Yes	
Level 3: resultMessage
No	Element	Description	Type	Max Byte	Not Null	Note
1	code	コード	String	4	Yes	詳細は、ShopAPI Response Codes Reference を参照してください。
2	message	メッセージ	String	-	Yes
Level 2: layoutLossLeaderBizModel
No	Element	Description	Type	Max Byte	Not Null	Note
1	layoutLossLeaderList	目玉商品（PC）のテンプレート設定情報リスト	layoutLossLeaderList	-	Yes	
Level 3: layoutLossLeaderList
No	Element	Description	Type	Max Byte	Not Null	Note
1	layoutLossLeader	目玉商品（PC）のテンプレート設定情報	layoutLossLeader	-	Yes	
Level 4: layoutLossLeader
No	Element	Description	Type	Max Byte	Not Null	Note
1	lossLeaderId	目玉商品テンプレートID	Integer	10	No	
2	name	目玉商品テンプレート名	String	90	No	
3	imageSize	目玉商品画像サイズ（ピクセル）	Integer	10	No	
4	imageScaleStandard	目玉商品画像サイズを設定する方向	Short	5	No	0: 自動調整
1: 高さ
2: 幅
5	dispItemFlag	商品名の表示	Short	5	No	0: 非表示
1: 表示
6	dispPriceFlag	販売価格の表示	Short	5	No	0: 非表示
1: 表示
7	textPosition	目玉商品のレイアウト	Short	5	No	1: 商品名の上に画像1を配置
2: 商品名の下に画像1を配置
8	wrapLength	商品名の横幅（ピクセル）	Integer	10	No	
9	imageCols	1行あたりの商品数	Short	5	No	
10	defaultFlag	テンプレートの自動選択	Short	5	No	0: 自動選択しない
1: 自動選択対象
11	lastUpdate	更新日時	Date	-	No	
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
    <result xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="shopbiz:layoutLossLeaderBizModel">
        <layoutLossLeaderList>
            <layoutLossLeader>
                <lossLeaderId>18700</lossLeaderId>
                <name>目玉商品01</name>
                <imageSize>70</imageSize>
                <imageScaleStandard>0</imageScaleStandard>
                <dispItemFlag>1</dispItemFlag>
                <dispPriceFlag>1</dispPriceFlag>
                <textPosition>1</textPosition>
                <wrapLength>100</wrapLength>
                <imageCols>4</imageCols>
                <defaultFlag>1</defaultFlag>
                <lastUpdate>2016-10-13T11:40:11+09:00</lastUpdate>
            </layoutLossLeader>
        </layoutLossLeaderList>
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
