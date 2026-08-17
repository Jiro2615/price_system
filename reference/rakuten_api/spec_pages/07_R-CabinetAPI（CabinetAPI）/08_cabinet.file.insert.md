RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/cabinetapi/cabinetfileinsert/
サービス: R-CabinetAPI（CabinetAPI）

サービス一覧へ戻る / CabinetAPI

RMS WEB SERVICE : cabinet.file.insert
この機能を利用すると、画像ファイルを指定して画像を登録することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/cabinet/file/insert	POST
Request
独自または非標準のHTTPクライアントライブラリを使用する場合、下記赤字は手動で設定する必要があります。
現代的なHTTPクライアントライブラリ（例: Guzzle HTTP 7.x、Apache HTTP Client 5.xなど）を使用する場合、これらのパラメータを明示的に指定する必要がなく、自動的に設定されサーバーに渡されます。

HTTP Header
No	Key	Value	Note
1	Authorization	ESA Base64(serviceSecret:licenseKey)	
2	Content-Type	multipart/form-data; boundary=【boundaryの文字列】	boundaryは必ず設定してください。
boundaryに利用できる文字はRFC 7578を準拠してください。
※（[0-9],[a-z],[A-Z],[-]）、最大長70文字
3	Content-Length	リクエストボディの合計サイズ（バイト）	例として、リクエストボディの合計サイズが1000バイトを送信する場合、「Content-Length: 1000」の指定が必要です。
0は設定できません。
Query parameters
None

HTTP Body
このAPI は、Content-Type: multipart/form-data を使用したリクエストボディが必要です。
このボディは、複数のパートで構成され、それぞれがファイルやAPIのパラメータ（XML形式）を含みます。

正しいフォーマットをご確認いただくには、下部の「sample multipart/form-data」をご参照ください。

Boundary Separator
マルチパートデータの各パートを区切るため、リクエストボディの各パートは「--【boundaryの文字列】」で始まります。
最後のパートは「--【boundaryの文字列】--」で終わります。

Content-Disposition Header Field
No	Key	Value	Note
1	Content-Disposition	form-data; name="【xmlまたはfile】"; filename="【ファイル名】"	各パートのContent-Disposition設定が必要です。

name="xml"を指定する場合、filenameは不要です。
Form Values
No	Key	Description	Mandatory	Type　	Note
1	xml	リクエスト	○	String	APIのパラメータ
2	file	画像情報	○	binary	HTMLのフォームを使ったファイルアップロード

1ファイルあたりの重さ ： 2MBまで

1ファイルあたりのサイズ ： 横3840×縦3840pixelまで

登録可能な形式 ： JPEG、GIF、アニメーションGIF、PNG、TIFF、BMP
※PNG、TIFF、BMP形式の画像はJPEGに変換  (その他の形式はエラー)
XML : request
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	request.fileInsertRequest	画像情報登録要求	XML : fileInsertRequest	-	○	1	
XML : FILEINSERTREQUEST
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	fileInsertRequest.file	画像情報	XML : file	-	○	1	
XML : FILE
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	file.fileName	登録画像名	String	50	○	1	50バイト以内（全角25文字以内/半角50文字以内）
 
使用禁止文字 ： 機種依存文字（コントロールコード除く）、半角カタカナ
 　
全角スペース → 半角スペースに変換
　
スペースのみは不可
　
前後にスペースがある場合は、スペースを自動削除
　
タグは無効（入力した場合は、タグと判断されたものを削除して表示）
2	file.folderId	登録先フォルダID		Integer	10	○	0,1	
3	file.filePath	登録file名	String	20		0,1	20バイト以内（半角20文字以内）
　
デフォルト値 ： img[数字8桁].gif / jpg or imgrc[数字10桁].gif / jpg
　
入力可能文字 ： 半角英数字（小文字）/記号は「-」「_」のみ
　
使用禁止文字 ： 機種依存文字（コントロールコード含む）、img+8桁の数字、imgrc+10桁の数字
　
スペースのみ/字間にスペースは不可
　
前後にスペースがある場合は、スペースは自動削除
　
タグは無効（入力した場合はタグと判断されたものを削除して表示）
4	file.overWrite	上書きフラグ	boolean	-		0,1	デフォルト値 ： false
※overWriteがtrueかつfilePathの指定がある場合、filePathをキーとして画像情報を上書きすることができます。

Request Sample
sample request body
<?xml version="1.0" encoding="UTF-8"?>
<request>
    <fileInsertRequest>
        <file>
            <fileName>ZZZ</fileName>
            <folderId>0</folderId>
            <filePath>img136281.jpg</filePath>
            <overWrite>true</overWrite>
        </file>
    </fileInsertRequest>
</request>
sample multipart/form-data
POST /public/1.0/cabinet/file/insert HTTP/1.1
Host: 127.0.0.1:8011
Proxy-Connection: keep-alive
Content-Length: 999999 --サイズ
User-Agent: Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36
Origin: chrome-extension://hgmloofddffdnphfgcellkdfbfbjeloo
Content-Type: multipart/form-data; boundary=【boundaryの文字列】
Accept: */*
Accept-Encoding: gzip,deflate
Accept-Language: ja,en-US;q=0.8,en;q=0.6
 
--【boundaryの文字列】
Content-Disposition: form-data; name="xml"
 
<?xml version="1.0" encoding="UTF-8"?>
<request>
    <fileInsertRequest>
        <file>
            <fileName>ZZZ</fileName>
            <folderId>0</folderId>
            <filePath>img136281.jpg</filePath>
            <overWrite>true</overWrite>
        </file>
    </fileInsertRequest>
</request>

--【boundaryの文字列】
Content-Disposition: form-data; name="file"; filename="Chrysanthemum.jpg"
Content-Type: image/jpg
 
[画像ファイルのバイナリデータ]
--【boundaryの文字列】--
Response
HTTP Header
No	Key	Value
1	Content-Type		text/xml
HTTP Body
XML : result
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	result.status	ステータス	XML : status	-	1	interfaceId=cabinet.file.insert
2	result.cabinetFileInsertResult	画像情報登録結果	XML : cabinetFileInsertResult	-	1	
XML : cabinetFileInsertResult
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	cabinetFileInsertResult.resultCode	結果コード	Integer	4		1	
2	cabinetFileInsertResult.FileId	画像ID	Integer	10		1	
Response Sample
sample multipart/form-data
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <status>
        <interfaceId>cabinet.file.insert</interfaceId>
        <systemStatus>OK</systemStatus>
        <message>OK</message>
        <requestId>714a4983-555f-42d9-aeea-89dae89f2f45</requestId>
        <requests />
    </status>
    <cabinetFileInsertResult>
        <resultCode>0</resultCode>
        <FileId>0</FileId>
    </cabinetFileInsertResult>
</result>
