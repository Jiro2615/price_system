RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/shoppageapi/codereference/
サービス: 店舗ページAPI（ShopPageAPI）

サービス一覧へ戻る / ShopPageAPI

RMS WEB SERVICE : ShopPageAPI Response Code Reference
※SKUプロジェクトにてチェック内容が変更となるエラーについては背景色を緑に変更しています。

HTTP Status Code
Code	Status	Description
200	OK	リクエストが成功しました。
204	No Content	リクエストが成功しました。
400	Bad Request	リクエストが不正です。
401	Unauthorized	インターフェースの呼び出し権限がありません。
404	Not Found	リクエストパスが見つかりません。
405	Method Not Allowed	指定されたメソッドはサポートされていません。
415	Unsupported Media Type	指定されたメディアタイプはサポートされていません。
422	Unprocessable Entity	リクエストボディに不正があって処理が継続できません。
500	Internal Server Error	サーバ内部にエラーが発生しました。
503	Service Unavailable	サービスが一時的に過負荷やメンテナンスで使用不可能です。
※400と422の違い、400はHTTP HeaderやQuery Parameterにエラーがあった場合や、HTTP Bodyのフォーマットにエラーがあった場合に返されます。422はHTTP Bodyのフォーマットが正しく、各Parameterの値チェックなどでエラーが発生した場合に返されます。

Error code list
ShopPageAPIで扱うエラーコードの一覧は以下の通りです。

Generic errors
No	Error Code	Error Message	Description	MetaData	Staus Code
1	GE0001	Invalid value on field {0}	リクエストパスに不正な値が含まれます。

{0}:エラーが発生したリクエストパス	-	400
2	GE0002	Invalid value on parameter {0}	クエリパラメータが正しくありません。

{0}:エラーが発生したパラメータ名	-	400
3	GE0003	Invalid value on header {0}	リクエストヘッダの内容が正しくありません。

{0}:エラーが発生したヘッダー名	-	400
4	GE0005	Missing required parameter {0}	必須のクエリパラメータが未指定です。

{0}:エラーが発生したパラメータ名	-	400
5	GE0006	Missing required header {0}	必須のリクエストヘッダが未指定です。

{0}:エラーが発生したヘッダー名	-	400
6	GE0007	Requested path does not exist	リクエストパスが見つかりません。	-	404
7	GE0008	The call is unauthorized. Check Authorization header	インターフェース呼び出し権限がありません。	-	401
8	GE0009	The HTTP method utilized is not supported by this resource	このメソッドはサポートされていません。	-	405
9	GE0011	Request body cannot be processed	リクエストボディが正しくありません。	-	400
10	GE0012	Media Type {0} is not supported	指定されたメディアタイプはサポートされていません。
{0}:エラーが発生したメディアタイプ	-	415
11	GE0014	The resource with id: {0} does not exist.	指定されたIDをもつリソースは存在しません。

{0}:値	-	404
12	GE1001	The resource with {0}: {1} already exist	指定された値をもつリソースが既に存在します。

{0}:キー
{1}:値	-	400
13	GE1002	Operation is forbidden for layout type {0}	そのAPIで操作できないレイアウトタイプが指定されています。	-	400
14	X0000	An unexpected error has occurred	予期せぬエラーが発生しました。	-	500
Business validation errors
No	Error Code	Error Message	MetaData	Description	Staus Code
1	BE0001	Missing required field	{
  "propertyPath": #(String)
}	必要なフィールドが指定されていません。
propertyPath:エラーが発生したパラメータ名	422
2	BE0002	Length Exceeded	{
  "propertyPath": #(String), 
  "max": #(Integer)
}	文字列の文字数が上限を超えています。
propertyPath:エラーが発生したパラメータ名
max:最大文字数	422
3	BE0003	Number of elements exceeds limit	{
  "propertyPath": #(String),
  "max": #(Integer),
  "detail": #(String)
}	要素数が上限を超えています。
propertyPath:エラーが発生したパラメータ名
max:最大要素数
detail:要素の詳細情報	422
4	BE0004	Unapproved Links	{
  "propertyPath": #(String)
}	フィールドに許可されない外部リンクが含まれます。
propertyPath:エラーが発生したパラメータ名	422
5	BE0005	Illegal characters	{
  "propertyPath": #(String)
}	フィールドに不正な文字が含まれます。
propertyPath:エラーが発生したパラメータ名	422
6	BE0006	Unapproved html	{
  "propertyPath": #(String), 
  "invalidValueList": [
    {
      "tag": #(String), 
      "attribute": #(String), 
      "value": #(String) 
    }
  ]
}	フィールドに許可されないHTMLタグが含まれます。
propertyPath:エラーが発生したパラメータ名
invalidaValueList[]:エラーがあったタグまたは属性のリスト

invalidaValueList[].tag: エラーがあったタグ名
invalidValueList[].attribute: エラーがあった属性名
invalidValueList[].value: エラーの値	422
7	BE0007	Number out of range	{
  "propertyPath": #(String), 
  "min": #(Integer), 
  "max": #(Integer) 
}	フィールドの数値が許容範囲外です。
propertyPath:エラーが発生したパラメータ名
min:最小値
max:最大値	422
8	BE0008	Unapproved image path format	{
  "propertyPath": #(String)
}	許可されない画像パスです。
propertyPath:エラーが発生したパラメータ名	422
9	BE0009	Missing dependent input	{
  "propertyPath": #(String)
}	依存入力がありません。
propertyPath:エラーが発生したパラメータ名	422
10	BE0010	The field cannot be set	{
  "propertyPath": #(String)
}	条件によりフィールドの値をセットできません。
propertyPath:エラーが発生したパラメータ名	422
11	BE0011	The field cannot be updated	{
  "propertyPath": #(String)
}	このフィールドは更新できません。
propertyPath:エラーが発生したパラメータ名	422
12	BE0012	The combination of values is invalid	{
  "propertyPath": #(String)
}	無効な組み合わせが含まれています。
propertyPath:エラーが発生したパラメータ名	422
13	BE0013	The Widget type cannot be created/updated	{
  "propertyPath": #(String),
  "detail": #(String)
}	指定されたパーツ種別は登録または更新ができません。
propertyPath:エラーが発生したパラメータ名
detail:エラーの詳細情報	422
14	BE0014	The page cannot be created	{
  "detail": #(String) 
}	指定されたレイアウトは登録できません。
detail:エラーの詳細情報	422
15	BE0015	Unapproved contents	{
  "propertyPath": #(String)
}	指定された値は入力できません。
propertyPath:エラーが発生したパラメータ名	422
16	BE0016	Specified value does not match any of the acceptable values	{
  "propertyPath": #(String)
}	無効な値が指定されています。
propertyPath:エラーが発生したパラメータ名	422
17	BE0101	Requested category not found	{
  "propertyPath": #(String)
}	指定されたIDのカテゴリが見つかりません。
propertyPath:エラーが発生したパラメータ名	422
18	BE0102	Requested category is non-displayable	{
  "propertyPath": #(String)
}	指定されたIDのカテゴリは表示不可です。
propertyPath:エラーが発生したパラメータ名	422
19	BE0103	Requested category is not allowed category type	{
  "propertyPath": #(String)
}	指定されたIDのカテゴリは指定できない種別のカテゴリIDです。
propertyPath:エラーが発生したパラメータ名	422
20	BE0201	Requested item not found	{
  "propertyPath": #(String)
}	指定された商品管理番号をもつ商品が見つかりません。
propertyPath:エラーが発生したパラメータ名	422
21	BE0202	Requested item is not allowed item type	{
  "propertyPath": #(String)
}	この商品種別は許可されていません。
propertyPath:エラーが発生したパラメータ名	422
22	BE0203	Requested item is soko item	{
  "propertyPath": #(String)
}	倉庫指定商品／仮倉庫の商品は登録できません。
SKU移行後は上記に加え、すべてのSKUが倉庫指定の商品も登録できません。
propertyPath:エラーが発生したパラメータ名	422
23	BE0204	Requested item is yamiichi item	{
  "propertyPath": #(String)
}	闇市商品は登録できません。
propertyPath:エラーが発生したパラメータ名	422
24	BE0205	Requested item is search disable item	{
  "propertyPath": #(String)
}	検索不可商品は登録できません。
propertyPath:エラーが発生したパラメータ名	422
25	BE0206	Requested item is adult item	{
  "propertyPath": #(String)
}	アダルト商品は登録できません。
propertyPath:エラーが発生したパラメータ名	422
26	BE0301	Invalid format	{
  "propertyPath": #(String), 
  "detail": #(String) 
}	フォーマットが不正です。
propertyPath:エラーが発生したパラメータ名
detail:フォーマットの詳細情報
※ 日付の場合は、Format must be YYYY-MM-DDThh:mm:ssZなど	422
27	BE0302	Invalid period settings	{
  "propertyPath": #(String)
}	公開開始時間は公開終了時間よりも早い必要があります。
公開終了時間は公開開始時間よりも遅い必要があります。
propertyPath:エラーが発生したパラメータ名	422
28	BE0304	Invalid minimum set time of startTime	-	公開開始時間は現在時刻の1分後以降である必要があります。	422
29	BE0305	Reservation time overlapping	-	公開開始時間と公開終了時間は他の予約の時間帯と重ならない必要があります。	422
30	BE0306	Value Not Unique	{
  "propertyPath": #(String)
}	値が一意ではありません。
propertyPath:エラーが発生したパラメータ名	422
31	BE0307	Widget already used	{
  "linked": [
    {
      "layoutId": #(String) 
    }
  ]
}	パーツを削除もしくはレイアウトに紐付ける場合、そのパーツは他のレイアウトに紐づけられていない必要があります。
linked[]:パーツが紐づけされているレイアウトのリスト

linked[].layoutId:パーツが紐づけれているレイアウトのID	422
32	BE0308	Specifying a layout that cannot be deleted	-	指定されたレイアウトは削除できません。	422
33	BE0309	Specifying a layout that cannot be replaced	-	デフォルトのレイアウトのみ置き換えることができます。	422
34	BE0310	Dependent data cannot be found	{
  "linked": [
    {
      "widgetId": #(String),
      "navigationId":#(String)
    }
  ]
}	依存データを更新できませんでした。
linked[]:更新できなかったデータのリスト

linked[].widgetId:更新できなかったパーツのID
linked[].navigationId:更新できなかったナビゲーションのID	422
35	BE0312	First public layout must be default layout	-	初回のレイアウト公開はデフォルトレイアウトの必要があります。	422
36	BE0313	Invalid settings of startTime and endTime	{
  "propertyPath": #(String)
}	公開開始時間もしくは公開終了時間の指定が不正です。
propertyPath:エラーが発生したパラメータ名	422
37	BE0314	Invalid min and max price settings	{
  "propertyPath": #(String)
}	最低価格もしくは最高価格の指定が不正です。
propertyPath:エラーが発生したパラメータ名	422
38	BE0315	Invalid minimum set time of endTime	{
  "propertyPath": #(String)
}	公開終了時間の最小値よりも早い時間が設定されています。
propertyPath:エラーが発生したパラメータ名	422
39	BE0316	URL exceeded max slashes limit	{
  "propertyPath": #(String),
  "max": #(Integer)
}	URLに指定できる最大の"/"数を超えています。
propertyPath:エラーが発生したパラメータ名
max:最大の"/"数	422
40	BE0317	URL part is out of range	{
  "propertyPath": #(String),
  "min": #(Integer),
  "max": #(Integer)
}	URLの"/"間に指定された文字が範囲内に収まっていません。
propertyPath:エラーが発生したパラメータ名
max:最大の文字数
min:最小の文字数	422
41	BE0401	Requested couponCode not found	{
  "propertyPath": #(String)
}	指定されたクーポンコードをもつクーポンが見つかりません。
propertyPath:エラーが発生したパラメータ名	422
42	BE0402	Requested couponCode is not displayable	{
  "propertyPath": #(String)
}	クーポンの状態は公開可能である必要があります。
propertyPath:エラーが発生したパラメータ名	422
43	BE0403	Requested couponCode is invalid period	{
  "propertyPath": #(String)
}	有効期間内のクーポンを指定する必要があります。
propertyPath:エラーが発生したパラメータ名	422
44	BE0404	Requested couponCode is reached the usage limit	{
  "propertyPath": #(String)
}	クーポンの全利用回数上限を超えています。
propertyPath:エラーが発生したパラメータ名	422
45	BE0405	Requested couponCode is not allowed discount type	{
  "propertyPath": #(String)
}	定額値引き、もしくは定率値引きのクーポンを指定する必要があります。
propertyPath:エラーが発生したパラメータ名	422
46	BE0501	Requested video is not found	{
  "propertyPath": #(String)
}	指定された動画IDが存在しません。
propertyPath:エラーが発生したパラメータ名	422
47	BE0502	Requested video is not owned by the shop	{
  "propertyPath": #(String)
}	指定された動画IDはこのショップでは使えません。
propertyPath:エラーが発生したパラメータ名	422
48	BE0601	Shop is out of target genres	-	この店舗ジャンルでは実行することはできません。	422
