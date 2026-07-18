RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/categoryapi2/getcategorytree/
サービス: カテゴリAPI 2.0（CategoryAPI 2.0）

サービス一覧へ戻る / CategoryAPI 2.0

RMS WEB SERVICE : category.category-trees.get
Overview
この機能を利用すると、カテゴリセットIDを指定しカテゴリツリー情報を取得することができます。
カテゴリセットを利用していない場合、カテゴリセットIDには「0」を指定してください。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/{categorySetId}	GET
Request
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	categorySetId	カテゴリセットID	yes	string	40	1	カテゴリセットを利用していない場合、「0」を指定。
Query Parameter
No	Parameter Name	Logical Name	Required	Type	Max Byte	Multiplicity	Description
1	categorysetfields	カテゴリセットフィールド	no	enum	-	0,1	以下のカテゴリセット情報を取得したい場合は指定。
複数指定する場合はカンマ区切り。

・TITLE：カテゴリセット名
・CATEGORY_SET_FEATURES：カテゴリセット設定
・CREATED：カテゴリセットの登録日時
・UPDATED： カテゴリセットの更新日時
2	categoryfields	カテゴリフィールド	no	enum	-	0,1	以下のカテゴリ情報を取得したい場合は指定。
複数指定する場合はカンマ区切り。

・CATEGORY_SET_ID：カテゴリセットID
・TITLE：カテゴリ名
・CATEGORY_FEATURES：カテゴリ設定
・DESCRIPTION：カテゴリ説明文
・ADDITIONALDESCRIPTION：カテゴリ説明文下
・IMAGES：カテゴリ画像
・LAYOUT：カテゴリレイアウト
・CREATED：カテゴリの登録日時
・UPDATED：カテゴリの更新日時
HTTP Body
None

Response
HTTP Headers
No	Key	Value
1	Content-Type	application/json
HTTP Body
成功した場合
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
L1	L2	L3	L4	L5	L6
1	categorySet	カテゴリセット	no	object	-	0,1	Query Parameterを指定した場合に返される。
2		categorySetId	カテゴリセットID	yes	string	20	1	数字または"etc"。
カテゴリセットを利用していない場合は「0」。
3		title	カテゴリセット名	no	string	60	0,1	"categorySetfields"で指定した場合に返される。
カテゴリセットを利用していない場合は全角スペース。
4		categorySetFeatures	カテゴリセット設定	no	object	-	0,1	"categorySetfields"で指定した場合に返される。
5			display	カテゴリセット表示	no	boolean	-	0,1	・true：表示
・false：非表示
6		created	カテゴリセットの登録日時	no	string	-	0,1	"categorySetfields"で指定した場合に返される。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
7		updated	カテゴリセットの更新日時	no	string	-	0,1	"categorySetfields"で指定した場合に返される。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
8	categorySetId	カテゴリセットID	no	string	-	0,1	Query Parameterを指定しない場合に返される。
9	rootNode	ルートノード	yes	object	-	1	
10		children	子カテゴリのリスト	yes	list<object>	-	1..30	
11			category	カテゴリ	yes	object	-	1	
12				categoryId	カテゴリID	yes	string	40	1	型は文字列だが、値は数値。
13				categorySetId	カテゴリセットID	no	string	20	0,1	"categoryfields"で指定した場合に返される。
数字または"etc"。
カテゴリセットを利用していない場合は「0」。
14				title	カテゴリ名	no	string	60	0,1	"categoryfields"で指定した場合に返される。
15				categoryFeatures	カテゴリ設定	no	object	-	0,1	"categoryfields"で指定した場合に返される。
16					display	カテゴリ表示	no	boolean	-	0,1	・true：表示
・false：非表示
17					categoryPageViewMode	カテゴリページ表示形式	no	enum	-	0,1	・LIST：リスト形式
・GALLERY：ウィンドウショッピング形式
・PLURAL ：1ページ複数商品形式
18				description	カテゴリ説明文	no	object	-	0,1	"categoryfields"で指定した場合に返される。
19					pc	カテゴリ説明文上	no	string	8000	0,1	PC用カテゴリ説明文の上部。
20					sp	スマートフォン用カテゴリ説明文	no	string	8000	0,1	
21				additionalDescription	カテゴリ説明文下	no	string	8000	0,1	"categoryfields"で指定した場合に返される。
PC用カテゴリ説明文の下部。
22				images	カテゴリ画像	no	object	-	0,1	"categoryfields"で指定した場合に返される。
23					type	カテゴリ画像種別	no	enum	-	0,1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
・ABSOLUTE：楽天市場おすすめ画像
24					location	カテゴリ画像URL	no	string	255	0,1	カテゴリ画像種別が「CABINET」「GOLD」の場合、画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
例: "/myfolder-1/tv01.jpg"

「ABSOLUTE」の場合、URL全文。
例："https://image.rakuten.co.jp/com/img/rms/cabinet/recommend_new/imgXX.jpg"
25					alt	カテゴリ画像名(ALT)	no	string	255	0,1	
26				layout	カテゴリレイアウト	yes	object	-	1	"categoryfields"で指定した場合に返される。
27					navigationId	ヘッダー・フッター・レフトナビのテンプレートID	yes	number	-	1	
28					layoutCategorySequenceId	表示項目の並び順テンプレートID	yes	number	-	1	
29					smallDescriptionId	共通説明文（小）テンプレートID	yes	number	-	1	
30					showcaseId	目玉商品テンプレートID	yes	number	-	1	
31					largeDescriptionId	共通説明文（大）テンプレートID	yes	number	-	1	
32				created	カテゴリの登録日時	no	string	-	0,1	"categoryfields"で指定した場合に返される。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
33				updated	カテゴリの更新日時	no	string	-	0,1	"categoryfields"で指定した場合に返される。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
34			children	子カテゴリのリスト	no	list<object>	-	0..30	
35				category	カテゴリ	no	object	-	0,1	
36					categoryId	カテゴリID	no	string	40	0,1	型は文字列だが、値は数値。
37					categorySetId	カテゴリセットID	no	string	20	0,1	"categoryfields"で指定した場合に返される。
数字または"etc"。
カテゴリセットを利用していない場合は「0」。
38					title	カテゴリ名	no	string	60	0,1	"categoryfields"で指定した場合に返される。
39					categoryFeatures	カテゴリ設定	no	object	-	0,1	"categoryfields"で指定した場合に返される。
40						display	カテゴリ表示	no	boolean	-	0,1	・true：表示
・false：非表示
41						categoryPageViewMode	カテゴリページ表示形式	no	enum	-	0,1	・LIST：リスト形式
・GALLERY：ウィンドウショッピング形式
・PLURAL ：1ページ複数商品形式
42					description	カテゴリ説明文	no	object	-	0,1	"categoryfields"で指定した場合に返される。
43						pc	カテゴリ説明文上	no	string	8000	0,1	PC用カテゴリ説明文の上部。
44						sp	スマートフォン用カテゴリ説明文	no	string	8000	0,1	
45					additionalDescription	カテゴリ説明文下	no	string	8000	0,1	"categoryfields"で指定した場合に返される。
PC用カテゴリ説明文の下部。
46					images	カテゴリ画像	no	object	-	0,1	"categoryfields"で指定した場合に返される。
47						type	カテゴリ画像種別	no	enum	-	0,1	・CABINET：R-Cabinetの画像
・GOLD：GOLDの画像
・ABSOLUTE：楽天市場おすすめ画像
48						location	カテゴリ画像URL	no	string	255	0,1	カテゴリ画像種別が「CABINET」「GOLD」の場合、画像URLの"/画像パス”部分。

CABINET：https://image.rakuten.co.jp/[SHOP_URL]/cabinet/画像パス
GOLD：https://www.rakuten.ne.jp/gold/[SHOP_URL]/画像パス
例: "/myfolder-1/tv01.jpg"

「ABSOLUTE」の場合、URL全文。
例："https://image.rakuten.co.jp/com/img/rms/cabinet/recommend_new/imgXX.jpg"
49						alt	カテゴリ画像名(ALT)	no	string	255	0,1	
50					layout	カテゴリレイアウト	no	object	-	0,1	"categoryfields"で指定した場合に返される。
51						navigationId	ヘッダー・フッター・レフトナビのテンプレートID	no	number	-	0,1	
52						layoutCategorySequenceId	表示項目の並び順テンプレートID	no	number	-	0,1	
53						smallDescriptionId	共通説明文（小）テンプレートID	no	number	-	0,1	
54						showcaseId	目玉商品テンプレートID	no	number	-	0,1	
55						largeDescriptionId	共通説明文（大）テンプレートID	no	number	-	0,1	
56					created	カテゴリの登録日時	no	string	-	0,1	"categoryfields"で指定した場合に返される。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
57					updated	カテゴリの更新日時	no	string	-	0,1	"categoryfields"で指定した場合に返される。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
58	created	カテゴリツリーの登録日時	yes	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。
59	updated	カテゴリツリーの更新日時	yes	string	-	1	フォーマットはISO 8601、タイムゾーンは日本標準時(JST)、秒まで。


失敗した場合
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
L1	L2
1	errors		エラー	yes	List<error>	-	1..n	エラーのリスト。
2		code	コード	yes	string	-	1	メッセージコードの一覧はこちら。
3		message	メッセージ	yes	string	-	1
Sample
サンプルで用いるカテゴリセット(categorySetId=32345)のカテゴリツリー状態は以下のようになっています。


成功した場合(QueryParameterで何も設定していない場合)
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/32345' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "categorySetId": "32345",
    "rootNode": {
        "children": [
            {
                "categoryId": "1",
                "children": [
                    {
                        "categoryId": "2",
                        "children": [
                            {
                                "categoryId": "5",
                                "children": [
                                    {
                                        "categoryId": "8",
                                        "children": [
                                            {
                                                "categoryId": "10"
                                            },
                                            {
                                                "categoryId": "11"
                                            },
                                            {
                                                "categoryId": "12"
                                            }
                                        ]
                                    },
                                    {
                                        "categoryId": "9"
                                    }
                                ]
                            },
                            {
                                "categoryId": "6"
                            }
                        ]
                    },
                    {
                        "categoryId": "3",
                        "children": [
                            {
                                "categoryId": "7"
                            }
                        ]
                    },
                    {
                        "categoryId": "4"
                    }
                ]
            }
        ]
    },
    "created": "2021-10-21T11:26:46+09:00",
    "updated": "2021-10-21T11:26:46+09:00"
}
成功した場合(QueryParameterで全てのFieldを設定した場合)
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/32345?categorysetfields=TITLE,CATEGORY_SET_FEATURES,CREATED,UPDATED&categoryfields=CATEGORY_SET_ID,TITLE,CATEGORY_FEATURES,DESCRIPTION,ADDITIONALDESCRIPTION,IMAGES,LAYOUT,CREATED,UPDATED' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 200 OK)
{
    "categorySet": {
        "categorySetId": "32345",
        "title": "Tree 日本 1",
        "categorySetFeatures": {
            "display": true
        },
        "created": "2021-03-10T00:56:02+09:00",
        "updated": "2023-06-02T17:26:30+09:00"
    },
    "rootNode": {
        "children": [
            {
                "category": {
                    "categoryId": "1",
                    "categorySetId": "32345",
                    "title": "カテゴリ1",
                    "categoryFeatures": {
                        "display": true,
                        "categoryPageViewMode": "LIST"
                    },
                    "description": {
                        "pc": "aaa",
                        "sp": "aaa"
                    },
                    "additionalDescription": "aaa",
                    "images": [
                        {
                            "type": "CABINET",
                            "location": "/washingmachine.jpg",
                            "alt": "全自動洗濯機1"
                        }
                    ],
                    "layout": {
                        "navigationId": 0,
                        "layoutCategorySequenceId": 0,
                        "smallDescriptionId": 0,
                        "showcaseId": 0,
                        "largeDescriptionId": 0
                    },
                    "created": "2021-06-14T17:45:10+09:00",
                    "updated": "2021-10-21T11:48:12+09:00"
                },
                "children": [
                    {
                        "category": {
                            "categoryId": "2",
                            "categorySetId": "32345",
                            "title": "カテゴリ2",
                            "categoryFeatures": {
                                "display": true,
                                "categoryPageViewMode": "LIST"
                            },
                            "description": {
                                "pc": "aaa",
                                "sp": "aaa"
                            },
                            "additionalDescription": "aaa",
                            "images": [
                                {
                                    "type": "CABINET",
                                    "location": "/washingmachine.jpg",
                                    "alt": "全自動洗濯機1"
                                }
                            ],
                            "layout": {
                                "navigationId": 0,
                                "layoutCategorySequenceId": 0,
                                "smallDescriptionId": 0,
                                "showcaseId": 0,
                                "largeDescriptionId": 0
                            },
                            "created": "2021-06-14T17:45:10+09:00",
                            "updated": "2021-10-21T11:48:12+09:00"
                        },
                        "children": [
                            {
                                "category": {
                                    "categoryId": "5",
                                    "categorySetId": "32345",
                                    "title": "カテゴリ5",
                                    "categoryFeatures": {
                                        "display": true,
                                        "categoryPageViewMode": "LIST"
                                    },
                                    "description": {
                                        "pc": "aaa",
                                        "sp": "aaa"
                                    },
                                    "additionalDescription": "aaa",
                                    "images": [
                                        {
                                            "type": "CABINET",
                                            "location": "/washingmachine.jpg",
                                            "alt": "全自動洗濯機1"
                                        }
                                    ],
                                    "layout": {
                                        "navigationId": 0,
                                        "layoutCategorySequenceId": 0,
                                        "smallDescriptionId": 0,
                                        "showcaseId": 0,
                                        "largeDescriptionId": 0
                                    },
                                    "created": "2021-06-14T17:45:10+09:00",
                                    "updated": "2021-10-21T11:48:12+09:00"
                                },
                                "children": [
                                    {
                                        "category": {
                                            "categoryId": "8",
                                            "categorySetId": "32345",
                                            "title": "カテゴリ8",
                                            "categoryFeatures": {
                                                "display": true,
                                                "categoryPageViewMode": "LIST"
                                            },
                                            "description": {
                                                "pc": "aaa",
                                                "sp": "aaa"
                                            },
                                            "additionalDescription": "aaa",
                                            "images": [
                                                {
                                                    "type": "CABINET",
                                                    "location": "/washingmachine.jpg",
                                                    "alt": "全自動洗濯機1"
                                                }
                                            ],
                                            "layout": {
                                                "navigationId": 0,
                                                "layoutCategorySequenceId": 0,
                                                "smallDescriptionId": 0,
                                                "showcaseId": 0,
                                                "largeDescriptionId": 0
                                            },
                                            "created": "2021-06-14T17:45:10+09:00",
                                            "updated": "2021-10-21T11:48:12+09:00"
                                        },
                                        "children": [
                                            {
                                                "category": {
                                                    "categoryId": "10",
                                                    "categorySetId": "32345",
                                                    "title": "カテゴリ10",
                                                    "categoryFeatures": {
                                                        "display": true,
                                                        "categoryPageViewMode": "LIST"
                                                    },
                                                    "description": {
                                                        "pc": "aaa",
                                                        "sp": "aaa"
                                                    },
                                                    "additionalDescription": "aaa",
                                                    "images": [
                                                        {
                                                            "type": "CABINET",
                                                            "location": "/washingmachine.jpg",
                                                            "alt": "全自動洗濯機1"
                                                        }
                                                    ],
                                                    "layout": {
                                                        "navigationId": 0,
                                                        "layoutCategorySequenceId": 0,
                                                        "smallDescriptionId": 0,
                                                        "showcaseId": 0,
                                                        "largeDescriptionId": 0
                                                    },
                                                    "created": "2021-06-14T17:45:10+09:00",
                                                    "updated": "2021-10-21T11:48:12+09:00"
                                                }
                                            },
                                            {
                                                "category": {
                                                    "categoryId": "11",
                                                    "categorySetId": "32345",
                                                    "title": "カテゴリ11",
                                                    "categoryFeatures": {
                                                        "display": true,
                                                        "categoryPageViewMode": "LIST"
                                                    },
                                                    "description": {
                                                        "pc": "aaa",
                                                        "sp": "aaa"
                                                    },
                                                    "additionalDescription": "aaa",
                                                    "images": [
                                                        {
                                                            "type": "CABINET",
                                                            "location": "/washingmachine.jpg",
                                                            "alt": "全自動洗濯機1"
                                                        }
                                                    ],
                                                    "layout": {
                                                        "navigationId": 0,
                                                        "layoutCategorySequenceId": 0,
                                                        "smallDescriptionId": 0,
                                                        "showcaseId": 0,
                                                        "largeDescriptionId": 0
                                                    },
                                                    "created": "2021-06-14T17:45:10+09:00",
                                                    "updated": "2021-10-21T11:48:12+09:00"
                                                }
                                            },
                                            {
                                                "category": {
                                                    "categoryId": "12",
                                                    "categorySetId": "32345",
                                                    "title": "カテゴリ12",
                                                    "categoryFeatures": {
                                                        "display": true,
                                                        "categoryPageViewMode": "LIST"
                                                    },
                                                    "description": {
                                                        "pc": "aaa",
                                                        "sp": "aaa"
                                                    },
                                                    "additionalDescription": "aaa",
                                                    "images": [
                                                        {
                                                            "type": "CABINET",
                                                            "location": "/washingmachine.jpg",
                                                            "alt": "全自動洗濯機1"
                                                        }
                                                    ],
                                                    "layout": {
                                                        "navigationId": 0,
                                                        "layoutCategorySequenceId": 0,
                                                        "smallDescriptionId": 0,
                                                        "showcaseId": 0,
                                                        "largeDescriptionId": 0
                                                    },
                                                    "created": "2021-06-14T17:45:10+09:00",
                                                    "updated": "2021-10-21T11:48:12+09:00"
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        "category": {
                                            "categoryId": "9",
                                            "categorySetId": "32345",
                                            "title": "カテゴリ9",
                                            "categoryFeatures": {
                                                "display": true,
                                                "categoryPageViewMode": "LIST"
                                            },
                                            "description": {
                                                "pc": "aaa",
                                                "sp": "aaa"
                                            },
                                            "additionalDescription": "aaa",
                                            "images": [
                                                {
                                                    "type": "CABINET",
                                                    "location": "/washingmachine.jpg",
                                                    "alt": "全自動洗濯機1"
                                                }
                                            ],
                                            "layout": {
                                                "navigationId": 0,
                                                "layoutCategorySequenceId": 0,
                                                "smallDescriptionId": 0,
                                                "showcaseId": 0,
                                                "largeDescriptionId": 0
                                            },
                                            "created": "2021-06-14T17:45:10+09:00",
                                            "updated": "2021-10-21T11:48:12+09:00"
                                        }
                                    }
                                ]
                            },
                            {
                                "category": {
                                    "categoryId": "6",
                                    "categorySetId": "32345",
                                    "title": "カテゴリ6",
                                    "categoryFeatures": {
                                        "display": true,
                                        "categoryPageViewMode": "LIST"
                                    },
                                    "description": {
                                        "pc": "aaa",
                                        "sp": "aaa"
                                    },
                                    "additionalDescription": "aaa",
                                    "images": [
                                        {
                                            "type": "CABINET",
                                            "location": "/washingmachine.jpg",
                                            "alt": "全自動洗濯機1"
                                        }
                                    ],
                                    "layout": {
                                        "navigationId": 0,
                                        "layoutCategorySequenceId": 0,
                                        "smallDescriptionId": 0,
                                        "showcaseId": 0,
                                        "largeDescriptionId": 0
                                    },
                                    "created": "2021-06-14T17:45:10+09:00",
                                    "updated": "2021-10-21T11:48:12+09:00"
                                }
                            }
                        ]
                    },
                    {
                        "category": {
                            "categoryId": "3",
                            "categorySetId": "32345",
                            "title": "カテゴリ3",
                            "categoryFeatures": {
                                "display": true,
                                "categoryPageViewMode": "LIST"
                            },
                            "description": {
                                "pc": "aaa",
                                "sp": "aaa"
                            },
                            "additionalDescription": "aaa",
                            "images": [
                                {
                                    "type": "CABINET",
                                    "location": "/washingmachine.jpg",
                                    "alt": "全自動洗濯機1"
                                }
                            ],
                            "layout": {
                                "navigationId": 0,
                                "layoutCategorySequenceId": 0,
                                "smallDescriptionId": 0,
                                "showcaseId": 0,
                                "largeDescriptionId": 0
                            },
                            "created": "2021-06-14T17:45:10+09:00",
                            "updated": "2021-10-21T11:48:12+09:00"
                        },
                        "children": [
                            {
                                "category": {
                                    "categoryId": "7",
                                    "categorySetId": "32345",
                                    "title": "カテゴリ7",
                                    "categoryFeatures": {
                                        "display": true,
                                        "categoryPageViewMode": "LIST"
                                    },
                                    "description": {
                                        "pc": "aaa",
                                        "sp": "aaa"
                                    },
                                    "additionalDescription": "aaa",
                                    "images": [
                                        {
                                            "type": "CABINET",
                                            "location": "/washingmachine.jpg",
                                            "alt": "全自動洗濯機1"
                                        }
                                    ],
                                    "layout": {
                                        "navigationId": 0,
                                        "layoutCategorySequenceId": 0,
                                        "smallDescriptionId": 0,
                                        "showcaseId": 0,
                                        "largeDescriptionId": 0
                                    },
                                    "created": "2021-06-14T17:45:10+09:00",
                                    "updated": "2021-10-21T11:48:12+09:00"
                                }
                            }
                        ]
                    },
                    {
                        "category": {
                            "categoryId": "4",
                            "categorySetId": "32345",
                            "title": "カテゴリ4",
                            "categoryFeatures": {
                                "display": true,
                                "categoryPageViewMode": "LIST"
                            },
                            "description": {
                                "pc": "aaa",
                                "sp": "aaa"
                            },
                            "additionalDescription": "aaa",
                            "images": [
                                {
                                    "type": "CABINET",
                                    "location": "/washingmachine.jpg",
                                    "alt": "全自動洗濯機1"
                                }
                            ],
                            "layout": {
                                "navigationId": 0,
                                "layoutCategorySequenceId": 0,
                                "smallDescriptionId": 0,
                                "showcaseId": 0,
                                "largeDescriptionId": 0
                            },
                            "created": "2021-06-14T17:45:10+09:00",
                            "updated": "2021-10-21T11:48:12+09:00"
                        }
                    }
                ]
            }
        ]
    },
    "created": "2021-10-21T11:26:46+09:00",
    "updated": "2021-10-21T11:26:46+09:00"
}
失敗した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/categories/shop-category-trees/category-set-ids/xxx' \
--header 'Authorization: ESA xxx'
Response in JSON format (Status: 400 Bad Request)
{
    "errors": [
        {
            "code": "IE0002",
            "message": "categorySetId has an invalid value : \"xxx\"."
        }
    ]
}
