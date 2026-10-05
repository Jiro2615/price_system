# 手動最新化の優先書き込み

`rakuten_listing_batch_execute.py` は Amazon/Keepa の取得を従来どおり準備パイプラインで処理し、実更新時だけ `scripts/listing/write_coordination.py` の共有書き込み枠を取得します。

- 同一店舗の楽天/Cabinet API書き込みと出品DB同期を1商品単位で排他にします。
- `--update-existing` かつASINが1件の場合だけ優先扱いです。優先ジョブが書き込みを待っている間、通常バッチは次の書き込みを始めません。処理中の商品は強制停止しません。
- セッションロック用の接続を閉じることで全ロックを解放します。DB障害・30分の待機タイムアウトは安全側に失敗し、API送信しません。
- 1商品の更新終了後も1秒間枠を保持し、別プロセスの次の商品更新とのAPI間隔を確保します。
- フォルダ容量のローカルキャッシュは商品間で引き継ぎません。別プロセスによる画像追加を次の処理で再確認します。
- `LISTING_WRITE_PROTOCOL 1` は、この排他を実装した子プロセス自身が起動時に通知します。Web Orchestratorがこれを確認してから、一括出品と単品最新化の並行準備を許可します。

Web Orchestrator側の受付・キュー・進捗表示変更も必要です。両リポジトリ更新後、エージェントは稼働中ジョブがない時に再起動してください。旧プロセスへの割り込みは許可しません。

テスト:

```powershell
py -3.12 -m unittest -b tests.test_listing_write_coordination tests.test_listing_batch_fast_pipeline
```

テストは外部サービスを使わず、排他順序・例外時解放・DB障害時の送信禁止・更新/DB同期が枠内で実行されることを確認します。
