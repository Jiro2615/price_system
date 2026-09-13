# 多品種・長時間ブラウザ比較（本番への切替ではありません）

## 通常の使い方

最新の feature/rakuten-listing をpullし、初回セットアップ済みなら
tools/browser_probe/run_probe.cmd をダブルクリックしてください。

標準では通常処理のDB接続設定を使い、amazon_productsから
「未チェック、または6時間以上前にチェック」のASINを古い順に最大100件取得します。
price_check_from_db.py の通常選択と同じ条件です。
必須 B07QP2L8LC、定期購入確認用 B019SKZXV8、数量差確認用 B0F2HTH5H9 を追加。
追加商品10件ごとにこの3商品を再挿入し、一巡後は同じ順序で巡回します。

DB接続は開始時のASIN取得だけ。サーバー側の読み取り専用トランザクションを指定します。
checked_at、価格、在庫、ジョブ状態、ロック、DBスキーマを更新しません。
ブラウザ側の取得処理では従来通りDB接続・保存を禁止。出品・購入・カート追加も行いません。
DB取得失敗や対象0件で固定3件に黙って切り替えることはありません。

## 初回セットアップ

リポジトリのルートでPowerShellを開いて実行します。system32では実行しません。
既存ワーカーとは別の仮想環境を使用します。Chrome本体のインストールも必要です。

```powershell
py -3.12 -m venv tools/browser_probe/.venv
tools/browser_probe/.venv/Scripts/python.exe -m pip install -r tools/browser_probe/requirements.txt
tools/browser_probe/.venv/Scripts/python.exe -m playwright install chromium --only-shell
```

通常のワーカーでstats方式を使っている場合は、期限・状態・優先順をその方式に合わせます。
ただし検証では仕事の確保（UPDATEやFOR UPDATE）を行いません。

```powershell
tools/browser_probe/.venv/Scripts/python.exe tools/browser_probe/interaction_probe.py --use-stats
```

対象数と時間を変更する例（最大100件、各ラウンド30分×2回）:

```powershell
tools/browser_probe/.venv/Scripts/python.exe tools/browser_probe/interaction_probe.py --db-limit 100 --hours 6 --seconds 1800 --rounds 2
```

## 比較方法と所要時間

両方式とも専用匿名ブラウザを起動したまま再利用し、
商品AのChrome→商品AのShell→商品BのChrome→商品BのShell、と交互に取得します。
第2ラウンドではShellを先にします。対象一覧は開始時に一度保存し、両方で共有します。
取得開始時刻の差も保存します。同時刻ではないためAmazon側の変動を完全には排除できません。

標準は各ラウンド15分×2回、計約30分＋末尾処理時間です。
以前の方式とは異なり、両ブラウザが同時に存在しますがページの検査は交互です。
待機中のCPU・メモリも測定値に含むため、旧方式の数字とは直接比較しないでください。
PC全体のメモリ負荷が増えます。まず本番ジョブが止まっている時間帯に実行してください。
本番ワーカー・QNAPの設定変更や再起動は不要です。

最低3商品を確認した後は時間制限で止まります。100件すべてを処理する保証ではありません。
summary.json の distinct_asins_tested と untested_asins を確認し、未検証が多ければ時間を延ばします。
約0.2秒間隔の専有メモリ推移と、取得価格・数量・出品者・配送等の差分を記録します。
必要出品件数は先頭20件（表示総数が少なければその件数）。--offer-limit 40 などで最大100件に拡張できます。
在庫切れなど出品一覧がない商品も取得結果を残しますが、件数判定は未達・不明となり得ます。
必要件数未達は合格扱いにしません。画像は各ラウンド冒頭3件だけ保存します。

## 短い確認とファイル入力

DBを使わない固定3件の動作確認は、明示的に --smoke を指定します。

```powershell
tools/browser_probe/.venv/Scripts/python.exe tools/browser_probe/interaction_probe.py --smoke --seconds 1 --rounds 1
```

任意で --asin-file ファイル名 も使用可能です（UTF-8、1行1件テキスト、またはASIN列のCSV）。
通常運用では指定不要です。

## 停止と結果

Ctrl+Cまたは出力フォルダに空の STOP ファイルを作ると専用テストを停止します。
専用プロセスツリーだけが対象で、本番Chromeを名前で一括終了しません。
商品単位の取得エラー（ギフト判定、タイムアウト等）はエラーを記録して次へ進みます。
その商品は成功扱いにせず、同じラウンドの同じ位置で両方式の結果を残します。
認証・CAPTCHA・DB禁止操作・ブラウザ切断では全体停止し、回避や無限リトライは行いません。

output/browser_probe_日時/ に一覧スナップショット、機種情報、
round*.json、ログ、最初の商品の画像、summary.json を保存します。Gitには含めません。
計測値は約2秒ごとに round*.resources.json へ別途保存します。
停止時は最大20秒の保存猶予後、終了しない専用プロセスだけを強制停止します。
最終集計がない場合は直近の保存値を使用し、summaryの metrics_partial=true と明示します。
強制終了直前・電源断・ディスク書込失敗時の未保存分までは復元できません。再集計:

```powershell
tools/browser_probe/.venv/Scripts/python.exe tools/browser_probe/summarize.py output/browser_probe_日時
```

summary.json と round*.json / log を渡してください。
all_runs_complete は実行完了であり、情報の完全一致・本番採用合格ではありません。
メモリ増加だけでリークと断定せず、ウォームアップ後の推移と反復間の再現性を確認します。

既知: 以前の短時間試験でB0F2HTH5H9は同価格2,792円でも選択出品者が異なり数量2個/15個の差が出ました。
時刻・同価格出品順・ブラウザ差の原因は未確定。多品種・実運用PCでの実測後に採用判断します。
# 50件ごとの完全再起動比較

セットアップ済みの実運用PCで `tools\browser_probe\run_restart_probe.cmd` を実行します。
DB対象＋固定3商品（B07QP2L8LCを含む）を同じ順番で取得し、Chrome／Shellそれぞれ50件×3周、計150件を比較します。
1件につき通常パーサー1回だけです。追加の全出品取得・購入オプション切替・再取得はしません。同価格の表示順による差分は残して報告し、自動的に不合格にはしません。
ブラウザとPlaywrightを完全終了し、Pythonは同じプロセスで継続します。各周のピークCPU/RAM、起動前・終了前・終了後のUSS、古いPID（生成時刻も照合）の残留を記録します。
`output\browser_probe_日時\summary.json` の `runs[].restart_cycles` を確認してください。各周の生データは `round1_chrome_cycles` / `round1_shell_cycles` にあります。
このテストでは `--seconds` の時間打切りは使用せず、件数で完了します。安全用の全体タイムアウトは別にあります。停止はCtrl+Cまたは出力フォルダのSTOPファイルです。
本番ワーカー・DB更新・出品送信は実行しません。短い疎通確認には `run_restart_probe.cmd --smoke --restart-every 3 --cycles 2` を使用できます。
50件以内で十分低いピーク、各終了後のメモリ低下、残留プロセスなし、データ差分の説明が採用判断の条件です。正常完走だけでは採用になりません。
