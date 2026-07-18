RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inquirymanagementapi/inquires_patch_read/
サービス: 問い合わせ管理API（InquiryManagementAPI）

サービス一覧へ戻る / InquiryManagementAPI

RMS WEB SERVICE : inquirymngapi.inquiries.patch.read
Overview

この機能を利用すると、指定された複数の問い合わせを既読状態に変更することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method


https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api/inquiries/read

	PATCH
Request
Request Header
Key	Value


Authorization

	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Body
No	Parameter Name	Description	Required	Type	Note
1	inquiryNumbers	変更対象となる問い合わせ番号のリスト	yes	list<string>	重複することのない番号（ランダムに発行、桁数は変動する可能性があります）と英文字の組合せ。

・半角英数字と-（ハイフン）
・1〜40文字

※問い合わせ番号は最大20個まで指定可能
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

InquiryManagementAPI Error Code Reference を参照してください。

Response Body
Level 1: result
No	Parameter Name	Type	Note
1	ok	list<string>	更新に成功した問い合わせ番号のリスト
2	error	list<error>	更新に失敗した問い合わせの番号とエラーメッセージのリスト。
詳細は Level2: error を参照してください。
Level 2: error
No	Parameter Name	Type	Note
1	inquiryNumber	string	更新に失敗した問い合わせ番号
2	errorMessage	string	エラーメッセージ
Sample
状態の変更が成功した場合
Request
{
  "inquiryNumbers" : [
    "999999-20191212-1t",
    "999999-20191212-2t",
    "999999-20191212-3t",
    ...
    "999999-20191212-20t"
  ]
}

Response (Status: 200 OK)
{
    "result": {
        "ok": [
            "999999-20191212-1t",
            "999999-20191212-2t",
            "999999-20191212-3t",
            ...
            "999999-20191212-20t"
        ],
        "error": []
    }
}
一部のリクエストが失敗した場合
Request
{
  "inquiryNumbers" : [
    "999999-20191212-1t",
    "999999-20191212-2t",
    "999999-20191212-3t",
    ...
    "999999-20191212-20t"
  ]
}

Response (Status: 200 OK)
{
    "result": {
        "ok": [
            "999999-20191212-1t",
            "999999-20191212-2t",
            "999999-20191212-3t",
            ...
            "999999-20191212-20t"
        ],
        "error": [
            {
                "inquiryNumber": "999999-20191212-11t" ,
                "errorMessage": "already set value as specified"
            },
            {
                "inquiryNumber": "999999-20191212-12t" ,
                "errorMessage": "not found."
            }
        ]
    }
}
パラメータ指定に誤りがあった場合（問い合わせ番号が空の場合）
Request
{
  "inquiryNumbers" : [
    "",
    "999999-20191212-2t",
    "999999-20191212-3t",
    ...
    "999999-20191212-20t"
  ]
}


 

下記のいずれかがリスポンスされる

Response 1 (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "inquiryNumbers[]": "must not be blank"
        }
    }
}
Response 2 (Status: 400 Bad Request)
{
    "error": {
        "code": "IE001",
        "message": "bad parameter",
        "targets": {
            "inquiryNumbers[]": "must match \"^[0-9a-zA-Z-]+$\""
        }
    }
}
