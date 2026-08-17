RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/reserveapi/reserveinfolistpost/
サービス: 購入申込API（ReserveAPI）

サービス一覧へ戻る / ReserveAPI

RMS WEB SERVICE : reserve.earlyCommit.update
Overview

この機能を利用すると、一括で早期確定を行うことができます。

Endpoint / HTTP Method
Endpoint	HTTP Method


https://api.rms.rakuten.co.jp/es/1.0/reserve/earlyCommitReservations

	POST
Request
Request Header
Key	Value


Authorization

	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Body
Level 1: base
No	Parameter Name	Description	Required	Multiple	Type	Default	Note	Sample
1	reserveKeyList	更新対象リスト	yes	no	list<reserveKeyListModel>	-	更新する申込番号と詳細IDの組み合わせのリスト
最大500件まで指定可能	
Level 2: reserveKeyListModel
No	Parameter Name	Description	Required	Multiple	Type	Default	Note	Sample
1	reserveNumber	申込番号	yes	yes	string	-		123456-20191204-262709-r
2	detailId	お届け回（詳細ID）	yes	yes	number	0	0以上の値が指定可能

0を指定した場合、直近のお届け回が更新される

1つの申込番号につき、1件の詳細IDのみ指定できる
	1
Request Sample
Request (curl コマンドを使った例)
curl -X POST \
  https://api.rms.rakuten.co.jp/es/1.0/reserve/earlyCommitReservations \
  -H 'Authorization:ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "reserveKeyList": [
        {
            "reserveNumber":"123456-20200409-9195583-r",
            "detailId":1
        },
        {
            "reserveNumber":"123456-20200109-9186222-r",
            "detailId":3
        },
        {
            "reserveNumber":"123456-20200310-9187001-r",
            "detailId":2
        },
        {
            "reserveNumber":"123456-20200412-9197655-r",
            "detailId":1
        }
    ]
}'
Response
Response Header
Key	Value
Content-Type	application/json; charset=utf-8
Response Body
Level 1: base
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	responseDatetime	レスポンス時刻	date	yes	yyyy-MM-ddTHH:mm:ssZ	2019-12-18T10:52:20+0900
2	summaryResultMessage	処理結果メッセージのまとめ	string	yes	リクエストした問い合わせの内、何件が正常終了したのかを表す	10件中3件正常終了しました


3	updateResultList	各申込番号の処理結果のリスト	list<updateUnitResponseModel>	yes	以下の場合、更新処理への続行ができないため、詳細に1件のみ返却する。

・必須パラメーターが指定されていない
・リクエスト件数が上限を超える
・認証失敗	Response Sample 内 必須パラメータ不足等により後続処理が行えない場合 参照



Level 2: updateUnitResponseModel
No	Parameter Name	Description	Type	Not Null	Note	Sample
1	reserveNumber	申込番号	string	no	後続処理できない場合の返却値はnull	123456-20200409-9195583-r
2	detailId	更新対象の明細ID	number	yes	リクエスト時0で指定した場合、実際に更新対象の詳細IDが設定される

後続処理できない場合の返却値は-1	10
3	resultCode	処理結果コード	string	yes	Response Code Reference の一覧は こちら	N00-000
4	resultMessage	処理結果メッセージ	string	yes	Response Code Reference の一覧は こちら	正常終了しました
Response Sample
リクエストがすべて成功した場合
Response (Status: 200 OK)
{
    "responseDatetime": "2020-04-18T00:31:23+0900",
    "summaryResultMessage": "4件中4件正常終了しました",
    "updateResultList": [
        {
            "reserveNumber": "123456-20200409-9195583-r",
            "detailId": "1",
            "resultCode": "N00-000",
            "resultMessage": "正常終了しました"
        },
        {
            "reserveNumber": "123456-20200109-9186222-r",
            "detailId": "3",
            "resultCode": "N00-000",
            "resultMessage": "正常終了しました"
        },
        {
            "reserveNumber": "123456-20200310-9187001-r",
            "detailId": "2",
            "resultCode": "N00-000",
            "resultMessage": "正常終了しました"
        }
        {
            "reserveNumber": "123456-20200412-9197655-r",
            "detailId": "1",
            "resultCode": "N00-000",
            "resultMessage": "正常終了しました"
        }
    ]
}
リクエストが一部失敗した場合
Response (Status: 200 OK)
{
    "responseDatetime": "2020-04-18T00:31:23+0900",
    "summaryResultMessage": "4件中1件正常終了しました",
    "updateResultList": [
        {
            "reserveNumber": "123456-20200409-9195583-r",
            "detailId": "1",
            "resultCode": "N00-000",
            "resultMessage": "正常終了しました"
        },
        {
            "reserveNumber": "123456-20200109-9186222-r",
            "detailId": "3",
            "resultCode": "E01-002",
            "resultMessage": "有効な詳細IDを指定してください"
        },
        {
            "reserveNumber": "123456-20200310-9187001-r",
            "detailId": "2",
            "resultCode": "E02-001",
            "resultMessage": "対象のお届け回が存在しません"
        },
        {
            "reserveNumber": "123456-20200412-9197655-r",
            "detailId": "1",
            "resultCode": "E02-002",
            "resultMessage": "既に早期確定準備中のため更新できません"
        }
    ]
}
必須パラメータ不足等により後続処理が行えない場合
Response (Status: 200 OK)
{
    "responseDatetime": "2020-03-18T00:31:23+0900",
    "summaryResultMessage": "0件正常終了しました",
    "updateResultList": [
        {
            "reserveNumber": null,
            "detailId": -1,
            "resultCode": "E01-000",
            "resultMessage": "必須パラメーター店舗IDを必ず指定してください"
        }
    ]
}
