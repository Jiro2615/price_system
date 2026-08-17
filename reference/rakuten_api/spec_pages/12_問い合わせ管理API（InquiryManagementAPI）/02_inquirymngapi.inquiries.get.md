RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inquirymanagementapi/inquiries_get/
サービス: 問い合わせ管理API（InquiryManagementAPI）

サービス一覧へ戻る / InquiryManagementAPI

RMS WEB SERVICE : inquirymngapi.inquiries.get
Overview
この機能を利用すると、指定された条件の問い合わせリストを取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiries	GET
Request
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
No	Parameter Name	Description	Required	Type	Default	Note
1	limit	取得件数	no	int	10	・limit
　・値の範囲：1 ～ 100
・page
　・値の範囲：1 ～ 10000
・取得できる最大件数は、下記の式に当てはめて10000以下です。
　 limit × ( page - 1) + limit <= 10000
2	page	リスト取得ページ位置	no	int	1
3	fromDate	期間指定開始日時	yes	date		yyyy-MM-ddTHH:mm:ss

※ "fromDate" と"toDate"で指定される日付の期間は31日以内とします。
※ 日時はJSTで指定してください。
4	toDate	期間指定終了日時	yes	date	
5	noMerchantReply	店舗未返信フラグ	no	boolean		このパラメータを指定して値をtrueとすると、店舗様からの返信が未返信の問い合わせを返します。
Response
Response Header
Key	Value
Content-Type	application/json;charset=UTF-8
HTTP Response Status
Code	Status	Description
200	OK	リクエストが成功しました。
400	Bad Request	パラメータに不備があります。
404	Not Found	指定された条件に一致するデータがありません。
500	Internal Server Error	APIに障害が起こっているか、レスポンスが遅くなっている可能性があります。しばらく経ってから再度アクセスしてください。
503	Temporary Unavailable	一時的にAPIがサービス提供できない状態になっています。
HTTP Response Error message
InquiryManagementAPI Error Codes Reference を参照してください。

Response Body
Level 1: base
No	Parameter Name	Description	Type	Note
1	totalCount	トータル件数	int	
2	totalPageCount	ページ数	int	
3	page	リスト取得ページ位置	int	
4	list	取得リスト	list<inquiry>	取得された問い合わせは「問い合わせ日時」の降順でソートされます。
詳細は Level 2: inquiry を参照してください。
Level 2: inquiry
No	Parameter Name	Description	Type	Note
1	inquiryNumber	問い合わせ番号	string	重複することのない番号（ランダムに発行、桁数は変動する可能性があります）と英文字の組合せ。

・半角英数字と-（ハイフン）
2	shopId	店舗ID	int	
3	userName	ユーザ氏名	string	
4	userMaskEmail	ユーザーマスクメールアドレス	string	
5	message	メッセージ	string	
6	regDate	問い合わせ日時	date	yyyy-MM-dd'T'HH:mm:ss+09:00
7	itemUrl	商品URL	string	
8	itemName	商品名	string	
9	itemNumber	商品番号	string	
10	isCompleted	処理完了フラグ	boolean	問い合わせが「完了」状態となったか否かを表します。

・true：完了
・false：未完了
11	completedDate	処理完了日時	date	問い合わせが「完了」状態となった日時。

yyyy-MM-dd'T'HH:mm:ss+09:00
12	orderNumber	受注番号	string	
13	readByMerchant	店舗既読フラグ	boolean	問い合わせを店舗が読んだか否かを表します。

・true：既読
・false：未読
14	attachments	添付ファイル	list<attachments>	Level 3: attachments を参照ください。
15	replies	返信	list<replies>	Level 3: replies を参照ください。
16	category	問い合わせカテゴリ	string	問い合わせタイプ（type）に応じて、以下のいずれかの値を返します。

・店舗問い合わせ
　・商品詳細
　・再入荷・在庫
　・返品・交換・キャンセル
　・配送
　・店舗サービス
　※2024年9月17日以前に作成されたもの等、一部の問合せについては、空の値を返します。

・商品問い合わせ
　・商品詳細
　・再入荷・在庫
　・返品・交換・キャンセル
　・配送
　・店舗サービス
　　※2021年8月4日以前に作成されたもの等、一部の問合せについては、空の値を返します。

・受注問い合わせ
　・送料・商品配送
　・返品交換・キャンセル
　・決済方法・購入金額
　・商品詳細
　・注文情報の追加連絡
　・ソーシャルギフト受取
　・その他

・店舗からの問い合わせ
　・発送の確認・連絡
　・注文内容の確認
17	type	問い合わせタイプ	string	以下のいずれかの値

・店舗問い合わせ
・商品問い合わせ
・受注問い合わせ
・店舗からの問い合わせ
18	isMessageDeleted	メッセージ削除	boolean	メッセージが楽天によって削除されたか否かを表します。

・true：削除された
・false：削除されていない

※メッセージが削除された場合、「message」と「attachments」は空になります。
19	lastUpdateDate	最終更新日	date	yyyy-MM-dd'T'HH:mm:ss+09:00
20	socialGiftUserType	ソーシャルギフトユーザタイプ	string	ソーシャルギフト注文関連の問い合わせにおけるユーザの種別を表します。※ソーシャルギフト注文ではない場合はnullになります。

・注文者
・受取人
・null
Level 3: attachments
No	Parameter Name	Description	Type	Note
1	label	ファイル名	string	
2	path	添付ファイルのパス	string	/yyyy/MM/dd/{shopId}/xxxxxxxxxxxxxxxxxxxxx
Level 3: replies
No	Parameter Name	Description	Type	Note
1	id	返信ID	int	同一問い合せに対する返信に付与される連番のID
2	message	メッセージ	string	
3	regDate	返信日時	date	yyyy-MM-dd'T'HH:mm:ss+09:00
4	replyFrom	返信者	string	店舗・ユーザのどちらからの返信かを表します。

・merchant：店舗からの返信
・user：ユーザからの返信
5	isRead	既読フラグ	boolean	店舗・ユーザが返信を読んだか否かを表します。

・true：既読
・false：未読
6	isMessageDeleted	メッセージ削除	boolean	メッセージが楽天によって削除されたか否かを表します。

・true：削除された
・false：削除されていない

※メッセージが削除された場合、「message」と「attachments」は空になります。
7	attachments	添付ファイル	list<attachments>	Level 3: attachments を参照してください。
Sample
リクエストが成功した場合
問い合わせが取得できた場合
Request
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiries?fromDate=2020-05-01T00:00:00&toDate=2020-05-30T23:59:59
Response (Status: 200 OK)
{
    "totalCount": 2,
    "totalPageCount": 1,
    "page": 1,
    "list": [
        {
            "inquiryNumber": "999999-20200519-1t",
            "shopId": 999999,
            "userName": "楽天太郎",
            "userMaskEmail": "9ca9e8e4ef09fe8d9a239a6af95b9bc6s9@pc.fw.rakuten.ne.jp",
            "message": "こんにちは。他の種類の製品はありますか？また群馬県までは何日で届きますか？",
            "regDate": "2020-05-19T15:25:48+09:00",
            "itemUrl": "/_sampleshop/105/",
            "itemName": "おかかふりかけ全3種",
            "itemNumber": "105",
            "isCompleted": false,
            "completedDate": null,
            "category": "",
            "type": "商品問い合わせ",
            "orderNumber": null,
            "readByMerchant": true,
            "attachments": [],
            "replies": [
                {
                    "id": 0,
                    "message": "お問い合わせありがとうございます。ご案内いたします。",
                    "regDate": "2020-05-19T15:25:58+09:00",
                    "replyFrom": "merchant",
                    "isRead": false,
                    "attachments": [],
                    "isMessageDeleted": false
                },
                {
                    "id": 1,
                    "message": "画像をお送りします。",
                    "regDate": "2020-05-19T15:26:59+09:00",
                    "replyFrom": "merchant",
                    "isRead": false,
                    "attachments": [
                        {
                            "label": "images.jpg",
                            "path": "2020/05/19/999999/123456_55080b8b9c864ae694f37771d1f37388"
                        }
                    ],
                    "isMessageDeleted": false
                }
            ],
            "lastUpdateDate": "2020-05-19T15:26:59+09:00",
            "isMessageDeleted": false,
            "socialGiftUserType": null
        },
        {
            "inquiryNumber": "999999-20200519-2t",
            "shopId": 999999,
            "userName": "楽天花子",
            "message": "こんにちは。お店の営業時間を教えて下さい。",
            "regDate": "2020-05-19T15:26:59+09:00",
            "itemUrl": "/_sampleshop/",
            "itemName": "店舗トップページ",
            "itemNumber": null,
            "isCompleted": false,
            "completedDate": null,
            "category": "",
            "type": "店舗問い合わせ",
            "orderNumber": null,
            "readByMerchant": false,
            "attachments": [],
            "replies": [],
            "lastUpdateDate": "2020-05-19T15:26:59+09:00",
            "isMessageDeleted": false,
            "socialGiftUserType": null
        }
     ]
 }
条件に一致する問い合わせがない場合
Request
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiries?toDate=2019-10-31T23:59:59&fromDate=2019-10-01T00:00:00
Response (Status: 200 OK)
{
    "totalCount": 0,
    "totalPageCount": 0,
    "page": 1,
    "list": []
}
リクエストが失敗した場合のResponse Sample
フォーマットに誤りがある場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "toDate": "must match \"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}$\""
        }
    }
}
fromDate と toDate の時系列が逆だった場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "fromDate": "date time range is invalid.",
            "toDate": "date time range is invalid."
        }
    }
}
fromDate と toDateの間が31日以上の場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "fromDate": "date time range should be within 31 days.",
            "toDate": "date time range should be within 31 days."
        }
    }
}
page に 10001 以上を指定した場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",         
　　　　"message": "400 Bad Request"
    }
}
limit に 101 以上を指定した場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "limit": "should be less than equal 100"
        }
    }
}
limit × ( page - 1 ) + limit > 10000 を指定した場合（取得件数が 10001 以上の場合）
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE000",
        "message": "400 Bad Request"
    }
}
