RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inquirymanagementapi/inquiry_get/
サービス: 問い合わせ管理API（InquiryManagementAPI）

サービス一覧へ戻る / InquiryManagementAPI

RMS WEB SERVICE : inquirymngapi.inquiry.get
Overview
この機能を利用すると、指定された問い合わせ番号の問い合わせ内容を取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiry/{inquiryNumber}	GET
Request
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
No	Parameter Name	Description	Required	Type	Note
1	inquiryNumber	問い合わせ番号	yes	string	重複することのない番号（ランダムに発行、桁数は変動する可能性があります）と英文字の組合せ

・半角英数字と-（ハイフン）
・1〜40文字
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
InquiryManagementAPI Error Code Reference を参照してください。

Response Body
Level 1: result
No	Parameter Name	Description	Type	Note
1	inquiryNumber	問い合わせ番号	string	
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
11	completedDate	処理完了日時	date	yyyy-MM-dd'T'HH:mm:ss+09:00

問い合わせが「完了」状態となった日時
12	orderNumber	受注番号	string	
13	readByMerchant	店舗既読フラグ	boolean	問い合わせを店舗が読んだか否かを表します。

・true：既読
・false：未読
14	attachments	添付ファイル	list<attachments>	Level 2: attachments を参照ください。
15	replies	返信	list<replies>	Level 2: replies を参照ください。
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
Level 2: attachments
No	Parameter Name	Description	Type	Note
1	label	ファイル名	string	
2	path	添付ファイルのパス	string	/yyyy/MM/dd/{shopId}/xxxxxxxxxxxxxxxxxxxxx
Level 2: replies
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
7	attachments	添付ファイル	list<attachments>	Level 2: attachments を参照してください。
Sample
リクエストが成功した場合
Request
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiry/999999-20190806-1t
Response
{
    "result": {
        "inquiryNumber": "999999-20190806-1t",
        "shopId": 999999,
        "userName":"楽天太郎",
        "userMaskEmail": "9ca9e8e4ef09fe8d9a239a6af95b9bc6s9@pc.fw.rakuten.ne.jp",
        "message":"こんにちは。他の種類の製品はありますか？また群馬県高崎市までは何日で届きますか？",
        "regDate": "2020-04-30T13:58:37+09:00",
        "itemUrl":"/shopname/itemnumber/",
        "itemName":"ごはんのおともにおかか生姜",
        "itemNumber": "okakagohan",
        "isCompleted": true,
        "completedDate": "2020-05-20T13:09:52+09:00",
        "category": "",
        "type": "商品問い合わせ",
        "orderNumber": null,
        "readByMerchant": true,
        "attachments":[{
            "label":"filelabel.jpg",
            "path":"2016/12/22/999999/115857_0_3490f97f6258d8dbd9c64f6ab289e1b1",
        "socialGiftUserType": null
        }],
        "replies": [
            {
                "id": 0,
                "message": "楽天太郎様。お問い合わせありがとうございました。うめおかかかもあります。ぜひともご利用ください。\nメール便で送る場合は高崎市までは発送から2日ほどお時間をいただきます。",
                "regDate": "2020-05-20T16:20:05+09:00",
                "replyFrom": "merchant",
                "isRead": false,
                "attachments": [
                    {
                        "label": "media.jpg",
                        "path": "2020/05/18/999999/122905_b69768111bbc4543947562958d7f8fee"
                    }
                ],
                "isMessageDeleted": false
            },
            {
                "id": 1,
                "message": "",
                "regDate": "2020-05-20T16:21:17+09:00",
                "replyFrom": "merchant",
                "isRead": false,
                "attachments": [],
                "isMessageDeleted": true
            }
        ],
        "lastUpdateDate": "2020-05-21T17:21:17+09:00",
        "isMessageDeleted": false
     }
}
