# 実運用PCでのブラウザ比較（本番切替ではありません）

必須ASIN B07QP2L8LC と B019SKZXV8、B0F2HTH5H9 を匿名ブラウザで反復取得します。
出品・注文・カート追加・DB接続と保存は行いません。本番ワーカーの設定変更や再起動は不要です。
ChromeとHeadless Shellを同じPCで比較します。Chrome自体のインストールが必要です。

## 初回セットアップ

このブランチを取得したリポジトリのルートでPowerShellを開き、以下を1行ずつ実行してください。
専用の仮想環境を作るため、既存ワーカーのPythonパッケージは変更しません。

```powershell
py -3.12 -m venv tools/browser_probe/.venv
tools/browser_probe/.venv/Scripts/python.exe -m pip install -r tools/browser_probe/requirements.txt
tools/browser_probe/.venv/Scripts/python.exe -m playwright install chromium --only-shell
```

## 実行

まず短い動作確認（各方式1回、最低3商品。約2〜5分）:

```powershell
tools/browser_probe/.venv/Scripts/python.exe tools/browser_probe/interaction_probe.py --seconds 1 --rounds 1
```

問題なければ tools/browser_probe/run_probe.cmd をダブルクリックします。
標準はChrome→Shell→Shell→Chromeの順で各15分、計約1時間です。
各試験内はブラウザを再起動せず再利用。商品間10秒休止。末尾の処理により予定時間を超過する場合があります。
本番ワーカーと同時に動かすとPC全体の負荷が増え、測定条件も変わります。まず通常ジョブが止まっている時間帯で実施してください。

長めの比較（各30分×各2回、計約2時間）:

```powershell
tools/browser_probe/.venv/Scripts/python.exe tools/browser_probe/interaction_probe.py --seconds 1800 --rounds 2
```

先頭20件は既存処理の検査上限です。総件数が分かる場合はその少ない方を必要件数とします。
必要件数まで追加読み込みし、未達は記録して終了コード1。総件数不明も明記します。
拡張検証は --offer-limit 40 などで最大100件まで指定可能。全件読込を保証するものではありません。
価格順の並びや表示総数の意味も生結果・画像で確認してください。

## 停止と結果

Ctrl+Cで専用テストプロセスだけを停止します。本番Chromeを名前で一括終了しません。
または画面に出る出力フォルダに空の STOP ファイルを作ると、現在の商品が終了した時点で停止します。
認証・CAPTCHAや取得エラー時は自動再試行せず終了。途中結果は成功扱いにしません。

結果は output/browser_probe_日時/ に保存されGit対象外です。各方式のJSON、ログ、最初の3商品の画像、
商品ごとの取得内容・クリック証跡・必要件数判定、約0.2秒間隔の専有メモリ推移を保存します。
途中停止では最終リソース記録が欠ける場合があります。

```powershell
tools/browser_probe/.venv/Scripts/python.exe tools/browser_probe/summarize.py output/browser_probe_日時
```

正常完了時は summary.json を自動作成します。途中終了後は上のコマンドで集計できます。
生成した summary.json と各 round*.json / log を渡してください。画像には商品ページの表示情報が含まれます。
稼働PCでの実測結果を確認してから採用判断します。今回のpushのみでは本番のブラウザは変わりません。
ChromeとShellのバージョン差、取得時刻による価格・配送・締切の変化、他プロセスの負荷に注意。
専有メモリの増加だけでリークと断定せず、ウォームアップ後の推移と反復間の再現性を見ます。

## push前の短時間検証（2026-09-13）

自動テストに加え、Chrome/Shell各1回・3商品で起動から結果保存まで動作確認。
必要な8件・20件・10件は双方で取得。各方式内で操作前後の取得結果は一致。
ただしB0F2HTH5H9では2,792円の同価格出品から異なる出品者を選び、購入可能数量がChrome 2個 / Shell 15個。
B019SKZXV8の出品カードにも差分あり。時刻・同価格出品の順序・ブラウザ差のどれが原因かは未確定。
そのため本ツールは検証用であり、採用済みの切替機能ではありません。
長時間検証と実運用PC検証は未完了です。summaryのall_runs_completeは実行完了であり、情報一致の合格判定ではありません。
