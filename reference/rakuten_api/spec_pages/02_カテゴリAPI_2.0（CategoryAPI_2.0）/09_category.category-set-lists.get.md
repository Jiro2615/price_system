RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/categoryapi2/getcategorysetlist/
サービス: カテゴリAPI 2.0（CategoryAPI 2.0）

サービス一覧へ戻る / CategoryAPI 2.0

RMS WEB SERVICE : category.category-set-lists.get
Overview
この機能を利用すると、すべてのカテゴリセット情報を取得することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-set-lists	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
None

Query Parameter
No	Parameter Name	Logical Name	Required	Type	Multiplicity	Description
1	categorysetfields	カテゴリセットフィールド	no	enum	0,1	以下のカテゴリセット情報を取得したい場合は指定。
複数指定する場合はカンマ区切り。

・TITLE：カテゴリセット名
・CATEGORY_SET_FEATURES：カテゴリセット設定
・CREATED：カテゴリセットの登録日時
・UPDATED： カテゴリセットの更新日時
HTTP Body
None

Response
HTTP Header
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合(categorysetfieldsに何も設定されていない場合)
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	categorySetKeyList	カテゴリセットID一覧	yes	List<string>		-	1..n	数字または"etc"。
カテゴリセットを利用していない場合は「0」。
2	created	カテゴリセットリストの登録日時	yes	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
3	updated	カテゴリセットリストの登録日時	yes	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
成功した場合(categorysetfieldsに何かが設定されていた場合)
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
L1	L2	L3
1	categorySetList	カテゴリセット一覧	yes	List<categorySet>	-	1..n	カテゴリセットリスト
2		categorySetId	カテゴリセットID	yes	string	20	1	数字または"etc"。
カテゴリセットを利用していない場合は「0」。
3		title	カテゴリセット名	no	string	60	0,1	"categorysetfields"で指定した場合に返される。
カテゴリセットを利用していない場合は全角スペース。
4		categorySetFeatures	カテゴリセット設定	no	object	-	0,1	"categorysetfields"で指定した場合に返される。
5			display	カテゴリセット表示	yes	boolean	-	1	・true：表示
・false：非表示
6		created	カテゴリセットの登録日時	yes	string	-	1	"categorysetfields"で指定した場合に返される。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
7		updated	カテゴリセットの更新日時	yes	string	-	1	"categorysetfields"で指定した場合に返される。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
8	created	カテゴリセットリストの登録日時	no	string	-	0,1	フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
9	updated	カテゴリセットリストの更新日時	no	string	-	0,1	フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
失敗した場合
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
L1	L2
1	errors	エラー	yes	List<error>	-	1..n	エラーのリスト
2		code	コード	yes	string	-	1	メッセージコードの一覧はこちら
3		message	メッセージ	yes	string	-	1
Sample
成功した場合(categorysetfieldsが設定されていない場合)
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-set-lists' \
--header 'Authorization: ESA xxx' 
Response in JSON format (Status: 200 OK)
{
    "categorySetKeyList": [
        "0",
        "16",
        "etc"
    ],
    "created": "2020-05-22T14:47:37+09:00",
    "updated": "2021-08-20T09:40:07+09:00"
}
成功した場合(categorysetfieldsが設定されている場合)
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-set-lists?
categorysetfields=TITLE,CATEGORY_SET_FEATURES,CREATED,UPDATED' \
--header 'Authorization: ESA xxx' 
Response in JSON format (Status: 200 OK)
{
    "categorySetList": [
        {
            "categorySetId": "0",
            "title": "医薬品・医薬部外品",
            "categorySetFeatures": {
                "display": true
            },
            "created": "2020-05-22T14:47:34+09:00",
            "updated": "2021-08-20T09:44:37+09:00"
        },
        {
            "categorySetId": "16",
            "title": "K",
            "categorySetFeatures": {
                "display": true
            },
            "created": "2020-05-22T14:47:34+09:00",
            "updated": "2021-08-20T09:40:07+09:00"
        },
        {
             "categorySetId": "etc",
             "title": "その他",
             "categorySetFeatures": {
                 "display": true
             },
             "created": "2020-08-27T18:01:01+09:00",
             "updated": "2020-08-27T18:01:01+09:00"
         }
    ],
    "created": "2020-05-22T14:47:37+09:00",
    "updated": "2021-08-20T09:40:07+09:00"
}
失敗した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-set-lists?categorysetfields=TITLE123' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
       {
          "code": "IE0002",
          "message": "categorysetfields has an invalid value : TITLE123."
       }
    ]
}
