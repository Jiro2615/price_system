RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inquirymanagementapi/counts_get/
サービス: 問い合わせ管理API（InquiryManagementAPI）

サービス一覧へ戻る / InquiryManagementAPI

RMS WEB SERVICE : inquirymngapi.counts.get
Overview

この機能を利用すると、指定された日付の期間の問い合わせの数を取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method


https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiries/count

	GET
Request
Request Header
Key	Value


Authorization

	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
No	Parameter Name	Description	Required	Type	Note
1	fromDate	件数を取得する期間の最初の日時	yes	date	yyyy-MM-ddTHH:mm:ss

※ "fromDate" と"toDate"で指定される日付の期間は31日以内とします。
2	toDate	件数を取得する期間の最後の日時	yes	date
3	noMerchantReply	店舗様からの未返信フラグ	no	boolean	このパラメータを指定して値をtrueとすると、店舗様からの返信が未返信の問い合わせ数を返します。
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
1	count	件数	int	
Sample
リクエストが成功した場合
問い合わせ数が取得できた場合
Request
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiries/count?toDate=2019-10-31T02:59:59&fromDate=2019-10-01T00:00:00&noMerchantReply=false
Response (Status: 200 OK)
{
    "result": {
        "count": 12
    }
}
問い合わせ数が０の場合
Request
https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiries/count?toDate=2019-10-31T02:59:59&fromDate=2019-10-01T00:00:00&noMerchantReply=false
Response (Status: 200 OK)
{
    "result": {
        "count": 0
    }
}
リクエストが失敗した場合のResponse Sample
Date フォーマットが不正な場合
Response (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "fromDate": "must match \"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}$\"",
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
