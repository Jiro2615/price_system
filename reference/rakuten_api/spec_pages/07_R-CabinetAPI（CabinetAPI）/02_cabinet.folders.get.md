RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/cabinetapi/cabinetfoldersget/
サービス: R-CabinetAPI（CabinetAPI）

サービス一覧へ戻る / CabinetAPI

RMS WEB SERVICE : cabinet.folders.get
この機能を利用すると、フォルダの一覧を取得することができます。
フォルダの登録、更新、削除後の情報が本機能の取得情報に反映されるまでの時間は最短10秒です。
ページング機能(offset, limit)を用いて情報取得している時にはフォルダの登録、更新、削除はお控えください。情報が正しく取得できない場合があります。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/cabinet/folders/get	GET
Request
HTTP Header
No	Key	Value	Note
1	Authorization	ESA Base64(serviceSecret:licenseKey)	
Query parameters
No	Parameter	Description	Type	Mandatory	Multiplicity	Note
1	offset	検索結果取得ページ数	Integer		0,1	1を基準値とした検索結果取得ページ数

　例）100件データが存在する場合を仮定し、検索結果の1ページあたりの取得上限数を10に設定した場合
　offset=1、limit=10 → 1件目～10件目のデータを取得する
　offset=2、limit=10 → 11件目～20件目のデータを取得する
　offset=3、limit=10 → 21件目～30件目のデータを取得する

　例）100件データが存在する場合を仮定し、検索結果の1ページあたりの取得上限数を20に設定した場合
　offset=1、limit=20 → 1件目～20件目のデータを取得する
　offset=2、limit=20 → 21件目～40件目のデータを取得する
　offset=3、limit=20 → 41件目～60件目のデータを取得する
2	limit	検索結果取得上限数	Integer		0,1	検索結果の1ページあたりの取得上限数

　例）100件データが存在する場合を仮定し、検索結果の1ページあたりの取得上限数を10に設定した場合
　offset=1、limit=10 → 1件目～10件目のデータを取得する
　offset=2、limit=10 → 11件目～20件目のデータを取得する
　offset=3、limit=10 → 21件目～30件目のデータを取得する
 
　例）100件データが存在する場合を仮定し、検索結果の1ページあたりの取得上限数を20に設定した場合
　offset=1、limit=20 → 1件目～20件目のデータを取得する
　offset=2、limit=20 → 21件目～40件目のデータを取得する
　offset=3、limit=20 → 41件目～60件目のデータを取得する

※値は100まで指定可能です。
HTTP Body
None

Response
HTTP Header
No	Key	Value
1	Content-Type	text/xml
HTTP Body
XML : result
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	result.status	ステータス	XML : status	-	1	interfaceId=cabinet.folders.get
2	result.cabinetFoldersGetResult	フォルダ内画像情報取得結果	XML : cabinetFoldersGetResult	-	1	
XML : cabinetFoldersGetResult
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	cabinetFoldersGetResult.resultCode	結果コード	Integer	4	1	
2	cabinetFoldersGetResult.folderAllCount	全フォルダ数	Integer	5	1	
3	cabinetFoldersGetResult.folderCount	返却フォルダ数	Integer	5	1	
4	cabinetFoldersGetResult.folders	フォルダ情報リスト	XML : folders	-	1	
XML : folders
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	folders.folder	フォルダ情報	XML : folder	-	1 ... n	
XML : folder
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	folder.FolderId	フォルダID	Integer	10	1	
2	folder.FolderName	フォルダ名	String	50	1	
3	folder.FolderNode	フォルダノード	Integer	1	1	1 or 2 or 3
4	folder.FolderPath	フォルダパス	String	153	1	path1/path2/path3
区切り文字は"/"です。

フォルダ作成時にdirectory名を指定した場合、指定したdirectory名。
指定していなかった場合、以下の規則に基づいたフォーマット。
・フォルダIDが8桁未満の場合：8桁になるまでフォルダIDの冒頭に0を補完した値
・フォルダIDが8桁以上の場合：フォルダIDと同一の値
5	folder.FileCount	格納画像数	Integer	10	1	
6	folder.FileSize	フォルダ内の画像の合計サイズ（KB）	Decimal	10,3
※小数点第3位まで	1	
7	folder.TimeStamp	フォルダ更新日時	DateTime	19	1	
Response sample
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <status>
        <interfaceId>cabinet.folders.get</interfaceId>
        <systemStatus>OK</systemStatus>
        <message>OK</message>
        <requestId>714a4983-555f-42d9-aeea-89dae89f2f55</requestId>
    </status>
    <cabinetFoldersGetResult>
        <resultCode>0</resultCode>
        <folderAllCount>1000</folderAllCount> 
        <folderCount>100</folderCount>
        <folders>
            <folder>
                <FolderId>10001</FolderId>
                <!-- omission -->
            </folder>
            <folder>
                <FolderId>10002</FolderId>
                <!-- omission -->
            </folder>
            <folder>
                <FolderId>10003</FolderId>
                <!-- omission -->
            </folder>
        </folders>
    </cabinetFoldersGetResult>
</result>
