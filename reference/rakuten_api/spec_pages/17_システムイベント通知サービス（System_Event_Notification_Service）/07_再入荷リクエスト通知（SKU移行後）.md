RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/systemeventnotificationservice/systemnotificationnotifier2/
サービス: システムイベント通知サービス（System Event Notification Service）

サービス一覧へ戻る / システムイベント通知サービス / システム情報通知

RMS WEB SERVICE : 再入荷リクエスト通知（SKU移行後）
「システム情報通知」の再入荷リクエスト通知サービスで提供される、格納データについて定義します。
インターフェース項目は、「システム情報通知」の内容に準じます。

実装の前に、「RMS WEB SERVICE : システムイベント通知サービス/４．制約事項」をご確認ください。

こちらのページはSKU移行後（SKU移行後リクエスト）用の再入荷リクエスト通知となります。
SKU移行前（SKU移行前リクエスト）に対する通知については「再入荷リクエスト通知（移行前）」をご確認ください。
※SKU移行後も継続して再入荷リクエスト通知を利用希望の場合は、4100：再入荷リクエスト通知（SKU移行前）と別に、4200：再入荷リクエスト通知（SKU移行後）のお申込みが必要です。

再入荷リクエスト通知
No	Element	Description	Sample	Note
Element Name	Attribute Value	Element Name	Attribute Value
1	value1	pageURL	データ1	商品ページURL	/_superagent001/ntf00001/	/<店舗URL>/<商品管理番号>/
2	value2	orgItemNumber	データ2	商品番号	testntf00001	全角文字含む、最大255桁
3	value3	inventoryType	データ3	在庫タイプ	2	0：在庫設定なし
1：通常在庫設定
2：SKU在庫設定
4	value4	variantId	データ4	SKU管理番号	1234567	半角英数字または"-", "_"
5	value5	-	データ5			
6	value6	-	データ6			
7	value7	-	データ7			
8	value8	-	データ8			
9	value9	-	データ9			
10	value10	entryDate	データ10	再入荷リクエスト登録日付	2013/10/10	YYYY/MM/DD
