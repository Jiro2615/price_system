RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/categoryapi2/updatecategory/
サービス: カテゴリAPI 2.0（CategoryAPI 2.0）

サービス一覧へ戻る / CategoryAPI 2.0

RMS WEB SERVICE : category.shop-categories.update
Overview
この機能を利用すると、カテゴリIDを指定しカテゴリ情報を更新することができます。
部分更新の機能ではないため、リクエストに含まれなかった項目は値が削除されるか、デフォルト値で更新されます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/categories/shop-categories/category-ids/{categoryId}	PUT
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
2	Content-Type	application/json
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	categoryId	カテゴリID	yes	string	40	1	
HTTP Body
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
L1	L2
1	categorySetId	カテゴリセットID	yes	string	20	1	数字または"etc"。
カテゴリセットを利用していない場合は「0」を指定。
2	title	カテゴリ名	yes	string	60	1	以下のものは使用不可。

・HTMLタグ
・「\」マーク（「カテゴリ」を区切るために利用）
3	categoryFeatures	カテゴリ設定	no	object	-	0,1	
4		display	カテゴリ表示	no	boolean	-	0,1	・true：表示（デフォルト）
・false：非表示
5		categoryPageViewMode	カテゴリページ表示形式	no	enum	-	0,1	・LIST：リスト形式
・GALLERY：ウィンドウショッピング形式（デフォルト）
・PLURAL：1ページ複数商品形式
6	description	カテゴリ説明文	no	object	-	0,1	
7		pc	カテゴリ説明文上	no	string	8000	0,1	PC用カテゴリ説明文の上部。
8		sp	スマートフォン用カテゴリ説明文	no	string	8000	0,1	
9	additionalDescription	カテゴリ説明文下	no	string	8000	0,1	PC用カテゴリ説明文の下部。
10	images	カテゴリ画像	no	object	-	0,1	
11		type	カテゴリ画像種別	yes	enum	-	1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
・ABSOLUTE：楽天市場おすすめ画像
12		location	カテゴリ画像URL	yes	string	255	1	カテゴリ画像種別が「CABINET」「GOLD」の場合、画像URLの"/画像パス”部分。

CABINET: https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD: https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
例: "/myfolder-1/tv01.jpg"

「ABSOLUTE」を指定した場合、URL全文。
例： "https://image.rakuten.co.jp/com/img/rms/cabinet/recommend_new/imgXXX.jpg"

拡張子がjpg, jpeg, png, gifの画像パスのみ使用可能です。
画像パスに使用できる文字は以下の通りです。
0-9、a-z、A-Z、- (U+002D)、. (U+002E)、/ (U+002F)、: (U+003A)、_ (U+005F)
13		alt	カテゴリ画像名(ALT)	no	string	255	0,1	"<", ">"とhtmlタグ以外のすべての文字列が使用可能。
14	layout	カテゴリレイアウト	no	object	-	0,1	
15		navigationId	ヘッダー・フッター・レフトナビのテンプレートID	no	number	-	0,1	IDの値はShopAPIの shop.shopLayoutCommon.get の下記項目から取得可能。
　4.2.6. Level 4: shopLayoutCommon - layoutCommonId

デフォルト値：0
16		layoutCategorySequenceId	表示項目の並び順テンプレートID	no	number	-	0,1	IDの値はShopAPIの shop.layoutCategoryMap.get の下記項目から取得可能。
　4.2.6. Level 4: layoutCategoryMap - categoryMapId

デフォルト値：0
17		smallDescriptionId	共通説明文（小）テンプレートID	no	number	-	0,1	IDの値はShopAPIの shop.layoutTextSmall.get の下記項目から取得可能。
　4.2.6. Level 4: layoutTextSmall - textSmallId

デフォルト値：0
18		showcaseId	目玉商品テンプレートID	no	number	-	0,1	IDの値はShopAPIの shop.layoutLossLeader.get の下記項目から取得可能。
　4.2.6. Level 4: layoutLossLeader - lossLeaderId

デフォルト値：0
19		largeDescriptionId	共通説明文（大）テンプレートID	no	number	-	0,1	IDの値はShopAPIの shop.layoutTextLarge.get の下記項目から取得可能。
　4.2.6. Level 4: layoutTextLarge - textLargeId

デフォルト値：0
Response
HTTP Headers
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合
None

失敗した場合

No	Parameter Name	Logical Name	Not Null	Type	Multiplicity	Description
L1	L2	L3
1	errors	エラー	yes	List<error>	1..n	エラーのリスト
2		code	コード	yes	string	1	メッセージコードの一覧はこちら
3		message	メッセージ	yes	string	1
4		metadata	メタデータ	no	object	0,1	エラーの補足情報
5			propertyPath	属性パス	no	string	0,1	発生したエラーの位置
Sample
成功した場合
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-categories/category-ids/3333' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "categorySetId": "32345",
    "title": "色3",
    "categoryFeatures": {
        "display": false,
        "categoryPageViewMode": "LIST"
    },
    "description": {
        "pc": "PC用カテゴリ説明文の上部",
        "sp": "スマートフォン用カテゴリ説明文"
    },
    "additionalDescription": "PC用カテゴリ説明文の下部",
    "images": [
        {
            "alt": "全自動洗濯機",
            "location": "/washingmachine.jpg",
            "type": "CABINET"
        }
    ]
}'
Response in JSON format (Status: 204 No Content)
失敗した場合(カテゴリが存在しなかった場合)
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-categories/category-ids/9999999' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
  "categorySetId" : "32345",
  "title" : "name 日本 2",
  "categoryFeatures"  : {
    "display" : false,
    "categoryPageViewMode" : "LIST"
  },
  "description" : {
    "pc" : "test",
    "sp": "description SP 日本 1"
  }
}'
Response in JSON format (Status: 404 Not Found)
{
    "errors": [
        {
            "code": "GE0014",
            "message": "Not found for inputs; categoryId:14120"
        }
    ]
}
失敗した場合(その他のエラー)
Request (curl コマンドを使った例)
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-categories/category-ids/3333' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
  "categorySetId" : "32345",
  "title" : "name 日本 2",
  "categoryFeatures"  : {
    "display" : false,
    "categoryPageViewMode" : "abcdefg"
  },
  "description" : {
    "pc" : "test",
    "sp": "description SP 日本 1"
  }
}'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0007",
            "message": "Invalid choice selected for categoryFeatures.categoryPageViewMode. Please choose from [GALLERY, LIST, PLURAL].",
            "metadata": {
                "propertyPath": "categoryFeatures.categoryPageViewMode"
            }
        }
    ]
}
