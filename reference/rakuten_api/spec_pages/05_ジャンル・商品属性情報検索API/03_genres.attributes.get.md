RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/navigationapi2/genresattributesget/
サービス: ジャンル・商品属性情報検索API

サービス一覧へ戻る / NavigationAPI 2.0

RMS WEB SERVICE : genres.attributes.get
Overview
この機能を利用すると、指定したジャンルIDに紐づく商品属性情報を取得することができます。
ジャンル情報のみを取得したい場合には、genres.get をご利用ください。

※商品の登録／更新時にジャンル・商品属性・推奨値の紐づきの整合性チェックを行っています。
　推奨値の取得を行う場合は genres.attributes.dictionaryValues.get をご利用ください。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/{genreId}/attributes/{attributeId}	GET
Request
HTTP Header
No	Key	Value
1	Authorization	ESA Base64(serviceSecret:licenseKey)
Path Parameter
No	Parameter Name	Logical Name	Required	Type	Description
1	genreId	ジャンルID	yes	integer	6桁のジャンルID。
0を指定すると、第一階層のジャンルを返却します。
2	attributeId	商品属性ID	no	integer	特定の商品属性情報を取得したい場合に指定してください。
※Level 3: attribute > id としてレスポンスされます。
Query Parameter
No	Parameter Name	Logical Name	Required	Type	Description
1	showAncestors	祖先ジャンルフラグ	no	boolean	・true：取得する
・false：取得しない（デフォルト）
2	showSiblings	兄弟ジャンルフラグ	no	boolean	・true：取得する
・false：取得しない（デフォルト）
3	showChildren	子ジャンルフラグ	no	boolean	・true：取得する
・false：取得しない（デフォルト）
HTTP Body
None

Response
HTTP Header
No	Key	Value	Description
1	Content-Type	application/json;  charset=utf-8	
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
3	dataType	データ型	yes	string	-	1	データ型に応じた以下文字列のいずれかを返却します。
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
Level 4: properties
No	Parameter Name	Logical Name	Not Null	Type	Max Byte	Multiplicity	Description
1	rmsMandatoryFlg	必須項目フラグ	yes	boolean	-	1	attributeが必須項目か否か。
・true：必須(必須 or いずれか必須）
・false：任意 (ナビゲーション用任意 or 商品ページ用任意）
2	rmsMandatoryType	必須(任意)種別	yes	String	-	1	attributeの必須/任意の種別。
・MANDATORY：必須
・MANDATORY_SELECTABLE：いずれか必須
・OPTIONAL_NAVIGATION ：ナビゲーション用任意
・OPTIONAL_ITEM_PAGE : 商品ページ用任意
3	rmsMultiValueLimit	attribute上限数	yes	integer	-	1	attributeの上限数。
4	rmsInputMethod	attribute入力方式	yes	String	-	1	・DESCRIPTIVE：記述式
・SELECTIVE：選択式
5	rmsSkuUnifyFlg	商品ページ内同一値登録対象フラグ		yes	boolean	-	1	attributeに入力する値がSKU間で一致する必要があるかどうか。
・true：一致する必要がある
・false：一致する必要はない
6	rmsRecommend	推奨値の有無	yes	boolean	-	1	attributeに対する推奨値の有無。
・true：推奨値がある
・false：推奨値がない

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
ジャンルに紐づく全ての商品属性を取得した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/304571/attributes' \
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
            }
        },
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
        }
    ]
}
}
ジャンルに紐づく特定の商品属性を取得した場合
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/304571/attributes/4838' \
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
            }
        }
    ]
}
}
Response: 301 (genreId={6桁のジャンルID}で成功し、かつ統合元ジャンルの指定だった場合)
レスポンスフォーマットは、Response：200の時と同様です。
指定したジャンルIDが別のジャンルIDに統合されていた場合は、統合先のジャンル情報を返却します。

ジャンル統合のイメージ


ジャンル変更での統合実施後に、統合元ジャンルへリクエスト
Request (curl コマンドを使った例)
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/navigation/genres/566023/attributes' \
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
            "id": 36,
            "nameJa": "カラー",
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
                "rmsMultiValueLimit": 5,
                "rmsInputMethod": "DESCRIPTIVE",
                "rmsSkuUnifyFlg": false,
                "rmsRecommend": false
            }
        },
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
            }
        },
        //...
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
            }
        }
    ]
}
}
失敗した場合
attributeIdが不正な場合
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
