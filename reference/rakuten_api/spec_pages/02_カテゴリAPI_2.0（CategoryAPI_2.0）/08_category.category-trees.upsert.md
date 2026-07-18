RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/categoryapi2/upsertcategorytree/
サービス: カテゴリAPI 2.0（CategoryAPI 2.0）

サービス一覧へ戻る / CategoryAPI 2.0

RMS WEB SERVICE : category.category-trees.upsert
Overview
この機能を利用すると、カテゴリセットIDを指定し、カテゴリツリー情報を登録・更新・削除することができます。
カテゴリ自体の登録は category.shop-categories.insert をご利用ください。

※機能の注意点
カテゴリツリー情報の削除について
Request Bodyが空の場合、カテゴリツリーが削除されます。
また、カテゴリツリーのRequest Bodyからカテゴリを削除すると、そのカテゴリが完全に削除され、商品の紐づきも解除されます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/{categorySetId}	PUT
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/json
Path Parameters
No	Parameter Name	Logical Name	Required	Tpe	Max Byte	Multiplicity	Description
1	categorySetId	カテゴリセットID	yes	string	40	1	カテゴリセットを利用していない場合は「0」を指定。
HTTP Body
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
L1	L2
1	children	子カテゴリのリスト	yes	list<children>	-	1..30	
2		categoryId	カテゴリID	yes	string	40	1	型は文字列だが、値は数値。
3		children	子カテゴリのリスト	no	list<children>	-	0..30	
Response
HTTP Header
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合
None

失敗した場合
No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
L1	L2	L3
1	errors	エラー	yes	List<error>	1..n	データ作成する際に発生したエラーのリスト
2		code	コード	yes	string	1	メッセージコードの一覧はこちら
3		message	メッセージ	yes	string	1
4		metadata	メタデータ	no	object	0,1	エラーの補足情報
5			propertyPath	属性パス	no	string	0,1	発生したエラーの位置
Sample
成功した場合
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/32345’ \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
  "children": [
    {
      "categoryId": "1234567891",
      "children": [
        {
          "categoryId": "1234567892",
          "children": [
            {
              "categoryId": "1234567893"
            },
            {
              "categoryId": "1234567893"
            }
          ]
        },
        {
          "categoryId": "1234567892",
          "children": [
            {
              "categoryId": "1234567893"
            },
            {
              "categoryId": "1234567893"
            }
          ]
        }
      ]
    }
  ]
}'
Response in JSON format (Status: 204 No Content)
失敗した場合
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/xxx' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
  "children": [
    {
      "categoryId": "1234567891",
      "children": [
        {
          "categoryId": "1234567892",
          "children": [
            {
              "categoryId": "1234567893"
            },
            {
              "categoryId": "1234567893"
            }
          ]
        },
        {
          "categoryId": "1234567892",
          "children": [
            {
              "categoryId": "1234567893"
            },
            {
              "categoryId": "1234567893"
            }
          ]
        }
      ]
    }
  ]
}'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0002",
            "message": "categorySetId has an invalid value : \"xxx\"."
        }
    ]
}
カテゴリ情報と商品との紐付き情報が削除されるケース
このサンプルでは、カテゴリツリーの更新で２つのカテゴリ（カテゴリID=1234567893と1234567896）をツリーから除いて更新します。
この更新ではカテゴリツリーが更新されるだけではなく、削除された２つのカテゴリと商品の紐付き情報も削除されます。
更新前後にカテゴリツリー情報、カテゴリ情報、商品との紐付き情報を取得し、カテゴリツリーが更新されていることと、更新で除かれたカテゴリ情報とそれに紐付く商品との紐付き情報が削除されていることを確認します。
今回のサンプルでの更新前と更新後は以下の図のようになります。


現在のカテゴリツリー情報を取得
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/32345?breadcrumb=false' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "categorySetId": "32345",
    "rootNode": {
        "children": [{
      "categoryId": "1234567891",
      "children": [
        {
          "categoryId": "1234567892",
          "children": [
            {
              "categoryId": "1234567894"
            },
            {
              "categoryId": "1234567895"
            }
          ]
        },
        {
          "categoryId": "1234567893",
          "children": [
            {
              "categoryId": "1234567896"
            }
          ]
        }
      ]
    }]
    },
    "created": "2021-11-25T04:55:21+09:00",
    "updated": "2021-11-25T04:55:21+09:00"
}
現在のカテゴリ情報を取得
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-categories/category-ids/1234567892?breadcrumb=false' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "categoryId": "1234567892",
    "categorySetId": "32345",
    "title": "name 日本 2",
    "categoryFeatures": {
        "display": false,
        "categoryPageViewMode": "PLURAL"
    },
    "description": {
        "pc": "test",
        "sp": "description SP 日本 1"
    },
    "additionalDescription": {
        "pc": "あばb\nあんj"
    },
    "images": [
        {
            "type": "CABINET",
            "location": "/myfolder-1/tv01.jpg",
            "alt": "l2_17-category-Test"
        }
    ],
    "layout": {
        "navigationId": 0,
        "layoutCategorySequenceId": 0,
        "smallDescriptionId": 0,
        "largeDescriptionId": 0,
        "showcaseId": 0
    },
    "created": "2021-11-25T04:54:41+09:00",
    "updated": "2021-11-25T04:59:27+09:00"
}
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-categories/category-ids/1234567896?breadcrumb=false' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "categoryId": "1234567896",
    "categorySetId": "32345",
    "title": "name 日本 2",
    "categoryFeatures": {
        "display": false,
        "categoryPageViewMode": "PLURAL"
    },
    "description": {
        "pc": "test",
        "sp": "description SP 日本 1"
    },
    "additionalDescription": {
        "pc": "あばb\nあんj"
    },
    "images": [
        {
            "type": "CABINET",
            "location": "/myfolder-1/tv01.jpg",
            "alt": "l2_17-category-Test"
        }
    ],
    "layout": {
        "navigationId": 0,
        "layoutCategorySequenceId": 0,
        "smallDescriptionId": 0,
        "largeDescriptionId": 0,
        "showcaseId": 0
    },
    "created": "2021-11-25T04:54:41+09:00",
    "updated": "2021-11-25T04:59:27+09:00"
}
現在の商品との紐付き情報を取得
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/item-mappings/manage-numbers/mng123?breadcrumb=false' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "categoryIds": [
        "1234567893",
        "1234567896"
    ],
    "mainPluralCategoryId": "1234567896",
    "created": "2021-11-25T05:02:32+09:00",
    "updated": "2021-11-25T05:04:26+09:00"
}
カテゴリツリー情報の更新
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/32345’ \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
  "children": [
    {
      "categoryId": "1234567891",
      "children": [
        {
          "categoryId": "1234567892",
          "children": [
            {
              "categoryId": "1234567894"
            },
            {
              "categoryId": "1234567895"
            }
          ]
        }
      ]
    }
  ]
}'
Response in JSON format (Status: 204 No Content)
更新されたカテゴリツリー情報を取得
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/32345?breadcrumb=false' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "categorySetId": "32345",
    "rootNode": {
        "children": [{
      "categoryId": "1234567891",
      "children": [
        {
          "categoryId": "1234567892",
          "children": [
            {
              "categoryId": "1234567894"
            },
            {
              "categoryId": "1234567895"
            }
          ]
        }
      ]
    }]
    },
    "created": "2021-11-25T04:55:21+09:00",
    "updated": "2021-12-25T04:55:21+09:00"
}
削除されたカテゴリ情報を取得
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-categories/category-ids/1234567893?breadcrumb=false' \
--header 'Authorization: ESA xxx' --header 'Content-Type: application/json'
Response in JSON format (Status: 404 Not Found)
{
    "errors": [
        {
            "code": "GE0014",
            "message": "No category found for inputs; dataId=CategoryKey(categoryId=1234567893)"
        }
    ]
}
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-categories/category-ids/1234567896?breadcrumb=false' \
--header 'Authorization: ESA xxx' --header 'Content-Type: application/json'
Response in JSON format (Status: 404 Not Found)
{
    "errors": [
        {
            "code": "GE0014",
            "message": "No category found for inputs; dataId=CategoryKey(categoryId=1234567896)"
        }
    ]
}
削除された商品との紐付き情報を取得
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/item-mappings/manage-numbers/mng123?breadcrumb=false' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "categoryIds": [
        "1"
    ],
    "mainPluralCategoryId": "1234567891",
    "created": "2021-11-25T04:55:21+09:00",
    "updated": "2021-11-25T04:55:21+09:00"
}
