RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itembundleapi/btocreate/
サービス: 組み合わせ販売API（ItemBundleAPI）

サービス一覧へ戻る / ItemBundleAPI

RMS WEB SERVICE : ItemBundle.create
Overview

この機能を利用すると、組み合わせ販売を新規登録することができます。

Endpoint
Endpoint
https://api.rms.rakuten.co.jp/es/1.0/bto/bundle
Request
Request Method
Method
POST
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
Level 1: base
No.	Logical Name	Parameter Name	Required	Type	Max Char	Default	Description	Sample
1	親商品管理番号	parentItemManageNumber	yes	String	32	-	組み合わせの親商品。
組み合わせられた子商品は親商品のページにて関連商品として表示されます。	item-001
2	組み合わせ管理番号	bundleManageNumber	yes	String	64	-	組み合わせ販売の管理番号。
組み合わせを新規登録する際に指定され、店舗内においてユニークな番号です。	my-shop-bundle-001
3	表示設定	bundleState	yes	String	-	-	商品ページ上の組み合わせ表示設定。
1つの親商品に対して、最大2つの組み合わせを表示させる（ACTIVE）ことが可能です。非表示（INACTIVE）の組み合わせの制限はありません。

設定可能な値は以下のいずれか

・ACTIVE
・INACTIVE	ACTIVE
4	組み合わせ商品リスト	bundleItems	yes	List<String>	-	-	組み合わせられた商品のリスト。
親商品も該当リストに入ります。
1つの親商品に対して、子商品は必ず1つ登録する必要があり、最大3つまで登録できます。	
5	組み合わせ管理名称	bundleName	yes	String	32	-	組み合わせの管理名称	スマートフォンの組み合わせ
6	組み合わせ販売説明文	bundleDescription	no	String	50	-	組み合わせ販売の説明文	スマートフォン本体とスマホカバーの組み合わせです。
Level 2: bundleItem
No	Logical Name	Parameter Name	Required	Type	Max Char	Default	Description	Sample
1	商品管理番号	itemManageNumber	yes	String	32	-	組み合わせ商品の商品管理番号	item-002
2	選択必須フラグ	mandatory	no	Boolean	-	false	組み合わせられた商品が選択必須かどうかのフラグ。
親商品は必ず「true」に設定する必要があります。
子商品については影響を及ぼさないため、設定は任意です。

設定可能な値は以下のいずれか

・true
・false	true
3	商品の並び順	sequence	no	Integer	-	0	親商品商品ページ上での子商品の表示順序	1
Response
HTTP Status
Code	Status	Description
201	OK	リクエストが成功した。
405	Method Not Allowed	許可されていないメソッドを使用しようとした。
例：POSTメソッドを利用すべきフォームでGETメソッドを使う。
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

Level 1: base
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	組み合わせ管理番号	bundleManageNumber	yes	String	64	組み合わせ販売の管理番号。
組み合わせを新規登録する際に指定され、店舗内においてユニークな番号です。	my-shop-bundle-001
2	組み合わせ管理名称	bundleName	yes	String	32	組み合わせの管理名称	スマートフォンの組み合わせ
3	組み合わせ販売説明文	bundleDescription	no	String	50	組み合わせ販売の説明文	スマートフォン本体とスマホカバーの組み合わせです。
4	親商品管理番号	parentItemManageNumber	yes	String	32	組み合わせの親商品。
組み合わせられた子商品は親商品のページにて関連商品として表示されます。	item-001
5	表示設定	bundleState	yes	String	-	商品ページ上の組み合わせ表示設定。

有効な値は以下のいずれか

・ACTIVE
・INACTIVE	ACTIVE
6	組み合わせ商品リスト	bundleItems	yes	List<String>	-	組み合わせられた商品のリスト。
親商品も該当リストに入ります。	
7	作成日	createdDate	yes	Date	-	組み合わせの作成日時	2017-11-22T06:30:00.000141Z
8	更新日	updatedDate	yes	Date	-	組み合わせの最終更新日時	2017-11-22T06:30:00.000141Z
Level 2: bundleItem
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	商品管理番号	itemManageNumber	yes	String	32	組み合わせ商品の商品管理番号	item-002
2	選択必須フラグ	mandatory	yes	Boolean	-	組み合わせられた商品が選択必須かどうかのフラグ。

有効な値は以下のいずれか

・true
・false	true
3	商品の並び順	sequence	yes	Integer	-	親商品商品ページ上での子商品の表示順序	1
4	商品削除フラグ	isDeletedItem	yes	Boolean	-	組み合わせ商品がデータベース上削除されたかどうかのフラグ。
商品がデータベース上から削除され、存在しない場合、「true」が返却されます。

有効な値は以下のいずれか

・true
・false	false




Error

Level 1: base
No	Logical Name	Parameter Name	Required	Type	Max Char	Description
1	エラー	errors	yes	List<Error>	-	組み合わせを作成する際に発生したエラーのリスト
Level 2: Error
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	メッセージ	message	yes	String	-	エラーの説明	item-0yyは販売期間指定商品です。販売期間指定商品は組み合わせに登録できません。
2	コード	code	yes	String	-	エラーコード。
詳細はこちら。	B1051
Sample
作成処理が成功した場合
Request (curl コマンドを使った例)
curl -X POST \
  https://api.rms.rakuten.co.jp/es/1.0/bto/bundle \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "parentItemManageNumber" :"item-001",
    "bundleState" : "ACTIVE",
    "bundleManageNumber" : "my-shop-bundle-01",
    "bundleName" : "スマートフォンの組み合わせ",
    "bundleDescription" : "スマートフォン本体とスマホカバーの組み合わせです。",
    "bundleItems": [
    {
        "itemManageNumber": "item-001",
        "mandatory" : true
    },
    {
        "itemManageNumber": "item-002",
        "sequence" : 1
    }
  ]
}'
Response in JSON format (Status: 201 OK)
{
    "bundleManageNumber": "my-shop-bundle-01",
    "parentItemManageNumber": "item-001",
    "bundleState": "ACTIVE",
    "bundleName" : "スマートフォンの組み合わせ",
    "bundleDescription" : "スマートフォン本体とスマホカバーの組み合わせです。",
    "bundleItems": [
        {
            "itemManageNumber": "item-001",
            "mandatory" : true,
            "sequence" : 0
            "isDeletedItem": "false"
        },
        {
            "itemManageNumber": "item-002",
            "mandatory" : false,
            "sequence" : 1
            "isDeletedItem": "false"
        }
    ],
    "createdDate": "2017-11-22T06:30:00.000141Z",
    "updatedDate": "2017-11-22T06:30:00.000141Z"
}
パラメータ指定に誤りがある場合
Request (curl コマンドを使った例)
curl -X POST \
  https://api.rms.rakuten.co.jp/es/1.0/bto/bundle \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "parentItemManageNumber" :"item-0xx",
    "bundleState" : "ACTIVE",
    "bundleManageNumber" : "my-shop-bundle-01",
    "bundleName" : "スマートフォンの組み合わせ",
    "bundleItems": [
    {
        "itemManageNumber": "item-0xx",
        "mandatory" : true
    },
    {
        "itemManageNumber": "item-0yy",
        "sequence" : 1
    }
  ]
}'
Response in JSON format (Status: 422 Unprocessable Entity)
{
    "errors": [
        {
            "code": "B1051",
            "message": "item-0yyは販売期間指定商品です。販売期間指定商品は組み合わせに登録できません。"
        }
    ]
}
