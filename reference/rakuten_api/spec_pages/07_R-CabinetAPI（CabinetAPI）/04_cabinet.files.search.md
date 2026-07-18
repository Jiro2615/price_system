RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/cabinetapi/cabinetfilessearch/
サービス: R-CabinetAPI（CabinetAPI）

サービス一覧へ戻る / CabinetAPI


RMS WEB SERVICE : cabinet.files.search




この機能を利用すると、画像名を指定して画像を検索することができます。
画像の登録、更新、削除後の情報が本機能の取得情報に反映されるまでの時間は最短10秒です。
ページング機能(offset, limit)を用いて情報取得をしている時には画像の登録、更新、削除はお控えください。情報が正しく取得できない場合があります。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/cabinet/files/search	GET
Request
HTTP Header
No	Key	Value	Note
1	Authorization	ESA Base64(serviceSecret:licenseKey)	
Query parameters
No	Parameter	Description	Type	Mandatory	Multiplicity	Note
1	fileId	画像ID	Integer	△	0,1	画像ID、ファイル名、画像名のうちいずれか一つを必ず指定する必要あります。

複数指定した場合、（１）画像ID　（２）ファイル名　（３）画像名の優先順位で検索します。
2	filePath	ファイル名	String	0,1
3	fileName	画像名	String	0,1
4	folderId	フォルダID	Integer		0,1	フォルダID、フォルダ名を両方指定した場合は、フォルダIDを優先して検索します。
5	folderPath	フォルダ名	String		0,1
6	offset	検索結果取得ページ数	Integer		0,1	1を基準値とした検索結果取得ページ数

　例）100件データが存在する場合を仮定し、検索結果の1ページあたりの取得上限数を10に設定した場合
　offset=1、limit=10 → 1件目～10件目のデータを取得する
　offset=2、limit=10 → 11件目～20件目のデータを取得する
　offset=3、limit=10 → 21件目～30件目のデータを取得する

　例）100件データが存在する場合を仮定し、検索結果の1ページあたりの取得上限数を20に設定した場合
　offset=1、limit=20 → 1件目～20件目のデータを取得する
　offset=2、limit=20 → 21件目～40件目のデータを取得する
　offset=3、limit=20 → 41件目～60件目のデータを取得する
7	limit	検索結果取得上限数	Integer		0,1	検索結果の1ページあたりの取得上限数

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
XML:result
No	Element	Description	Type	

Size(byte)

	

Multiplicity

	Note
1	

result.status

	ステータス	

XML:status

	-	1	

interfaceId=cabinet.files.search


2	

result.cabinetFilesSearchResult

	

フォルダ内画像情報検索結果

	XML:cabinetFilesSearchResult
	-	1	
XML:cabinetFilesSearchResult
No	Element	Description	Type	

Size(byte)

	Multiplicity	Note
1	

cabinetFilesSearchResult.resultCode

	

結果コード

	Integer	4	1	
2	

cabinetFilesSearchResult.fileAllCount

	全画像数	Integer	5	1	
3	

cabinetFilesSearchResult.fileCount

	

返却画像数

	Integer	5	1	
4	

cabinetFilesSearchResult.files

	

画像情報リスト

	

XML : files


	-	1	
XML:files
No	Element	Description	Type	

Size(byte)

	Multiplicity	Note
1	file	ファイル情報	XML : file
	-	1 ... n	
XML:file
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	file.FolderId	

フォルダID

	Integer	10	1	
2	file.FolderName	

フォルダ名

	String	50	1	
3	file.FolderNode	

フォルダノード

	Integer	1	1	1 or 2 or 3
4	file.FolderPath	

フォルダパス

	String	153	1	

path1/path2/path3
　

区切り文字は"/"です。


5	file.FileId	画像ID	Integer	10	1	
6	file.FileName	画像名	String	50	1	
7	file.FileUrl	画像保存先	String	265	1	
8	file.FilePath	file名	String	50	1	
9	file.FileType	画像タイプ	Integer	1	1	
10	file.FileSize	画像サイズ (KB)	Decimal	7	1	
11	file.FileWidth	画像の横幅	Integer	4	1	
12	file.FileHeight	画像の縦幅	Integer	4	1	
13	file.FileAccessDate	画像アクセス日	Date	10	1	
14	file.TimeStamp	画像情報更新日時	DateTime	19	1	
Response sample


<?xml version="1.0" encoding="UTF-8"?>
<result>
    <status>
        <interfaceId>cabinet.files.search</interfaceId>
        <systemStatus>OK</systemStatus>
        <message>OK</message>
        <requestId>714a4983-555f-42d9-aeea-89dae89f2f55</requestId> 
        <requests>
            <folderId>aaa</folderId>
            <fileName>bbb</fileName>
        </requests>
    </status>
    <cabinetFilesSearchResult> 
        <resultCode>0</resultCode>
        <fileAllCount>1000</fileAllCount>
        <fileCount>100</fileCount>
        <files>
            <file>
                <FolderId>10001</FolderId>
                <!-- omission -->
            </file>
            <file>
                <FolderId>10002</FolderId>
                <!-- omission -->
            </file>
            <file>
                <FolderId>10003</FolderId>
                <!-- omission -->
            </file>
        </files>
    </cabinetFilesSearchResult>
</result>
