RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inquirymanagementapi/reply_post/
サービス: 問い合わせ管理API（InquiryManagementAPI）

サービス一覧へ戻る / InquiryManagementAPI

RMS WEB SERVICE : inquirymngapi.reply.post
Overview
この機能を利用することで、問い合わせに対する返信を登録することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiry/reply	POST
Request
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Body
Level 1: base
No	Parameter Name	Description	Required	Type	Note
1	inquiryNumber	問い合わせ番号	yes	string	重複することのない番号（ランダムに発行、桁数は変動する可能性があります）と英文字の組合せ。

・半角英数字と-（ハイフン）
・文字列の長さは1-40文字
2	shopId	店舗ID	yes	string	
3	message	メッセージ	yes	string	・メッセージ文中の一行の最大文字数は300文字
・文字列の長さは1-2000文字

メッセージにURLを含める場合は、httpsプロトコルであり、以下のドメインのいずれかであることが条件です。

・rakuten.co.jp
・rakuten.ne.jp
・rakuten.com
・rakuten-bank.co.jp
・trafficgate.net
・rakuten-card.co.jp
・payment.sej.co.jp
・faq.rakuten.net
・support.rakuten-card.jp

4	attachments	添付ファイル	no	list<attachments>	添付できるファイルは1つまでですが、配列で渡してください。
Level 2: attachments
No	Parameter Name	Description	Required	Type	Note
1	label	ファイル名	yes	string	文字列の長さは100文字以内

label には下記のいずれかを指定します。

・inquirymngapi.inquiry.get や、inquirymngapi.attachment.post のレスポンスの中にある、attachments の label
・任意のファイル名
　※label で取得したファイルと同じ拡張子であること

指定可能な拡張子は下記の通りです。



MIME type	file extension
image/png	*.png
image/jpeg	*.jpeg, *.jpg
image/gif	*.gif
application/pdf	*.pdf




2	path	添付ファイルのパス	yes	string	inquirymngapi.inquiry.get や、inquirymngapi.attachment.post のレスポンスの中にある、attachments の path を指定します。

・文字列の長さは1000文字以内
・/yyyy/MM/dd/{shopId}/xxxxxxxxxxxxxxxxxxxxx

例：
2017/10/19/123456/235959_10_c59548c3c576228486a1f0037eb16a1b
Response
Response Header
Key	Value
Content-Type	application/json;charset=UTF-8
HTTP Response Status
Code	Status	Description
201	Created	返信が登録されました。
400	Bad Request	パラメータに不備があります。
404	Not Found	指定された条件に一致するデータがありません。
409	Conflict	データ重複のため登録できませんでした。
500	Internal Server Error	APIに障害が起こっているか、レスポンスが遅くなっている可能性があります。しばらく経ってから再度アクセスしてください。
503	Temporary Unavailable	一時的にAPIがサービス提供できない状態になっています。
HTTP Response Error message
InquiryManagementAPI Error Code Referenceを参照してください。

Response Body
Level 1: result
No	Parameter	Description	Type	Note
1	inquiryNumber	問い合わせ番号	string	
2	message	メッセージ	string	
3	regDate	返信日時	date	yyyy-MM-ddTHH:mm:ss+09:00
4	replyFrom	返信者	string	返信者（merchant）を表します。
5	isRead	既読フラグ	boolean	ユーザが返信を読んだか否かを表します。

・true：既読
・false：未読
6	attachments	添付ファイル	 list<attachments>	Level 2: attachments を参照してください
Level 2: attachments
No	Parameter	Description	Type	Note
1	label	ファイル名	string	
2	path	添付ファイルのパス	string	/yyyy/MM/dd/{shopId}/xxxxxxxxxxxxxxxxxxxxx
Sample
リクエストが成功した場合
返信登録が成功した場合
Request
{
   "inquiryNumber":"999999-20191112-1t",
   "shopId":"999999",
   "message":"メッセージです",
   "attachments":[
       {
             "label":"media.jpg",
             "path":"2019/12/18/999999/152700_a0444190b2b24f3a94c8b69d46212801"
        }
   ]
}
Response (Status: 201 Created)
{
    "result": {
        "message": "メッセージです",
        "regDate": "2019-12-19T09:47:13+09:00",
        "replyFrom": "merchant",
        "isRead": false,
        "attachments": [
            {
                "label": "media.jpg",
                "path": "2019/12/18/999999/152700_a0444190b2b24f3a94c8b69d46212801"
            }
        ]
    }
}
リクエストが失敗した場合のResponse Sample
添付ファイルを複数指定した場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "attachments": "size must be between 0 and 1"
        }
    }
}
label の文字数をオーバーした場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "attachments[0].label": "size must be between 1 and 100"
        }
    }
}
