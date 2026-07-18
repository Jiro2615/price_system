RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/navigationapi2/codesreference/
サービス: ジャンル・商品属性情報検索API

サービス一覧へ戻る / NavigationAPI 2.0

NavigationAPI Response Error Codes Reference
HTTP Status Code
Code	Status	Description
200	OK	リクエストが成功しました。
301	OK	リクエストが成功しました。
※指定したジャンルIDが別のジャンルIDに統合されていた場合など
400	Bad Request	リクエストが不正です。
401	Unauthorized	インターフェースの呼び出し権限がありません。
403	Forbidden	リクエストが禁止されています。
404	Not Found	リクエストパスが存在しません。
405	Method Not Allowed	指定されたメソッドはサポートされていません。
415	Unsupported Media Type	指定されたメディアタイプはサポートされていません。
429	Too Many Requests	リクエスト制限数を超えました。
500	Internal Server Error	サーバ内部にエラーが発生しました。
503	Service Unavailable	サービスが一時的に過負荷やメンテナンスで使用不可能です。
504	Bad Gateway	応答時間（60000ms）がタイムアウトしました。
Error code list
Generic errors
	エラーコード	エラーメッセージ	発生原因	対応方法	HTTP ステータスコード
1	invalidGenreId	The genreId parameter is invalid.	genreIdが不正	genreIdを見直したうえで、有効なgenreIdを指定してください	400
2	invalidShowGenreAncestors	The showGenreAncestors parameter is invalid.	showGenreAncestorsパラメータが不正	true もしくは false を指定してください	400
3	invalidShowGenreSiblings	The showGenreSiblings parameter is invalid.	showGenreSiblingsパラメータが不正	true もしくは false を指定してください	400
4	invalidShowGenreChildren	The showGenreChildren parameter is invalid.	showGenreChildrenパラメータが不正	true もしくは false を指定してください	400
5	invalidAttributeId	The attributeId parameter is invalid.	attributeIdの値が不正(1より小さいまたは、4294967295より大きい）	attributeIdを見直したうえで、有効なattributeIdを指定してください	400
6	invalidPage	The page parameter is invalid.	page parameterが不正(1より小さいまたは、10000より大きい）	有効な値を指定してください	400
7	invalidLimit	The limit parameter is invalid.	limit parameterが不正(1より小さいまたは、10000より大きい）	有効な値を指定してください	400
8	invalidPageAndLimit	Both page and limit parameters are required.	page もしくはlimitどちらかが足りない	pageとlimitをどちらも有効な値で指定してください	400
9	requiredAttributeId	The attributed parameter is required.	page・limitを利用する際にattributeIdが指定されていない	pagination機能を利用する際は、attributeIdを指定してください	400
10	notGenreFound	Not genre found.	ジャンルが存在しない	genreIdを見直したうえで、有効なgenreIdを指定してください	404
11	notAttributeFound	Not attribute found.	商品属性情報が存在しない	genreIdとattributeIdを見直したうえで、有効なgenreIdとattributeIdを指定してください	404
12	notDictionaryValueFound	Not dictionaryValue found.	推奨値が存在しない	genreIdとattributeIdを見直したうえで、有効なgenreIdとattributeIdを指定してください	404
