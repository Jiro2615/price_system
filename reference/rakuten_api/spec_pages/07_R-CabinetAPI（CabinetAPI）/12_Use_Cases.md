RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/cabinetapi/cabinetapiusecases/
サービス: R-CabinetAPI（CabinetAPI）

サービス一覧へ戻る / CabinetAPI


RMS WEB SERVICE : Cabinet API Use Cases

CabinetAPIを利用して出来る、Use caseを記載します。




1.R-Cabinetの利用状況を確認する

2.フォルダの一覧を取得する

3.画像を検索する




1. R-Cabinetの利用状況を確認する



1.1  R-Cabinetの各フォルダの画像保存可能数を確認する

　　　1. cabinet.usage.get実行
　　　2. cabinet.folders.get実行

　　→cabinet.usage.getのレスポンス項目"FileMax"の値から、cabinet.folders.getのレスポンス項目"FileCount"の値を引くことで、R-Cabinetの各フォルダの画像保存可能数を確認することができます。



2. フォルダの一覧を取得する



2.1 R-Cabinet内のフォルダ/画像の一覧を取得する

　　　1. cabinet.folders.getを実行
　　　2. cabinet.folders.getのレスポンス項目"FolderId"を、cabinet.folder.files.getのリクエスト項目"folderId"にセットし、実行
　　　　　※取得したFolderIdの数分実行

　　→1と2のレスポンスを組み合わせることで、R-Cabinet内のフォルダ情報とそれに紐づく画像情報を全て確認することができます。



3. 画像を検索する



3.1 検索対象の画像名が、R-Cabinet内の各フォルダに存在するか確認する

　　　1. cabinet.folders.get実行
　　　2. レスポンス項目"FolderId"を、cabinet.files.searchのリクエスト項目"folderId"にセットし、実行
　　　　　※取得したFolderIdの数分実行

　　→R-Cabinet内の各フォルダに検索対象の画像名が存在するか確認することができます。
