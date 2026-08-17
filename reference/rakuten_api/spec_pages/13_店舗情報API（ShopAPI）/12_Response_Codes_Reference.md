RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/shopapi/response-codes-reference/
サービス: 店舗情報API（ShopAPI）

サービス一覧へ戻る / ShopAPI

RMS WEB SERVICE : ShopAPI Response Code Reference

    1. Code List
    2. validationErrorCode List
    3. invalidValue List

※SKUプロジェクトにてチェック内容が変更となるエラーについては背景色を緑に変更しています。

Code List
ShopAPIのレスポンスは、以下のような形式でCode(結果コード)を含みます。

<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
    <resultCode>N000</resultCode>
    <resultMessageList>
        <resultMessage>
            <code>N000</code>
            <message>Succeeded.</message>
        </resultMessage>
    </resultMessageList>
</shopbiz:shopBizApiResponse>

処理結果に応じた、Code(結果コード)、HTTP Status、メッセージの関係は以下の表の通りです。

No.	Category	Code	HTTP Status Code	Message	Description
1	正常終了	N000	200	Succeeded.	正常に処理が行われました。
2	サーバー起因
（サービス停止・メンテナンス中など）	S900	500	Under maintenance.	メンテナンス中でサービスを提供できません。
3	S901	500	The Service is currently in read-only mode.	読み取り専用モードで運用中のため、更新機能は利用できません。
4	クライアント要因
（クライアントからの入力不備など）	C001	400	Request parameter is invalid.	パラメータのフォーマットバリデーションエラー。
Responce の fieldId にパラメータ名が入ります。
5	C003	400	Requested resource is not found.	指定された Resource が存在しない場合のコードです。
6	C005	400	Requested MediaType is not supported.	Accept や ContentType にAPIが対応していない MediaType を指定された場合のコードです。
7	C006	400	Update data is invalid.	更新データの UniqueKey に問題がある場合などのコードです。

※UniqueKey とは更新したいデータを特定する一意のキーです。例：layoutCommonId 等
8	C007	400	Request Model is invalid.	更新データ Model が不正な場合のコードです。
9	C008	404	Requested data is not found.	指定された Resource のデータが存在しない場合のコードです。
10	C012	400	Number of table elements exceeds limit.	レコード数が許可されている最大数を超えている場合のコードです。
11	C013	400	Validation Error.	更新データに不正な値が含まれてる場合のエラーです。
この場合、バリデーションエラーの種類に応じた検証エラーコードが、レスポンスデータに含まれます。
詳細については、validationErrorCode List をご覧ください。
12	C998	400	Multiple errors occurred.	複数のエラーが発生し、かつすべてのエラーがクライアント要因(コードC~)の場合のコードです。
13	実行エラー
（参照したいデータがない場合や更新しようとするレコードがない場合など）	E101	500	Failed to insert data.	データの登録に失敗した場合のコードです。
14	E102	500	Failed to update data.	データの更新に失敗した場合のコードです。
15	E998	500	Multiple errors occurred.	複数のエラーが発生した場合のコードです。
16	E999	500	Unknown Execution error.	サーバ内でエラーが起こった場合のコードです。
クライアント側で対応不能な場合このコードが返されます。
validationErrorCode List
送信した更新データが正当ではないデータを含む場合、ShopAPIは以下のような形式で validationErrorCode (バリデーションエラーコード)を含んだレスポンスを返します。

<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
    <resultCode>C013</resultCode>
    <resultMessageList>
        <resultMessage>
            <code>C013</code>
            <resourceId>naviButton</resourceId>
            <fieldId>buttonColsPosition</fieldId>
            <validationErrorCode>VE1002</validationErrorCode>
            <minValue>1</minValue>
            <maxValue>3</maxValue>
            <message>VE1002: buttonColsPosition must be between 1 and 3</message>
        </resultMessage>
      </resultMessageList>
</shopbiz:shopBizApiResponse>

validationErrorCode (バリデーションエラーコード)とその原因は、以下の表の通りです。

No	Code	Error Name	Description
1	VSE1000	System Logic Validation Error	クライアントから受け取った要求が、APIの仕様と一致しません。
2	VE1000	Variable Not Set	必須項目がありません。
3	VE1001	Variable Is Set	更新項目に有効でない値が入力されています。
4	VE1002	Number Out Of Range	数値項目が、仕様で定められた範囲を超えています。
5	VE1003	Byte Size Exceeded	セットされた項目が、仕様で定められた最大バイト長を超えています。
6	VE1004	Illegal Characters	不正な文字を含んでいます。
7	VE1005	Unapproved Links	フィールドが、システムが認めていない外部リンクを含んでいます。
8	VE1006	Is Empty String	文字列項目が空白です。
9	VE1007	Length Exceeded	文字列項目が仕様で定められた最大長を超えています。
10	VE1008	Unapproved Html	フィールドが、システムが認めていないHTMLを含んでいます。
11	VE1009	Unapproved Image Url	フィールドが、システムが認めていない画像リンクを含んでいます。
12	VE1010	Missing Dependent Input	更新しようとしている項目が依存している項目が未設定です。
13	VE1011	External Resource Not Found	要求された外部リソースが見つかりません。
14	VE1012	Resource Is In Use	変更しようとしているフィールドが現在使用されています。
15	VE1013	Number Sequence Wrong Ordering	順序データが誤っています。
16	VE1014	R-Cabinet Image Not Found	画像が R-Cabinet に存在しません。
17	VE1015	R-Cabinet Image Size Exceeded	画像データがR-Cabinetの最大許容サイズを超えています。
18	VE1016	Invalid Time Format	時間の形式に誤りがあります。
19	VE1017	Invalid Time	時間データに誤りがあります
(例: 開始時間を終了時間より後に設定しようとした)
20	VE1018	Value Not Unique	このフィールドの値は、一意である必要があります。
21	VE1026	ItemId not found from itemX API	商品管理番号に対する該当商品がありません。
22	VE1028	Featured product is not for sale	倉庫指定商品は目玉商品として登録することができません。

SKU移行後は上記に加え、すべてのSKUが倉庫指定の商品も登録できません。
23	VE1030	Featured product is not displayed for mobile	スマートフォン非表示商品は目玉商品として登録することができません。
24	VE1031	Item with password or featured product is hidden for searching	闇市パスワードかサーチ非表示設定されている時目玉商品として登録することができません。
25	VE1035	No published layout	公開レイアウトのデータが１つも存在しません。
26	VE1036	Value can be set only to specific value	更新する項目は特定の値のみ指定可能です。
27	VE1037	Already saved same data	同一のデータが既に存在します。
28	VE9998	Feature Is Not Supported	現バージョンは、この操作はサポートしていません。
29	VE9999	Unknown Validation Error	その他のバリデーションエラー。楽天にご連絡ください。
invalidValue List
ShopAPIのレスポンスは、以下のような形式で invalidValue を含みます。

<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
    <resultCode>C998</resultCode>
    <resultMessageList>
        <resultMessage>
            <code>C013</code>
            <resourceId>spTopPage</resourceId>
            <fieldId>topPageNote</fieldId>
            <validationErrorCode>VE1008</validationErrorCode>
            <invalidValue>UNCLOSED_OPEN.&lt;font&gt;</invalidValue>
            <message>VE1008: topPageNote must not contain unpaired HTML tag</message>
        </resultMessage>       
    </resultMessageList>
</shopbiz:shopBizApiResponse>


<?xml version="1.0" encoding="UTF-8"?>
<shopbiz:shopBizApiResponse xmlns:shopbiz="http://rakuten.co.jp/rms/mall/shop/biz/api/model/resource">
    <resultCode>C998</resultCode>
    <resultMessageList>
        <resultMessage>
            <code>C013</code>
            <resourceId>spTopPage</resourceId>
            <fieldId>topPageNote</fieldId>
            <validationErrorCode>VE1008</validationErrorCode>
            <invalidValue>TAG.&lt;font&gt;.&lt;dev&gt;</invalidValue>
            <message>VE1008: topPageNote may have unsafe html content</message>
        </resultMessage>       
    </resultMessageList>
</shopbiz:shopBizApiResponse>

invalidValue とその原因は、以下の表の通りです。

No	invalidValue	Error Name	Description
1	TAG	Unapproved tag or attribute	フィールドにシステムが認めていないタグを含んでいます。
2	UNCLOSED_OPEN	Invalid start tag	フィールドの開始タグに誤りがあります。
3	UNEXPECTED_CLOSE	Invalid end tag	フィールドの終了タグに誤りがあります。
4	HTML_COMMENT	Invalid HTML comment	フィールドのHTMLコメントに誤りがあります。
