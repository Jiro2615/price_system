RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/inventoryapi2_1/codereference/
サービス: 在庫API 2.1（InventoryAPI 2.1）

サービス一覧へ戻る / InventoryAPI 2.1

InventoryAPI 2.1 Response Codes Reference
HTTPステータスコード定義
コード	ステータス	内容
200	OK	リクエストが成功しました。
204	No Content	リクエストが成功しました。
400	Bad Request	リクエストが不正です。
404	Not Found	リクエストパスが見つかりません。
500	Internal Server Error	サーバ内部にエラーが発生しました。
エラーコード定義
汎用エラー
No.	エラーコード	エラーメッセージ	原因	対応方法	HTTP ステータスコード
1	GE0007	Requested path doesn't exist	リクエストパスが存在しない場合	リクエストパスをご確認の上、再度お試しください。	400
2	IE0001	${fieldName} is mandatory.	必須項目を設定してない場合	例：quantity is mandatory

必須項目を指定してください。	400
3	IE0002	${fieldName} has an invalid value : ${invalidValue}.	項目に不正な値を設定した場合	例：manageNumber has an invalid value : !~/invalidManageNumber.

項目に不正な値が設定されているため、項目をご確認の上、再度お試しください。	400
4	IE0003	${fieldName} must be between ${min} and ${max}.	項目に不正な値（範囲外）を指定した場合	例：quantity must be between 0 and 99999.

項目の値をご確認の上、再度お試しください。	400
5	IE0004	Max length of ${fieldName} must be within ${value} bytes.	項目に最大サイズを超えた値を指定した場合	例：Max length of variantId must be within 40 bytes.

項目の値をご確認の上、再度お試しください。	400
6	IE0105	One or both of minQuantity and maxQuantity query parameters is/are required.	最小在庫数と最大在庫数のいずれも指定しなかった場合	最小在庫数か最大在庫数、もしくはその両方を指定した上、再度お試しください。	400
7	IE0113	minQuantity value, must be smaller than maxQuantity.	最小在庫数に最大在庫数より大きな数を指定した場合	最小在庫数に最大在庫数以下の数を指定した上、再度お試しください。	400
8	IE0116	Too many search results, please change the query of search.	在庫数検索の結果が1001件以上の場合	最小在庫数と最大在庫数を変更した上、再度お試しください。	400
9	IE0117	After update, the quantity must be between 0 and 99999.	在庫の更新後の値が範囲外となる場合	quantityに指定の値をご確認の上、再度お試しください。	400
10	IE0121	Inventory cannot be added because the size has reached the limit.	在庫の更新後、1つのmanageNumberに組み合わされたvariantIdが400を超える場合	manageNumberとvariantIdの値をご確認の上、再度お試しください。	400
11	IE0500	Cannot use relative mode to update inventory which the combination of manageNumber and variantId does not exist.	modeに「Relative」を指定したが、manageNumberとvariantIdの組み合わせが存在しない場合	manageNumberとvariantIdの値をご確認の上、再度お試しください。	400
12	GE0014	Not found for inputs; identifier=${identifier}	リクエストするリソースが存在しない場合	リクエストをご確認の上、再度お試しください。	404
13	CE0001	Your request could not be processed due to a conflict with another process. Please try again after a short while.	リクエストが現在のサーバーの状態と競合した場合	時間を空けて再度お試しください。	409
14	GE0019	Failed to get the shop status.	楽天側で店舗のステータス確認に失敗した場合	時間を空けて再度お試しください。	500
15	X0000	An unexpected error has occurred	-	サーバーエラーのため、時間を空けて再度お試しください。	500
16	IE0118	${invalidValue} is invalid because it is not defined in ${invalidFieldName} of shop setting.	存在しないoperationLeadTimeまたはshipFromIdsを指定した場合	例：2 is invalid because it is not defined in shipFromIds of shop setting.

項目の値をご確認の上、再度お試しください。	400
17	GE0011	Request body is missing or is empty without any attributes.	リクエストボディが存在していないか空である場合	リクエストボディを設定の上、再度お試しください。	400
18	IE1105	This endpoint is disabled for the shop not migrated to SKU.	SKU移行前に登録、更新または削除しようとした場合	SKU移行前の場合InventoryAPI(在庫API)をご利用ください。	400
19	IE1101	${fieldName} exceeds the maximum number of entries allowed.	リストの要素数が上限に超えてリクエストしようとした場合	リストの要素数を削減した上、再度お試しください。	400
20	IE1102	There are multiple occurrences of the same manageNumber and variantId : ${invalidValue}	一括取得・登録・更新（inventories.bulk.get, inventories.bulk.upsert）の際、商品管理番号およびSKU管理番号が重複してリクエストしようとした場合	重複した値を削除した上、再度お試しください。	400
　※200番以外のHTTP Status Codeについては、HTTPの規格で規定されているものに従います。
