RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inquirymanagementapi/attachment_post/
サービス: 問い合わせ管理API（InquiryManagementAPI）

サービス一覧へ戻る / InquiryManagementAPI

RMS WEB SERVICE : inquirymngapi.attachment.post
Overview
この機能を利用すると、問い合わせ返信に利用する添付ファイルを登録することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/attachment	POST
Request
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	multipart/form-data;
Request Parameter
No	Parameter	Description	Required	Type	Note
1	file	ファイル	yes	form data	一度のリクエストで登録できる添付ファイルは1つです。パラメータとして複数のファイルが指定された場合は最後に指定されたものだけが登録されます。

・ファイルの容量は5Mbyte以下
・ファイル名は拡張子を含めて100文字以内
・添付ファイルの保存期限はアップロードした日から最大90日間
※ファイル名に"["や"]"の使用はお控えください。inquirymngapi.attachment.getのリクエストをしたときに、画像が取得できなくなります。

アップロードできるファイルの拡張子は下記の通りです。

MIME type	file extension
image/png	*.png
image/jpeg	*.jpeg, *.jpg
image/gif	*.gif
application/pdf	*.pdf
Response
Response Header
Header	Value
Content-Type	application/json;charset=UTF-8
HTTP Response Status
Code	Description	Note
201	Created	ファイルが登録されました。
400	Bad Request	パラメータに不備があります。
404	Not Found	指定された条件に一致するデータがありません。
413	Request Entity Too Large	Request エンティティーが大きすぎます。
500	Internal Server Error	APIに障害が起こっているか、レスポンスが遅くなっている可能性があります。しばらく経ってから再度アクセスしてください。
503	Temporary Unavailable	一時的にAPIがサービス提供できない状態になっています。
HTTP Response Error Message
InquiryManagementAPI Error Codes Reference を参照してください。

Response Body
Level 1: result
No	Parameter Name	Description	Type	Note
1	label	ファイル名	string	
2	path	添付ファイルのパス	string	/yyyy/MM/dd/{shopId}/xxxxxxxxxxxxxxxxxxxxx
3	errorMessage	エラーメッセージ	string	ファイルがサーバーに送信された後、登録処理中に何らかのエラーが起こった場合はこのフィールドにメッセージが入ります。
Sample
リクエストが成功した場合
ファイルの登録に成功した場合
Request
curl -X POST \
  https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/attachment \
  -H 'Accept: */*' \
  -H 'Accept-Encoding: gzip, deflate' \
  -H 'Authorization: ESA youresakey' \
  -H 'Cache-Control: no-cache' \
  -H 'Connection: keep-alive' \
  -H 'Content-Length: 10000' \
  -H 'Content-Type: multipart/form-data;' \
  -H 'Host: api.rms.rakuten.co.jp' \
  -H 'User-Agent: YourClient' \
  -H 'cache-control: no-cache' \
  -H 'content-type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
  -F 'file=@/Path/to/your/file.jpg'
Response (Status: 201 Created)
{
    "result": {
        "label": "images.jpg",
        "path": "2019/10/02/504166/173449_f37dd6d9b11e4b3589850fb286e345be"
    }
}
リクエストが失敗した場合のResponse Sample
ファイルサイズが 5Mbyte 以上の場合
Response (Status: 413 Request Entity Too Large)
{
    "errors": [
        {
            "code": "GF0003",
            "message": "Request entity too large"
        }
    ]
}
ファイルが指定されていない あるいは ファイル以外が指定されている場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "file": "attachment file is empty."
        }
    }
}
ファイル名が既定の文字数を超えた場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "file": "too long attachment file name."
        }
    }
}
