RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/purchaseitemapi/searchorderitem/
サービス: 購入商品API（PurchaseItemAPI）

サービス一覧へ戻る / PurchaseItemAPI

RMS WEB SERVICE : searchOrderItem
Overview
この機能を利用すると、「注文検索」を行うことができます。こちらは同期処理となります。
検索結果が 15000 件以上の場合、15001 件目以降の受注番号は取得できません。

SKUプロジェクトにて追加・修正となる項目は背景色を緑に変更しています。
Endpoint
Endpoint
https://api.rms.rakuten.co.jp/es/2.0/purchaseItem/searchOrderItem/
Request
Request Method
Method
POST
Request Header
Key	Value
Authorization	ESA Base64(serviceSecret:licenseKey)
Content-Type	application/json; charset=utf-8
Request Parameter
Level 1: base
No	Logical Name	Parameter Name	Required	Type	Max Byte	Default	Description	Sample
1	ステータスリスト	orderProgressList	no	List <Number>	128	-	以下のいずれか

100: 注文確認待ち
200: 楽天処理中
300: 発送待ち
400: 変更確定待ち
500: 発送済
600: 支払手続き中
700: 支払手続き済
800: キャンセル確定待ち
900: キャンセル確定	[100,300]
2	サブステータスIDリスト	subStatusIdList	no	List <Number>	512	-	・作成されたサブステータスIDを指定する場合は複数のIDを同時に指定することが可能です。
・[-1]を指定した場合、サブステータスが設定されていない注文を取得することが可能です。
[-1]を指定する場合、ステータスリスト（orderProgressList）の指定が必須となります。	[100,300]
3	期間検索種別	dateType	yes	Number	2	-	以下のいずれか

1: 注文日
2: 注文確認日
3: 注文確定日
4: 発送日
5: 発送完了報告日
6: 決済確定日	3
4	期間検索開始日時	startDatetime	yes	Datetime	25	-	YYYY-MM-DDThh:mm:ss+09:00

過去 730 日(2年)以内の注文を指定可能	2021-10-14T00:00:00+0900
5	期間検索終了日時	endDatetime	yes	Datetime	25	-	YYYY-MM-DDThh:mm:ss+09:00
開始日から 63 日以内	2021-11-15T23:59:59+0900
6	販売種別リスト	orderTypeList	no	List <Number>	32	-	以下のいずれか

1: 通常購入
4: 定期購入
5: 頒布会
6: 予約商品	4,6
7	検索キーワード種別	searchKeywordType	no	Number	2	0	以下のいずれか

0: なし
1: 商品名
2: 商品番号
7: SKU管理番号
8: システム連携用SKU番号
9: SKU情報	2
8	検索キーワード	searchKeyword	no	String	4000	-	以下の入力チェックが適用されます

・機種依存文字などの不正文字以外
・キーワード前後の空白は削除
・全角、半角にかかわらず、それぞれのキーワードの文字数は下記のとおり

1: 商品名：1024 文字以下
2: 商品番号：127文字以下
7: SKU管理番号：40文字以下
8: システム連携用SKU番号：96文字以下
9: SKU情報：400文字以下	keyword
9	ページングリクエストモデル	PaginationRequestModel	no	PaginationRequestModel	-	-		
Level 2: PaginationRequestModel
No	Logical Name	Parameter Name	Required	Type	Max Byte	Default	Description	Sample
1	1ページあたりの取得結果数	requestRecordsAmount	yes	Number	10	30	最大 1000 件まで指定可能	30
2	リクエストページ番号	requestPage	yes	Number	10	1		5
3	並び替えモデルリスト	SortModelList	no	List <SortModel>	-	-	現在は「注文日時」のみ指定可能	
Level 3: SortModel
No	Logical Name	Parameter Name	Required	Type	Max Byte	Default	Description	Sample
1	並び替え項目	sortColumn	yes	Number	5	1	以下のいずれか

1: 注文日時	1
2	並び替え方法	sortDirection	yes	Number	5	2	以下のいずれか

1: 昇順（小さい順、古い順）
2: 降順（大きい順、新しい順）	2
Response
HTTP Status
Code	Status	Description
200	OK	リクエストが成功した。
400	Bad Request	リクエストが不正である。
404	Not Found	Request-URI に一致するものを見つけられなかった。
405	Method Not Allowed	許可されていないメソッドを使用しようとした。
500	Internal Server Error	サーバ内部にエラーが発生した。
503	Service Unavailable	サービスが一時的に過負荷やメンテナンスで使用不可能である。
Response Header
Key	Value
Content-Type	application/json;charset=utf-8
Response Parameter
Level 1: base
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	メッセージモデルリスト	MessageModelList	yes	List <MessageModel>	-	-		
2	注文番号リスト	orderNumberList	no	List <String>	40960	-		["123456-20220506-10640141","123456-20220529-10635460"]
3	ページングレスポンスモデル	PaginationResponseModel	no	PaginationResponseModel	-	-		
Level 2: MessageModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	メッセージ種別	messageType	yes	String	16	-	以下のいずれか

・INFO
・ERROR
・WARNING	INFO
2	メッセージコード	messageCode	yes	String	128	-	メッセージコードの一覧はMessage Codes Reference参照	MESSAGE_CODE_SAMPLE
3	メッセージ	message	yes	String	1024	-	メッセージサンプル
Level 2: PaginationResponseModel
No	Logical Name	Parameter Name	Not Null	Type	Max Byte	Default	Description	Sample
1	総結果数	totalRecordsAmount	no	Number	10	-		997
2	総ページ数	totalPages	no	Number	10	-		34
3	リクエストページ番号	requestPage	no	Number	10	-	リクエストされたページ数	2
Sample
検索結果が取得できた場合
Request (curl コマンドを使った例)
curl -X POST \
  https://api.rms.rakuten.co.jp/es/2.0/purchaseItem/searchOrderItem/ \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "dateType": 1,
    "startDatetime": "2021-12-14T00:00:00+0900",
    "endDatetime": "2022-01-14T00:00:00+0900",
    "PaginationRequestModel" :
    {
        "requestRecordsAmount" : 30,
        "requestPage" : 1,
        "SortModelList" : [
            {
                "sortColumn" : 1,
                "sortDirection" : 1
            }
        ]
    }
}'
Response in JSON format (Status: 200 OK)
{
    "orderNumberList": [
        "123456-20220101-00068801",
        "123456-20220101-00067801",
        "123456-20220101-00062801",
        "123456-20220101-00059801",
        "123456-20220101-00058801",
        "123456-20220101-00057801",
        "123456-20220101-00048801",
        "123456-20220101-00046801",
        "123456-20220101-00043801",
        "123456-20220101-00039801",
        "123456-20220101-00038801",
        "123456-20220101-00037801",
        "123456-20220101-00030801",
        "123456-20220101-00028801",
        "123456-20220101-00023801",
        "123456-20220101-00022801",
        "123456-20220101-00019801",
        "123456-20220101-00017801",
        "123456-20220101-00016801",
        "123456-20220101-00076901",
        "123456-20220101-00074901",
        "123456-20220101-00073901",
        "123456-20220101-00072901",
        "123456-20220101-00071901",
        "123456-20220101-00070901",
        "123456-20220101-00068901",
        "123456-20220101-00067901",
        "123456-20220101-00066901",
        "123456-20220101-00065901",
        "123456-20220101-00064901"
    ],
    "MessageModelList": [
        {
            "messageType": "INFO",
            "messageCode": "ORDER_EXT_API_SEARCH_ORDER_INFO_101",
            "message": "注文検索に成功しました。"
        }
    ],
    "PaginationResponseModel": {
        "totalRecordsAmount": 79,
        "totalPages": 3,
        "requestPage": 1
    }
}
検索結果がなかった場合
Request (curl コマンドを使った例)
curl -X POST \
  https://api.rms.rakuten.co.jp/es/2.0/purchaseItem/searchOrderItem/ \
  -H 'Authorization: ESA xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "dateType" : 1,
    "startDatetime" : "2021-10-14T00:00:00+0900",
    "endDatetime" : "2021-12-14T00:00:00+0900",
    "PaginationRequestModel" :
    {
        "requestRecordsAmount" : 30,
        "requestPage" : 1,
        "SortModelList" : [
            {
                "sortColumn" : 1,
                "sortDirection" : 1
            }
        ]
    }
}'
Response in JSON format (Status: 200 OK)
{
    "orderNumberList": [],
    "MessageModelList": [
        {
            "messageType": "INFO",
            "messageCode": "ORDER_EXT_API_SEARCH_ORDER_INFO_102",
            "message": "注文検索に成功しました。(検索結果０件)"
        }
    ],
    "PaginationResponseModel": {
        "totalRecordsAmount": null,
        "totalPages": null,
        "requestPage": null
    }
}
