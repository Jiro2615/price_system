RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/cabinetapi/cabinetfiledelete/
サービス: R-CabinetAPI（CabinetAPI）

サービス一覧へ戻る / CabinetAPI

RMS WEB SERVICE : cabinet.file.delete

 

この機能を利用すると、画像IDを指定して画像を削除フォルダに移動することができます。

Endpoint / HTTP Method
Endpoint	HTTP Method
https://api.rms.rakuten.co.jp/es/1.0/cabinet/file/delete	POST
Request
HTTP Header
No	Key	Value	Note
1	Authorization	ESA Base64(serviceSecret:licenseKey)	
Query parameters

　None

HTTP Body
XML:request
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	request.fileDeleteRequest	画像情報削除要求	XML:fileDeleteRequest	-	○	1	
XML:fileDeleteRequest
No	Element	Description	Type	Size(byte)	Mandatory	Multiplicity	Note
1	fileDeleteRequest.file	画像情報	XML:file	-	○	1	
XML:file
No	Element	
Description
	Type	Size(byte)	Mandatory	Multiplicity	Note
1	file.fileId	画像ID	Integer	10	○	1	
Request Sample


<?xml version="1.0" encoding="UTF-8"?>
<request>
	<fileDeleteRequest>
		<file>
			<fileId>xxx</fileId>
		</file>
	</fileDeleteRequest>
</request>


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

	ステータス	XML : status	-	1	

nterfaceId=cabinet.file.delete


2	

result.cabinetFileDeleteResult

	

画像情報削除結果

	XML : cabinetFileDeleteResult	-	1	
XML:cabinetFileDeleteResult
No	Element	Description	Type	Size(byte)	Multiplicity	Note
1	

cabinetFileDeleteResult.resultCode

	結果コード	Integer	4	1	
Response sample


<?xml version="1.0" encoding="UTF-8"?>
<result>
	<status>
		<interfaceId>cabinet.file.delete</interfaceId>
		<systemStatus>OK</systemStatus>
		<message>OK</message>
		<requestId>714a4983-555f-42d9-aeea-89dae89f2f45</requestId>
	</status>
	<cabinetFileDeleteResult>
		<resultCode>0</resultCode>
	</cabinetFileDeleteResult>
 </result>
