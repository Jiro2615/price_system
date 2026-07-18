RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/navigationapi2/genresattributesdictionaryvaluesget/
サービス: ジャンル・商品属性情報検索API

サービス一覧へ戻る / NavigationAPI 2.0

RMS WEB SERVICE : genres.attributes.dictionaryValues.get
Overview
この機能を利用すると、指定したジャンルIDに紐づく商品属性情報と推奨値を取得することができます。
ジャンル情報のみを取得したい場合には、genres.get をご利用ください。

※商品の登録／更新時にジャンル・商品属性・推奨値の紐づきの整合性チェックを行っています。
　本APIで取得した情報を元に、それぞれのジャンルに登録可能な商品属性情報や推奨値を ItemAPI 2.0で指定してください。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/{genreId}/attributes/{attributeId}/dictionaryValues	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Description
1	genreId	ジャンルID	yes	integer	6桁のジャンルID。

0を指定すると、第一階層のジャンルを返却します。
2	attributeId	商品属性ID	yes	integer	特定の商品属性情報を取得したい場合に指定してください。

※ジャンルに紐づく商品属性と推奨値を全て取得したい場合は、「-」を設定してください。
※Level 3: attribute > id としてレスポンスされます。
Query Parameter
No	Parameter Name	Logical Name	Required	Type	Description
1	showAncestors	祖先ジャンルフラグ	no	boolean	・true：取得する
・false：取得しない（デフォルト）
2	showSiblings	兄弟ジャンルフラグ	no	boolean	・true：取得する
・false：取得しない（デフォルト）
3	showChildren	子ジャンルフラグ	no	boolean	・true：取得する
・false：取得しない（デフォルト）
4	page	ページ数	no	integer	ページネーション機能により、取得したいページのページ番号(1-10000)を指定できます。
このパラメータを使用するには、Path Parameterの「attributeId」が必要です。
5	limit	最大表示件数	no	integer	ページネーション機能により、ページに表示できる推奨値の数(1-10000)が設定できます。
このパラメータを使用するには、Path Parameterの「attributeId」が必要です。
HTTP Body
None

Response
HTTP Header
No	Key	Value	Description
1	Content-Type	application/json;  charset=utf-8	
2	Link		page/limit パラメータを指定した場合のみ返されます。
要素は下記の通りです。
現在取得しているページ位置については、レスポンス内容を元に判断が可能です。

Name	Description
first	最初のページへのリンク
prev	前ページへのリンク
next	次ページへのリンク
last	最後のページへのリンク


HTTP Body
成功した場合

Level 1: base
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	version	バージョン情報	-	version	-	1	ジャンル及び、商品属性定義のバージョン情報
2	genre	ジャンル情報	-	genre	-	1	ジャンル情報
Level 2: version
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	id	バージョンID	yes	integer	-	1	バージョンを区別するためのID
2	fixedAt	更新日時	yes	string	-	1	ジャンル及び、商品属性情報の更新最終日時。
フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。
Level 2: genre
genreId: 0以外の場合

No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	genreId	ジャンルID	yes	integer	6	1	
2	genreIdPath	ジャンルIDパス	yes	List<integer>	30	1..5	トップジャンルからのジャンルIDの配列を返却します。
第一階層から順にレスポンス。
3	nameJa	ジャンル名	yes	string	-	1	
4	nameJaPath	ジャンルパス	yes	List<string>	-	1..5	トップジャンルからのジャンル名の配列を返却します。
第一階層から順にレスポンス。
5	level	階層	yes	integer	1	1	ジャンル階層(1~5)を返却します。
6	lowest	最下層フラグ	yes	boolean	-	1	・true：最下層ジャンル
・false：最下層以外のジャンル
7	properties	ジャンルプロパティ	yes	properties	-	1..n	設定値を返却します。
8	ancestors	祖先ジャンル	no	List<baseGenre>	-	1..n	showAncestorsにtrueをセットした場合に、祖先ジャンルのジャンル情報を返却します。
9	siblings	兄弟ジャンル	no	List<baseGenre>	-	1..n	showSiblingsにtrueをセットした場合に、兄弟ジャンルのジャンル情報を返却します。
10	children	子ジャンル	no	List<baseGenre>	-	1..n	showChildrenにtrueをセットした場合に、子ジャンルのジャンル情報を返却します。
11	attributes	商品属性	no	attributes	-	1..n	genreIdに紐づく商品属性を返却します。

genreId: 0 の場合

No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	children	子ジャンル	yes	List<baseGenre>	-	1..n	子ジャンル情報を返却します
※showChildren=false の設定は無効となります。
Level 3: baseGenre
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	genreId	ジャンルID	yes	integer	6	1	
2	genreIdPath	ジャンルIDパス	yes	List<integer>	30	1..5	トップジャンルからのジャンルIDの配列。
第一階層から順にレスポンス。
3	nameJa	ジャンル名	yes	string	-	1	
4	nameJaPath	ジャンルパス	yes	List<string>	-	1..5	トップジャンルからのジャンル名の配列。
第一階層から順にレスポンス。
5	level	階層	yes	integer	1	1	ジャンル階層(1~5)。
6	lowest	最下層フラグ	yes	boolean	-	1	・true：最下層ジャンル
・false：最下層以外のジャンル
7	properties	ジャンルプロパティ	yes	properties	-	1..n	設定値。
Level 3~4: properties
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	itemRegisterFlg	商品登録可能フラグ	yes	boolean	-	1	・true：登録可能
・false：登録不可
Level 3: attributes
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	id	商品属性ID	yes	integer	-	1	attributeIdと同一です。
2	nameJa	商品属性名称	yes	string	-	1	※ジャンルとの紐づきにより変更される可能性もございます。
3	dataType	データ型	yes	string	-	1	データ型に応じた以下文字列のいずれか。
・STRING：文字列型
・NUMBER：数値型
・DATE：日付型
4	minLength	最小長	no	integer	-	1	文字列型の最小文字数。
5	maxLength	最大長	no	integer	-	1	文字列型の最大文字数。
6	minValue	最小値	no	float	-	1	数値型の最小値。
7	maxValue	最大値	no	float	-	1	数値型の最大値。
8	dateFormat	日付フォーマット	no	string	-	1	日付型のフォーマット。
9	unit	単位	no	string	-	1	楽天が定義している第一候補の単位。
10	subUnits	サブ単位	yes	List<string>	-	1	楽天が定義しているその他の単位の候補。
11	properties	商品属性プロパティ	yes	properties	-	1	設定値を返却します。
12	dictionaryValues	推奨値	yes	List<dictionaryValues>	-	1	attributeに紐づく推奨値。
Level 4: properties
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	rmsMandatoryFlg	必須項目フラグ	yes	boolean	-	1	attributeが必須項目か否か。
・true：必須 (必須 or いずれか必須）
・false：任意 (ナビゲーション用任意 or 商品ページ用任意）
2	rmsMandatoryType	必須(任意)種別	yes	String	-	1	attributeの必須/任意の種別。
・MANDATORY：必須
・MANDATORY_SELECTABLE：いずれか必須
・OPTIONAL_NAVIGATION ：ナビゲーション用任意
・OPTIONAL_ITEM_PAGE : 商品ページ用任意
3	rmsMultiValueLimit	attribute上限数	yes	integer	-	1	attributeの上限数。
4	rmsInputMethod	attribute入力方式	yes	String	-	1	・DESCRIPTIVE：記述式
・SELECTIVE：選択式
5	rmsSkuUnifyFlg	商品ページ内同一値登録対象フラグ	yes	boolean	-	1	attributeに入力する値がSKU間で一致する必要があるかどうか。
・true：一致する必要がある
・false：一致する必要はない
6	rmsRecommend	推奨値の有無	yes	boolean	-	1	attributeに対する推奨値の有無。
・true：推奨値がある
・false：推奨値がない
Level 4: dictionaryValues
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	id	推奨値id	yes	integer	-	1	推奨値を区別するためのID
2	nameJa	推奨値名称	yes	String	-	1	

失敗した場合

Level 1: base
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	errors	エラー	yes	error	-	1	エラー情報
Level 2: error
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	code	エラーコード	yes	string	-	1	メッセージコードの一覧はこちら。
2	message	エラーメッセージ	yes	string	-	1
Sample
成功した場合
ジャンルに紐づく全ての商品属性＆推奨値を取得し、成功した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/304571/attributes/-/dictionaryValues' \
--header 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
Response in JSON format (Status: 200 OK)
{
    "version": {
    "id": 32,
        "fixedAt": "2024-02-01T22:00:37+09:00"
},
    "genre": {
    "genreId": 304571,
        "genreIdPath": [
        100227,
        100236,
        304571
    ],
        "nameJa": "アジ",
        "nameJaPath": [
        "食品",
        "魚介類・水産加工品",
        "アジ"
    ],
        "level": 3,
        "lowest": true,
        "properties": {
        "itemRegisterFlg": true
    },
    "ancestors": null,
        "siblings": null,
        "children": null,
        "attributes": [
        {
            "id": 3,
            "nameJa": "シリーズ名",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": true,
                "rmsMandatoryType": "MANDATORY",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 13210,
                    "nameJa": "ウェルチ（アサヒ飲料）"
                },
                //...
                {
                    "id": 196401,
                    "nameJa": "前田食品"
                }
            ]
        },
        {
            "id": 298,
            "nameJa": "原産国／製造国",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 250,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": true,
                "rmsMandatoryType": "MANDATORY",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 1321,
                    "nameJa": "アイスランド共和国（アイスランド/氷洲）"
                },
                {
                    "id": 1322,
                    "nameJa": "アイルランド"
                },
                //...
                {
                    "id": 182663,
                    "nameJa": "レユニオン"
                }
            ]
        },
        {
            "id": 335,
            "nameJa": "総個数",
            "dataType": "NUMBER",
            "minLength": null,
            "maxLength": null,
            "minValue": 1,
            "maxValue": 999999999,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": true,
                "rmsMandatoryType": "MANDATORY_SELECTABLE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4838,
            "nameJa": "総重量",
            "dataType": "NUMBER",
            "minLength": null,
            "maxLength": null,
            "minValue": 0,
            "maxValue": 999999999,
            "dateFormat": null,
            "unit": "g",
            "subUnits": [
                "kg"
            ],
            "properties": {
                "rmsMandatoryFlg": true,
                "rmsMandatoryType": "MANDATORY_SELECTABLE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4836,
            "nameJa": "総容量",
            "dataType": "NUMBER",
            "minLength": null,
            "maxLength": null,
            "minValue": 0,
            "maxValue": 999999999,
            "dateFormat": null,
            "unit": "ml",
            "subUnits": [
                "L"
            ],
            "properties": {
                "rmsMandatoryFlg": true,
                "rmsMandatoryType": "MANDATORY_SELECTABLE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 2359,
            "nameJa": "アジの種類",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 20899,
                    "nameJa": "シマアジ"
                },
                {
                    "id": 20900,
                    "nameJa": "マアジ"
                },
                {
                    "id": 20901,
                    "nameJa": "ムロアジ"
                }
            ]
        },
        {
            "id": 2360,
            "nameJa": "アジの地域ブランド",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 20902,
                    "nameJa": "関アジ"
                }
            ]
        },
        {
            "id": 968,
            "nameJa": "オーガニック認証機関・基準",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 5,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 34142,
                    "nameJa": "有機JAS"
                },
                //...
                {
                    "id": 34138,
                    "nameJa": "ABマーク"
                }
            ]
        },
        {
            "id": 2361,
            "nameJa": "産地（都道府県）",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 250,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 26102,
                    "nameJa": "北海道"
                },
                //...
                {
                    "id": 26148,
                    "nameJa": "沖縄"
                }
            ]
        },
        {
            "id": 969,
            "nameJa": "自然派志向",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 35902,
                    "nameJa": "オーガニック・有機"
                },
                {
                    "id": 35909,
                    "nameJa": "特別栽培"
                }
            ]
        },
        {
            "id": 2362,
            "nameJa": "食品の梱包方法",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 50,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "SELECTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 20903,
                    "nameJa": "化粧箱入り・贈答用"
                }
            ]
        },
        {
            "id": 2363,
            "nameJa": "食品の状態",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 5,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 20904,
                    "nameJa": "冷凍"
                },
                //...
                {
                    "id": 175794,
                    "nameJa": "パック"
                }
            ]
        },
        {
            "id": 2364,
            "nameJa": "鮮魚・海藻の用途",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 5,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 32420,
                    "nameJa": "刺身"
                },
                //...
                {
                    "id": 32424,
                    "nameJa": "1尾丸ごと"
                }
            ]
        },
        {
            "id": 4839,
            "nameJa": "単品重量",
            "dataType": "NUMBER",
            "minLength": null,
            "maxLength": null,
            "minValue": 0,
            "maxValue": 999999999,
            "dateFormat": null,
            "unit": "g",
            "subUnits": [
                "kg"
            ],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4837,
            "nameJa": "単品容量",
            "dataType": "NUMBER",
            "minLength": null,
            "maxLength": null,
            "minValue": 0,
            "maxValue": 999999999,
            "dateFormat": null,
            "unit": "ml",
            "subUnits": [
                "L"
            ],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 970,
            "nameJa": "不使用添加物",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 500,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 35906,
                    "nameJa": "着色料"
                },
                //...
                {
                    "id": 177708,
                    "nameJa": "人工甘味料"
                }
            ]
        },
        {
            "id": 4867,
            "nameJa": "旬の時期",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 50,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 10,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 195427,
                    "nameJa": "1月"
                },
                //...
                {
                    "id": 195438,
                    "nameJa": "12月"
                }
            ]
        },
        {
            "id": 4844,
            "nameJa": "単品（個装）個数",
            "dataType": "NUMBER",
            "minLength": null,
            "maxLength": null,
            "minValue": 1,
            "maxValue": 999999999,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4830,
            "nameJa": "販売形態（並行輸入品）",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 50,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "SELECTIVE",
                "rmsSkuUnifyFlg": true,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 194999,
                    "nameJa": "並行輸入品"
                }
            ]
        },
        {
            "id": 4831,
            "nameJa": "販売形態（訳あり）",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 50,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "SELECTIVE",
                "rmsSkuUnifyFlg": true,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 195000,
                    "nameJa": "訳あり"
                }
            ]
        },
        {
            "id": 2,
            "nameJa": "ブランド名（カナ）",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 3,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4845,
            "nameJa": "消費期限",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 500,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 197303,
                    "nameJa": "製造日から15日未満"
                },
                //...
                {
                    "id": 197315,
                    "nameJa": "製造日から5年 ～"
                }
            ]
        },
        {
            "id": 4846,
            "nameJa": "賞味期限",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 500,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 197290,
                    "nameJa": "製造日から15日未満"
                },
                //...
                {
                    "id": 197302,
                    "nameJa": "製造日から5年 ～"
                }
            ]
        },
        {
            "id": 4847,
            "nameJa": "製造者",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4866,
            "nameJa": "販売者",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 3006,
            "nameJa": "保存方法",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 50,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4402,
            "nameJa": "名称",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4849,
            "nameJa": "輸入者",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        },
        {
            "id": 4,
            "nameJa": "シリーズ名（カナ）",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_ITEM_PAGE",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            },
            "dictionaryValues": []
        }
    ]
}
}
ジャンルに紐づく特定の商品属性、及びそれに紐づく推奨値を取得し、成功した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/304571/attributes/298/dictionaryValues' \
--header 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
Response in JSON format (Status: 200 OK)
{
    "version": {
    "id": 32,
        "fixedAt": "2024-02-01T22:00:37+09:00"
},
    "genre": {
    "genreId": 304571,
        "genreIdPath": [
        100227,
        100236,
        304571
    ],
        "nameJa": "アジ",
        "nameJaPath": [
        "食品",
        "魚介類・水産加工品",
        "アジ"
    ],
        "level": 3,
        "lowest": true,
        "properties": {
        "itemRegisterFlg": true
    },
    "ancestors": null,
        "siblings": null,
        "children": null,
        "attributes": [
        {
            "id": 298,
            "nameJa": "原産国／製造国",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 250,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": true,
                "rmsMandatoryType": "MANDATORY",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 1321,
                    "nameJa": "アイスランド共和国（アイスランド/氷洲）"
                },
                //...
                {
                    "id": 182663,
                    "nameJa": "レユニオン"
                }
            ]
        }
    ]
}
}
ジャンルに紐づく特定の商品属性、及びそれに紐づく推奨値を取得し、成功した場合 (※page, limitのパラメータ指定時)
Request (curl コマンドを使った例)
curl --location --dump-header --request GET 'https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/110001/attributes/3303/dictionaryValues?page=1&limit=100' \
--header 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
Linkヘッダーの例
link: </genres/110001/attributes/3303/dictionaryValues?page=2&limit=100>; rel="next", </genres/110001/attributes/3303/dictionaryValues?page=4&limit=100>; rel="last"
Response in JSON format (Status: 200 OK)
{
    "version": {
    "id": 32,
        "fixedAt": "2024-02-01T22:00:37+09:00"
},
    "genre": {
    "genreId": 110001,
        "genreIdPath": [
        100005,
        113084,
        110001
    ],
        "nameJa": "花束・切花",
        "nameJaPath": [
        "花・ガーデン・DIY",
        "花・観葉植物",
        "花束・切花"
    ],
        "level": 3,
        "lowest": true,
        "properties": {
        "itemRegisterFlg": true
    },
    "ancestors": null,
        "siblings": null,
        "children": null,
        "attributes": [
        {
            "id": 3303,
            "nameJa": "植物の種類",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 50,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": false,
                "rmsMandatoryType": "OPTIONAL_NAVIGATION",
                "rmsMultiValueLimit": 1,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 30228,
                    "nameJa": "苔玉"
                },
                {
                    "id": 36414,
                    "nameJa": "キッコウリュウ"
                },
                //...
                {
                    "id": 180517,
                    "nameJa": "タンゴール"
                }
            ]
        }
    ]
}
}
LINK HEADER PATTERN SAMPLE
ページネーションの指定により、以下のバリエーションがあります。

1) 100件ずつ取得し、最初の100件取得

/genres/110729/attributes/1/dictionaryValues?page=1&limit=100
Link: </genres/110729/attributes/1/dictionaryValues?page=2&limit=100>; rel="next",
  </genres/110729/attributes/1/dictionaryValues?page=33&limit=100>; rel="last"
2) 100件ずつ取得し、途中の100件取得

/genres/110729/attributes/1/dictionaryValues?page=3&limit=100
Link: </genres/110729/attributes/1/dictionaryValues?page=1&limit=100>; rel="first",
  </genres/110729/attributes/1/dictionaryValues?page=2&limit=100>; rel="prev",
  </genres/110729/attributes/1/dictionaryValues?page=4&limit=100>; rel="next",
  </genres/110729/attributes/1/dictionaryValues?page=33&limit=100>; rel="last"
3) 100件ずつ取得し、最後の100件取得

/genres/110729/attributes/1/dictionaryValues?page=33&limit=100
Link: </genres/110729/attributes/1/dictionaryValues?page=1&limit=100>; rel="first",
  </genres/110729/attributes/1/dictionaryValues?page=32&limit=100>; rel="prev"
指定したジャンルIDが別のジャンルIDに統合されていた場合
ジャンル統合のイメージ
レスポンスフォーマットは、Response：200の時と同様です。
指定したジャンルIDが別のジャンルIDに統合されていた場合は、統合先のジャンル情報を返却します。


ジャンル変更での統合実施後に、統合元ジャンルへリクエスト
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/566023/attributes/304/dictionaryValues' \
--header 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
統合先ジャンルの情報を返す
Response in JSON format (Status: 301 OK)
{
    "version": {
    "id": 32,
        "fixedAt": "2024-02-01T22:00:37+09:00"
},
    "genre": {
    "genreId": 303656,
        "genreIdPath": [
        100371,
        555086,
        303656
    ],
        "nameJa": "Tシャツ・カットソー",
        "nameJaPath": [
        "レディースファッション",
        "トップス",
        "Tシャツ・カットソー"
    ],
        "level": 3,
        "lowest": true,
        "properties": {
        "itemRegisterFlg": true
    },
    "ancestors": null,
        "siblings": null,
        "children": null,
        "attributes": [
        {
            "id": 1,
            "nameJa": "ブランド名",
            "dataType": "STRING",
            "minLength": null,
            "maxLength": 100,
            "minValue": null,
            "maxValue": null,
            "dateFormat": null,
            "unit": null,
            "subUnits": [],
            "properties": {
                "rmsMandatoryFlg": true,
                "rmsMandatoryType": "MANDATORY",
                "rmsMultiValueLimit": 3,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": true
            },
            "dictionaryValues": [
                {
                    "id": 6928,
                    "nameJa": "クリスプ"
                },
                {
                    "id": 6929,
                    "nameJa": "クリフメイヤー"
                },
                //...
                {
                    "id": 1985,
                    "nameJa": "ジーナシス"
                }
            ]
        }
    ]
}
}
失敗した場合
指定したattributeIdが不正な場合
Response in JSON format (Status: 400 NG)
{
  "errors": [
    {
      "code": "invalidAttributeId",
      "message": "The attributeId parameter is invalid."
    }
  ]
}
商品属性情報が存在しない場合
Response in JSON format (Status: 404 NG)
{
  "errors": [
    {
      "code": "notAttributeFound",
      "message": "Not attribute found."
    }
  ]
}
