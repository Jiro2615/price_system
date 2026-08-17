RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itembundleapi/btodelete/
サービス: 組み合わせ販売API（ItemBundleAPI）

サービス一覧へ戻る / ItemBundleAPI

RMS WEB SERVICE : ItemBundle.delete
Overview

この機能を利用すると、組み合わせ販売を削除することができます。

Endpoint
Endpoint
https://api.rms.rakuten.co.jp/es/1.0/bto/bundle/<bundleManageNumber>
Request
Request Method
Method
DELETE
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
Query URL
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	組み合わせ管理番号	bundleManageNumber	yes	String	64	組み合わせ販売の管理番号。
組み合わせを新規登録する際に指定され、店舗内においてユニークな番号です。	my-shop-bundle-001
Response
HTTP Status
Code	Status	Description
200	OK	リクエストが成功した。
405	Method Not Allowed	許可されていないメソッドを使用しようとした。
例：POSTメソッドを利用すべきフォームでGETメソッドを使う
406	Not Acceptable	Accept関連のヘッダに受理できない内容が含まれている場合に返される。
例：'Accept-type'はXML、リスポンスはJSON。
422	Unprocessable Entity error	リクエストエンティティが読み込み/解析できないか、パラメータまたはヘッダが間違っている/見つからない。
エラーコードの詳細はこちら。
500	Internal Server Error	サーバ内部にエラーが発生した。
エラーコードの詳細はこちら。
503	Service Unavailable	サービスが一時的に過負荷やメンテナンスで使用不可能である。
エラーコードの詳細はこちら。
Response Header
Key	Value
Content-Type	application/json;charset=utf-8
Response Parameter




Success

成功した場合、リスポンスボディはありません。「200」は組み合わせの削除が成功したことを表しています。




Error

Level 1: base
No	Logical Name	Parameter Name	Required	Type	Max Char	Description
1	エラー	errors	yes	List<Error>	-	組み合わせを削除する際に発生したエラーのリスト
Level 2: Error
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	メッセージ	message	yes	String	-	エラーの説明	B1038
2	コード	code	yes	String	-	エラーコード。
詳細はこちら。	組み合わせの削除に失敗しました。再度お試しください。
Sample
削除処理が成功した場合
Request (curl コマンドを使った例)
curl -X DELETE \
  https://api.rms.rakuten.co.jp/es/1.0/bto/bundle/my-shop-bundle-001 \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \

Response in JSON format (Status: 200 OK)
200
パラメータ指定に誤りがある場合
Request (curl コマンドを使った例)
curl -X DELETE \
  https://api.rms.rakuten.co.jp/es/1.0/bto/bundle/MyShop-Bundle-XX \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \

Response in JSON format (Status: 422 Unprocessable Entity)
{
  "errors": [
    {
      "code": "B1038",
      "message": "組み合わせの削除に失敗しました。再度お試しください。"
    }
  ]
}
