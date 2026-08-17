# TODO.md

## Immediate
- [ ] `rakuten_csv_winscp_upload_and_watch.py` のログ出力量をさらに整理する。
- [ ] `rakuten_csv_price_update_flow.py` の成功/エラー時のサマリーを見やすくする。
- [ ] blocked商品をAPI更新へ回す専用スクリプトを作る。
- [ ] API更新後、blocked商品の価格差分が消えるか確認する。

## Safety
- [ ] `RAKUTEN_1_SFTP_HOSTKEY` / `RAKUTEN_2_SFTP_HOSTKEY` を本番運用前に固定fingerprintへ変更する。
- [ ] `.env` のサンプル `.env.example` を作る。
- [ ] DBパスワード直書き箇所を `.env` 読み込みへ寄せる。
- [ ] `--execute` なしでは絶対に更新しないことを全スクリプトで統一する。

## CSV
- [ ] CSV処理結果件数をDBへ記録する。
- [ ] 楽天処理結果メールとCSVログを照合する。
- [ ] no-op CSVを正式な検証ツールとして整理する。
- [ ] blocked理由を分類できるようにする。

## API
- [ ] `rakuten_price_patch.py` にblocked商品のみ更新モードを追加する。
- [ ] 価格変更率上限・最低価格・最大価格の安全装置を再確認する。
- [ ] API更新ログを `price_update_logs` に統一的に残す。

## Mail
- [ ] `mail_processing_logs` テーブルを作る。
- [ ] 楽天CSV処理結果メールを解析する。
- [ ] Amazon発送メールを解析する。
- [ ] 配達ボックス通知メールを解析する。
- [ ] メールの二重処理防止を入れる。

## Listing
- [ ] 既存の出品ツールのCSV/API仕様を調べる。
- [ ] 楽天出品用DB設計を作る。
- [ ] 出品API化は価格/在庫運用安定後に進める。
