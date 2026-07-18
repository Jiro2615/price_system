RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itembundleapi/btogetbundle/
サービス: 組み合わせ販売API（ItemBundleAPI）

サービス一覧へ戻る / ItemBundleAPI

RMS WEB SERVICE : ItemBundle.getBundle
Overview

この機能を利用すると、特定の組み合わせ販売情報を取得することができます。

Endpoint
Endpoint
https://api.rms.rakuten.co.jp/es/1.0/bto/bundle/<bundleManageNumber>
Request
Request Method
Method
GET
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
Level 1: base
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	組み合わせ管理番号	bundleManageNumber	yes	String	64	組み合わせ販売の管理番号。
組み合わせを新規登録する際に指定され、店舗内においてユニークな番号です。	my-shop-bundle-001
Response
HTTP Status
Code	Status	Description
200	OK	リクエストが成功した。
404	Resource Not Found	リクエストリソースが見つからない。
例：該当店舗に存在しない組み合わせ管理番号を利用し、組み合わせを取得しようとした。
405	Method Not Allowed	許可されていないメソッドを使用しようとした。
例：POSTメソッドを利用すべきフォームでGETメソッドを使う。
406	Not Acceptable	Accept関連のヘッダに受理できない内容が含まれている場合に返される。
例：'Accept-type'はXML、リスポンスはJSON。
500	Internal Server Error	サーバ内部にエラーが発生した。
エラーコードの詳細はこちら。
503	Service Unavailable	サービスが一時的に過負荷やメンテナンスで使用不可能である。
エラーコードの詳細はこちら。
Response Header
Key	Value
Content-Type	application/json;charset=utf-8
Response Parameter




Success

Level 1: base
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	組み合わせ管理番号	bundleManageNumber	yes	String	64	組み合わせ販売の管理番号。
組み合わせを新規登録する際に指定され、店舗内においてユニークな番号です。	my-shop-bundle-001
2	組み合わせ管理名称	bundleName	yes	String	32	組み合わせの管理名称	スマートフォンの組み合わせ
3	組み合わせ販売説明文	bundleDescription	no	String	50	組み合わせ販売の説明文。
PC用商品ページでのみ表示されます。	スマートフォン本体とスマホカバーの組み合わせです。
4	表示設定	bundleState	yes	String	-	商品ページ上の組み合わせ表示設定。

有効な値は以下のいずれか

・ACTIVE
・INACTIVE

ACTIVE：表示
INACTIVE：非表示	ACTIVE
5	親商品管理番号	parentItemManageNumber	yes	String	32	組み合わせの親商品。
組み合わせられた子商品は親商品のページにて関連商品として表示されます。	item-001
6	組み合わせ商品リスト	bundleItems	yes	List<String>	-	組み合わせられた商品のリスト。
親商品も該当リストに入ります。	
7	作成日	createdDate	yes	Date	-	組み合わせの作成日時	2017-11-22T06:30:00.000141Z
8	更新日	updatedDate	yes	Date	-	組み合わせの最終更新日時	2017-11-30T06:30:00.000141Z
Level 2: bundleItem
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	商品管理番号	itemManageNumber	yes	String	32	組み合わせ商品の商品管理番号	item-002
2	商品削除フラグ	isDeletedItem	yes	Boolean	-	組み合わせ商品がデータベース上削除されたかどうかのフラグ。
商品がデータベース上から削除され、存在しない場合、「true」が返却されます。

設定可能な値は以下のいずれか

・true
・false	false
3	選択必須フラグ	mandatory	yes	Boolean	-	組み合わせられた商品が選択必須かどうかのフラグ。
親商品は必ず「true」に設定されています。
子商品に設定されていても、影響を与えません。

有効な値は以下のいずれか

・true
・false	true
4	商品の並び順	sequence	yes	Integer	-	親商品商品ページ上での子商品の表示順序	1




Error

Level 1: base
No	Logical Name	Parameter Name	Required	Type	Max Char	Description
1	エラー	errors	yes	List<Error>	-	組み合わせ情報を取得する際に発生したエラーのリスト
Level 2: Error
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	メッセージ	message	yes	String	-	エラーの説明	指定された条件に該当する組み合わせはありませんでした。
2	コード	code	yes	String	-	エラーコード。
詳細はこちら。	B1029
Sample
結果が取得できた場合
Request (curl コマンドを使った例)
curl -X GET \
  https://api.rms.rakuten.co.jp/es/1.0/bto/bundle/my-shop-bundle-01 \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
Response in JSON format (Status: 200 OK)
{
  "bundleName": "スマートフォンの組み合わせ",
  "bundleDescription": "スマートフォン本体とスマホカバーの組み合わせです。",
  "bundleManageNumber": "my-shop-bundle-01",
  "parentItemManageNumber": "item-001",
  "bundleState": "ACTIVE",
  "bundleItems": [
    {
      "itemManageNumber": "item-001",
      "isDeletedItem": false,
      "mandatory": true,
      "sequence": 0
    },
    {
      "itemManageNumber": "item-098",
      "isDeletedItem": false,
      "mandatory": true,
      "sequence": 1
    }
  ],
  "createdDate": "2017-08-29T11:05:35.000693Z",
  "updatedDate": "2017-08-29T11:05:35.000693Z"
}
パラメータ指定に誤りがある場合
Request (curl コマンドを使った例)
curl -X GET \
  https://api.rms.rakuten.co.jp/es/1.0/bto/bundle/my-shop-bundle-0xx \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
Response in JSON format (Status: 404 Resource Not Found)
{
  "errors": [
    {
      "code": "B1029",
      "message": "指定された条件に該当する組み合わせはありませんでした。"
    }
  ]
}
