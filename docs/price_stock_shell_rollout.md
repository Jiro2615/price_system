# 価格・在庫チェックの限定Shell導入

既定はChrome。出品・購入・候補収集のブラウザは切り替えません。
`price_check_from_db.py --browser shell` または起動元プロセスの環境変数
`PRICE_STOCK_BROWSER=shell` で価格在庫チェックだけ切り替えます。
環境変数は起動時に読みます。`.env` に書くだけの切替はサポートしません。
共通起動関数は引数未指定なら従来どおりChromeです。

## 実運用PCへの準備

最新コミットを取得後、実際のワーカーと同じPython環境で実行：

```powershell
python -m playwright install chromium-headless-shell
```

検証用venvではなく本番のPythonを指定してください。インストールがなければ
起動エラーになり、黙ってChromeに切り替えることはありません。

実行中ジョブがなくなってから、ワーカーを起動するPowerShellで：

```powershell
$env:PRICE_STOCK_BROWSER = 'shell'
```

そのPowerShellから通常のワーカーを起動してください。既に動作している
Orchestrator/サービス/別ターミナルには伝わりません。管理サービス経由の場合は
そのサービスの環境設定に指定し、全ジョブ終了後に計画的に再起動します。
開始ログの `browser=shell` を確認します。Shellは同一バッチでも50件ごとに
browser/context/page/Playwrightを終了して再起動し、従来のエラー時再起動でもShellを維持します。

## 戻す場合

同じ起動元で `PRICE_STOCK_BROWSER=chrome` に戻し、現在のジョブ終了後に
ワーカーを起動し直します。CLIでは `--browser chrome` が環境変数より優先です。
取得異常が増えた場合はログを保存してChromeへ戻してください。
DBスキーマ、商品判定、同価格の選択順、楽天送信ロジックは変更していません。

今回のコード反映だけで本番モードは変わりません。まず1ワーカーだけに適用し、
価格・在庫・ギフト判定とエラー率を確認してから展開します。
