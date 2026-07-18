# Allowed Phrase Migration Candidates

## Scope

This note inspects only the legacy files under `C:\price_system_listing\reference\legacy_listing`.

Inputs:

- `replacelist_rakuten.txt`
- `kinsiword_rakuten.txt`
- `docs/legacy_rakuten_listing_spec.md`
- current reference code:
  - `scripts/listing/master_loader.py`
  - `scripts/listing/listing_evaluator.py`

Out of scope in this phase:

- changing the current prohibited-word logic
- adding new masters
- Rakuten API / Amazon / Keepa / DB / image processing

## Legacy Behavior Confirmed

`docs/legacy_rakuten_listing_spec.md` confirms:

- `replacelist_rakuten.txt` is a tab-separated source/replacement list.
- empty column 2 means removal.
- `kinsiword_rakuten.txt` / `kinsiword_other.txt` are one-word-per-line masters.
- legacy prohibited-word matching was partial substring matching against title/description.

Current new-system behavior is still simple replacement followed by simple substring match:

- `scripts/listing/listing_evaluator.py`
  - `apply_replacements(...)`
  - `detect_prohibited_words(...)`

This means the legacy replacement list is the best local evidence we have for historical "allow phrase by masking" intent.

## Heuristic Classification Method

All `978` replacement rows were scanned and classified with the following heuristic:

- `high`
  - replacement only inserts whitespace
  - non-space characters stay identical
  - at least one current forbidden word match is broken by that whitespace
- `medium`
  - replacement only inserts whitespace
  - multiple forbidden-word candidates are broken, or the exact target word is ambiguous
- `low`
  - forbidden-word avoidance is possible, but wording also changes or the remaining signal is ambiguous
- `unrelated`
  - removal-only cleanup, generic wording rewrite, brand masking, punctuation normalization, or no visible forbidden-word avoidance signal

## Counts

Row counts:

- `high`: `457`
- `medium`: `23`
- `low`: `25`
- `unrelated`: `473`

Additional observations:

- total replacement rows: `978`
- whitespace-insertion rows: `505`
- removal-only rows: `431`

## High-Confidence Migration Candidates

These are the best candidates to migrate into a future allowed-phrase list because the legacy replacement appears to exist mainly to break a current forbidden-word substring.

### `アルコール`

The current legacy file contains direct whitespace splits for these phrases:

- `アルコールフリー` -> `アル コールフリー`
- `エチルアルコール` -> `エチルアル コール`
- `ステアリルアルコール` -> `ステアリルアル コール`
- `セテアリルアルコール` -> `セテアリルアル コール`
- `ベヘニルアルコール` -> `ベヘニルアル コール`
- `変性アルコール` -> `変性アル コール`
- `無鉱物油、アルコール` -> `無鉱物油、アル コール`

Assessment:

- these are strong evidence that old logic tried to keep cosmetic/ingredient phrases while avoiding raw `アルコール` substring hits
- `ラノリンアルコール` and `ノンアルコール` are not present in the replacement file, so they should not be auto-added solely from legacy evidence
- however, they are good future manual review candidates because they are structurally similar to the high-confidence ingredient phrases above

### `スキン`

Legacy whitespace splits exist for:

- `スキンケース` -> `スキ ンケース`
- `スキンタイプ` -> `ス キ ンタイプ`
- `スキンタイプ:ノーマル` -> `スキ ンタイプ:ノーマル`
- `スキントーン` -> `ス キ ントーン`
- `スキンプロテクトミルク` -> `スキ ンプロテクトミルク`
- `スキンヘッド?` -> `スキ ンヘッド?`
- `スキン中` -> `スキ ン中`

Assessment:

- old logic clearly tried to preserve ordinary `スキン*` compounds
- this supports future allow-phrase handling for phrases like `ドライスキン`
- the exact phrase `ドライスキン` was not found in `replacelist_rakuten.txt`, so adding it should still require human review

### `スプレー`

Legacy whitespace splits exist for:

- `オイルスプレー` -> `オイルス プレー`
- `スプレーボトル` -> `ス プ レーボトル`
- `スプレーしない` -> `スプ レーしない`
- `スプレーするだけ` -> `スプ レーするだけ`
- `スプレーに耐えることができます` -> `スプ レーに耐えることができます`
- `スプレー処理` -> `スプ レー処理`
- `スプレー機能` -> `スプ レー機能`

Assessment:

- this is strong evidence that old logic often treated `スプレー` as a false-positive substring rather than an automatic block
- caution:
  - some phrases such as `スプレー塗料で作られた` were split together with other risky words and should remain review-heavy
  - aerosol / hazardous-material products should still be reviewed separately from phrase masking

### `クリア`

Legacy row:

- `クリア` -> `ク リア`

Assessment:

- this is a notable historical signal
- however, no matching current forbidden word could be directly tied to this row from the present `kinsiword_rakuten.txt`
- classification: `medium`
- recommendation:
  - treat `クリア` as a future manual-review allow-phrase candidate
  - do not auto-adopt it solely from current master evidence

## Medium-Confidence Candidates

These likely reflect forbidden-word avoidance, but multiple current forbidden words overlap or the target phrase is too broad to auto-adopt safely.

- `4輪ガソリン/ディーゼル車両用` -> `4輪ガソ リン/ディー ゼル車両用`
- `この商品はブラウンの正規品ではなく` -> `この商品はブラウンの正 規 品ではなく`
- `ウイスキー?ブランデー?クリア ガラス` -> `ウイ スキー?ブラ ンデー?クリア ガラス`
- `人感センサーライト 防犯カメラ` -> `人感センサーライト 防 犯カメラ`
- `スプレー塗料で作られた` -> `スプ レー塗 料で作られた`
- `足にスプレーやローション` -> `足にス プ レーやロー シ ョ ン`

These are better handled as:

- phrase-specific review candidates
- not broad word-family auto-allow rules

## Low-Confidence Candidates

These touch forbidden words, but the main intent may be wording cleanup, punctuation repair, or mixed rewriting.

Examples:

- `Apple Watch等のデジタル製品でも` -> `App le Wa tch等のデジタル製品でも`
- `iPhoneのLightningコネクタ` -> `I PhoneのLight ningコネクタ`
- `照明防犯節電に` -> `照明、防 犯、節電に`
- `医療機器等の転倒落下事故を防止する為に機器面と設置面をベルトで強力に固定します` -> `医 療 機 器等の転倒落下事故を防止する為に機器面と設置面をベルトで強力に固定します。`

Recommendation:

- keep these out of the first migration set

## Clearly Unrelated Replacement Patterns

These should not become allowed-phrase rules.

### Removal / cleanup

Examples:

- warranty text removal
- contact instruction removal
- return/refund boilerplate removal
- `Amazonの購入履歴より...` removal

These are more likely compliance or description cleanup than forbidden-word masking.

### Meaning-changing substitution

Examples:

- `Amazon.co.jp限定` -> `ネット限定`
- `Amazon限定ブランド` -> `ネット限定ブ ラ ン ド`
- `BMP` -> `WMF`
- `?` -> `・`

These are not pure masking rules and should not be migrated into allowed phrases.

## Priority Candidate List By Forbidden Word

Recommended first-wave candidates:

- `アルコール`
  - `アルコールフリー`
  - `エチルアルコール`
  - `ステアリルアルコール`
  - `セテアリルアルコール`
  - `ベヘニルアルコール`
  - `変性アルコール`
- `スキン`
  - `スキンケース`
  - `スキンタイプ`
  - `スキントーン`
  - `スキンプロテクトミルク`
  - future manual review: `ドライスキン`
- `スプレー`
  - `スプレーボトル`
  - `オイルスプレー`
  - `スプレーしない`
  - `スプレーするだけ`
  - `スプレー機能`
- `クリア`
  - `クリア`
  - confidence is only `medium`

## Proposed New Logic

Do not mutate product text itself. Instead:

1. Keep `original_text` unchanged.
2. Build a detection-only copy for prohibited-word scanning.
3. Find allow-phrase matches on that detection copy.
4. Replace only the matched ranges with fixed-length sentinels.
5. Run forbidden-word detection on the masked copy.
6. Keep payload generation and downstream business logic on `original_text`.

Suggested diagnostics:

- `allowed_phrase_matches`
  - `phrase`
  - `forbidden_word`
  - `field`
  - `start`
  - `end`
  - `source`
- `matched_forbidden_words`
  - `word`
  - `field`
  - `start`
  - `end`
  - `context`

## Suggested Tests For Next Phase

- `クリア` is allowed when registered as an allow phrase.
- `アクリル` is still NG if not registered.
- `クリア クリ成分` only masks the `クリア` range; the later `クリ` remains detectable.
- `ノンアルコール` is allowed only after explicit registration.
- `ラノリンアルコール` is allowed only after explicit registration.
- `アルコール配合` remains NG.
- `ドライスキン` is allowed only after explicit registration.
- `スキン成分` remains NG.
- original item text is unchanged.
- diagnostic structure stays JSON serializable.

## Next Implementation Files

If we implement this next, the smallest likely change set is:

- `scripts/listing/listing_evaluator.py`
  - separate original text from detection-only text
  - add allow-phrase masking before prohibited-word scan
- new helper, likely one of:
  - `scripts/listing/allowed_phrase_rules.py`
  - `scripts/listing/prohibited_word_masking.py`
- `scripts/listing/models.py`
  - if we persist `allowed_phrase_matches` / richer forbidden-word diagnostics
- tests:
  - `tests/test_rakuten_listing_payload.py`
  - or a new focused test file such as `tests/test_prohibited_word_masking.py`

