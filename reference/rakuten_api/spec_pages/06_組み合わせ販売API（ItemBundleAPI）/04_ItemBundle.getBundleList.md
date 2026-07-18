RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itembundleapi/btogetforshop/
サービス: 組み合わせ販売API（ItemBundleAPI）

サービス一覧へ戻る / ItemBundleAPI

RMS WEB SERVICE : ItemBundle.getBundleList
Overview

この機能を利用すると、条件を指定して店舗様の組み合わせ販売一覧を取得することができます。

Endpoint
Endpoint
https://api.rms.rakuten.co.jp/es/1.0/bto/bundles
Request
Request Method
Method
GET
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
Filters
No.	Logical Name	Parameter Name	Required	Type	Max Char	Default	Description	Sample
1	表示設定	bundleState	no	String (Query Parameter)	-	-	商品ページ上の組み合わせ表示設定。
1つの親商品に対して、最大2つの組み合わせを表示させる（ACTIVE）ことが可能です。非表示（INACTIVE）の組み合わせの制限はありません。

設定可能な値は以下のいずれか

・ACTIVE
・INACTIVE	ACTIVE
2	ページサイズ	pageSize	no	Integer (Query Parameter)	-	10	1リクエストで取得できるレコード数。
最大100までです。	50
3	ページ番号	pageNumber	no	Integer (Query Parameter)	-	1	レコードが表示される特定のページ。	3
4	商品管理番号	itemManageNumber	no	String (Query Parameter)	32	-	組み合わせ商品の商品管理番号。
「type」パラメーターが指定された場合、必須になります。
商品管理番号での絞り込みは部分一致検索です。
部分一致検索の詳細についてはこちらを参照してください。	item-001
5	アイテムタイプ	type	no	String (Query Parameter)	-	-	有効な値は以下のいずれか

・parent
・child

上記の「itemManageNumber」が指定された場合、こちらが必須になります。	parent
6	組み合わせ管理名称	bundleName	no	String (Query Parameter)	32	-	組み合わせ管理名称。
組み合わせ管理名称での絞り込みは部分一致検索です。
部分一致検索の詳細についてはこちらを参照してください。	parent
Response
HTTP Status
Code	Status	Description
200	OK	リクエストが成功した。
404	Resource Not Found	リクエストリソースが見つからない。
例：該当店舗に存在しない組み合わせ管理番号を指定し、組み合わせを取得しようとした。
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
1	組み合わせ数	numberOfBundles	yes	Integer	-	取得した組み合わせの合計数	3
2	組み合わせリスト	bundles	yes	List<Bundle>	32	取得した店舗の組み合わせのリスト	
Level 2: Bundle
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
Level 3: bundleItem
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	商品管理番号	itemManageNumber	yes	String	32	組み合わせ商品の商品管理番号	item-002
2	商品削除フラグ	isDeletedItem	yes	Boolean	-	組み合わせ商品がデータベース上削除されたかどうかのフラグ。
商品がデータベース上から削除され、存在しない場合、「true」が返却されます。

有効な値は以下のいずれか

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
1	エラー	errors	yes	List<Error>	-	組み合わせ情報リストを取得する際に発生したエラーのリスト
Level 2: Error
No	Logical Name	Parameter Name	Required	Type	Max Char	Description	Sample
1	メッセージ	message	yes	String	-	エラーの説明	指定された条件に該当する組み合わせはありませんでした。
2	コード	code	yes	String	-	エラーコード。
詳細はこちら。	B1029
Sample
▼ 5.1 店舗のすべての組み合わせが取得できた場合
▼ 5.2 親商品を指定し、結果が取得できた場合
▼ 5.3 親商品を指定し、部分一致検索した結果が取得できた場合
▼ 5.4 子商品を指定し、結果が取得できた場合
▼ 5.5 ページ番号を指定し、結果が取得できた場合
▼ 5.6 親商品とページ番号を指定し、結果が取得できた場合
▼ 5.7 組み合わせ管理名称を指定し、部分一致検索した結果が取得できた場合
▼ 5.8 パラメータ指定に誤りがある場合
