# ROADMAP.md

## Phase 1: 現在ほぼ完了
楽天価格更新・在庫更新の基礎構築。

### 完了
- PostgreSQL `price_system` 構築
- 楽天商品CSV取り込み
- 楽天商品管理番号-ASIN紐付け
- Amazon価格取得
- target_price / target_stock 計算
- 楽天在庫API bulk-upsert
- 楽天価格API patch
- 楽天normal-item CSV出力
- WinSCP SFTPアップロード
- batch/logs監視
- CSV成功時DB反映
- CSVエラー時blocked化
- 親フロー `rakuten_csv_price_update_flow.py`

## Phase 2: 日常運用フロー安定化
普段の更新を安全に回す。

### 目標
- Amazon価格チェックの対象選定改善
- API価格更新の安全装置強化
- 在庫API更新のログ強化
- blocked商品をAPIへ自動回避
- 実行ログを整理
- 処理結果をCSV/ログで残す

### 方針
日常更新はAPI中心。CSVは大規模更新用。

## Phase 3: 全体価格更新フロー完成
価格計算方式変更時に全商品を安全に再更新する。

### 目標
- CSV flowの安定化
- partial successの精度改善
- エラーログ解析の精度改善
- 処理件数、正常件数、エラー件数のDB記録
- メール結果との照合

## Phase 4: メール処理基盤
将来的な配送情報自動取得のため、メール解析基盤を作る。

### 対象メール
- 楽天CSV処理結果メール
- Amazon発送通知メール
- 配達ボックス通知メール

### 取得したい情報
- CSV処理正常件数 / エラー件数
- Amazon注文番号
- 配送業者
- 追跡番号
- 配達完了日時
- 配達ボックス番号
- 暗証番号

## Phase 5: 出品管理
現在使っている高額な出品ツールの置き換え。

### 最初にやること
- 既存出品ツールの入出力調査
- 楽天出品API/CSV仕様整理
- 出品候補DB設計
- Amazon情報取得との連携
- 商品名、説明文、価格、在庫、画像の扱い整理

## Phase 6: 運用UI
CLIだけでなく、簡易画面やバッチメニューを作る。

### 候補
- Windowsバッチメニュー
- Streamlit
- Flask
- PowerShell GUI
