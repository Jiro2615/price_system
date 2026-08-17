RMS WEB SERVICE

URL: https://webservice.rms.rakuten.co.jp/merchant-portal/view/ja/common/1-1_service_index/itemapi2_0/responsecodesreference/
サービス: 商品API 2.0（ItemAPI 2.0）

サービス一覧へ戻る / ItemAPI 2.0

RMS WEB SERVICE : ItemAPI 2.0 Response Codes Reference
※定期購入リニューアルにて追加・修正となる項目は背景色を緑に変更しています。

HTTP ステータスコード定義
コード	ステータス	内容
200	OK	リクエストが成功しました。
201	Created	リクエストが成功しました。
204	No Content	リクエストが成功しました。
400	Bad Request	リクエストが不正です。
401	Unauthorized	インターフェースの呼び出し権限がありません。
404	Not Found	リクエストパスが見つかりません。
409	Conflict	データ重複のため登録できませんでした。
414	URI Too Long	URIが長すぎます。
415	Unsupported Media Type	指定されたメディアタイプはサポートされていません。
500	Internal Server Error	サーバ内部にエラーが発生しました。
503	Service Unavailable	サービスが一時的に過負荷やメンテナンスで使用不可能です。
エラーコード定義
汎用エラー
No	エラーコード	エラーメッセージ	原因	対応方法	HTTPステータスコード
1	GE0007	Requested path doesn't exist	リクエストパスが存在していない場合	リクエストパスをご確認の上、再度お試しください。	400
2	GE0017	Write methods isn't allowed in readsOnly-mode.	読取り専用モードで更新処理をした場合	読み取り専用モードの場合は更新処理できない。	400
3	IE0001	${fieldName} is mandatory.	必須項目を設定していない場合

${fieldName}: 項目名	必須項目を設定の上、再度お試しください。	400
4	IE0002	${fieldName} has an invalid value.	項目のバリデーションエラーが発生した場合や、リクエストボディに不正な項目が設定されていた場合

${fieldName}: 項目名
${invalidValue}: 不正な値	項目名や型など確認の上、再度お試しください。	400
${fieldName} has an invalid value : ${invalidValue}.
Unrecognized field ${fieldName}.
5	IE0003	${fieldName} must be between ${min} and ${max}.	項目の値が範囲内ではない場合

${fieldName}: 項目名
${min}: 最小値
${max}: 最大値	項目の値を範囲内に設定の上、再度お試しください。	400
6	IE0004	Max length of ${fieldName} must be within ${value} bytes.	項目の最大長さを超えた場合

${fieldName}: 項目名
${value}: 最大値	項目の長さを範囲内に設定の上、再度お試しください。	400
7	IE0007	Invalid choice selected for ${fieldName}.	enum型で定義している値以外の値を指定した場合

${fieldName}: 項目名	項目の値を選択肢のいずれかに設定の上、再度お試しください。	400
8	IE0101	Only one of shipping.shopAreaSoryoPatternId, shipping.postageSegment.local, shipping.postageSegment.overseas and shipping.fee can be registered.	個別送料と送料区分を同時に指定した場合	個別送料か送料区分のいずれかを設定の上、再度お試しください。	400
9	IE0104	When pointCampaign is set, ${fieldName} cannot be less than JPY 100.	販売価格が100未満の商品に商品別ポイント変倍を指定した場合

${fieldName}: 項目名	販売価格を100以上に設定の上、再度お試しください。	400
10	IE0108	Point Campaign End time is earlier than Start time.	ポイント変倍の終了日時に開始日時より前の時間を指定した場合	ポイント変倍の終了日時を開始日時より後に設定の上、再度お試しください。	400
11	IE0109	${fieldName} may be one of ${value} or NULL	消費税率に不正な値を指定した場合

${fieldName}: 項目名
${value}: 選択肢リスト	消費税率に選択肢リストの一つかNULLを設定の上、再度お試しください。	400
12	IE0110	There are multiple occurrences of the same variant selectorValue content : ${invalidValue}.	selectorValuesに重複した値を指定した場合

${invalidValue}: 不正な値	selectorValuesの値を一意に設定の上、再度お試しください。	400
13	IE0111	Duplicate definition found. There are multiple occurrences of the same ${fieldName} content : ${invalidValue}.	項目選択肢項目名や項目選択肢名に重複した値を指定した場合

${fieldName}: 項目名
${invalidValue}: 不正な値	項目選択肢項目名や項目選択肢名を一意に設定の上、再度お試しください。	400
14	IE0113	There are multiple occurrences of the same variantId content : ${invalidValue}.	variantIdに重複した値を指定した場合

${invalidValue}: 不正な値	variantIdを一意に設定の上、再度お試しください。	400
15	IE0114	Missing or unexpected element in ${fieldName}. Expected selectors : ${empty expectedSelectors ? 'none' : expectedSelectors}, given set : ${empty actualSelectors ? 'none' : actualSelectors}.	selectorValuesに要素が存在してない、または誤っている場合

${fieldName}: 項目名
${expectedSelectors}: 想定される値リスト
${actualSelectors}: 入力された値リスト	selectorValuesの値をご確認の上、再度お試しください。	400
16	IE0116	Maximum number of tag list is ${configValue}, request number of tags.exceeded.	タグIDの個数が最大値を超えた場合

${configValue}: 最大値	タグIDを最大個数以下に設定の上、再度お試しください。	400
17	IE0118	Fraction digits of ${fieldName} does not match the currency ${value}.	通貨を円に指定した上、項目に小数を指定した場合

${fieldName}: 項目名
${value}: 通貨(円)	値を小数点なしで設定の上、再度お試しください。	400
18	IE0119	{fieldName} exceeds the maximum number of entries allowed.	最大リストサイズを超えた場合

${fieldName}: 項目名	項目のリストを最大値より少なく設定の上、再度お試しください。	400
19	IE0121	pointCampaign.applicablePeriod.start should be later than the present time.	ポイント変倍の期間の開始日時が現在の時刻より前だった場合	ポイント変倍の期間の開始日時を現在の時刻より2時間以降に変更の上、再度お試しください。	400
pointCampaign.applicablePeriod.end should be later.	ポイント変倍の期間の終了日時が現在の時刻から2時間59分以降ではない場合。	ポイント変倍の期間の終了日時を現在の時刻より2時間59分以降に変更の上、再度お試しください。
20	IE0122	The period set from ${start} to pointCampaign.applicablePeriod.end can not be longer than ${value} days.	ポイント変倍の期間が最大日数を超えた場合

${start}: ポイント変倍適用期間開始日時または現在の時刻

${value}: 最大日数	終了日を最初から登録する場合、ポイント変倍の開始日と終了日の間を最大日数以内に変更の上、再度お試しください。

終了日時を設定しないポイント変倍情報を適用期間開始後に変更する場合、終了日時を最大日数以内に変更の上、再度お試しください。	400
21	IE0123	The period set between pointCampaign.applicablePeriod.start and pointCampaign.applicablePeriod.end can not be shorter than ${value} hours.	ポイント変倍の期間が最小時間を下回った場合

${value}: 最小時間	ポイント変倍の開始日時と終了日時を最小時間以上に変更の上、再度お試しください。	400
22	IE0124	When pointCampaign.applicablePeriod is registered, pointCampaign.rate is mandatory.	ポイント変倍期間指定したが、ポイント変倍率を指定しなかった場合	ポイント変倍率を設定の上、再度お試しください。	400
23	IE0128	${fieldName} is not required if genreId does not belong to medicine.	ジャンルIDに医薬品以外を指定したが、医薬品説明文や医薬品注意事項を指定した場合

${fieldName}: 項目名	薬品説明文や医薬品注意事項をご確認の上、再度お試しください。	400
24	IE0129	${fieldName} has invalid value "${invalidValue}".	存在しないSKU商品名を商品バリエーション項目に指定した場合

${fieldName}: 項目名
${invalidValue}: 不正な値	商品バリエーション項目をご確認の上、再度お試しください。	400
25	IE0130	${invalidValue} lists have been set for ${fieldName}. The maximum number of settings is ${value} lists.	商品バリエーション項目のサイズが最大値を超えた場合

${fieldName}: 項目名
${invalidValue}: 不正な値
${value}: 最大値	商品バリエーション項目のサイズを最大値以下に設定の上、再度お試しください。	400
26	IE0131	${invalidValue} lists have been set for ${fieldName}. The maximum number of settings is ${value} lists.	商品バリエーション項目の選択肢のサイズが最大値を超えた場合

${fieldName}: 項目名
${invalidValue}: 不正な値
${value}: 最大値	商品バリエーション項目の選択肢のサイズを最大値以下に設定の上、再度お試しください。	400
27	IE0132	${fieldName} is required if genreId belongs to specific medicine genre.	医薬品注意事項の記載が必要なジャンルIDを指定しているが、医薬品注意事項を指定しなかった場合

${fieldName}: 項目名	医薬品注意事項を設定の上、再度お試しください。	400
28	IE0133	${fieldName} is invalid value : ${invalidValue}. The ${fieldName} of settings is ${value} value.	個別価格に"firstPrice", "lastPrice"以外を指定した場合

${fieldName}: 項目名
${invalidValue}: 不正な値
${value}: 選択可能な値	個別価格を"firstPrice", "lastPrice"のいずれかを設定の上、再度お試しください。	400
29	IE0135	There are duplicate value for variantSelectors.key.	商品バリエーションのキーに重複する値が存在した場合	商品バリエーションのキーの値を一意に設定の上、再度お試しください。	400
30	IE0136	When customizationOptions.inputType is "SINGLE_SELECTION" or "MULTIPLE_SELECTION", customizationOptions.selections is mandatory.	選択肢タイプにSINGLE_SELECTIONかMULTIPLE_SELECTIONを指定したが、Select/Checkbox用選択肢を指定しなかった場合	Select/Checkbox用選択肢を設定の上、再度お試しください。	400
31	IE0137	When customizationOptions.inputType is "FREE_TEXT, customizationOptions.selections cannot be set.	選択肢タイプにFREE_TEXTを指定したが、Select/Checkbox用選択肢を指定した場合	Select/Checkbox用選択肢を削除の上、再度お試しください。	400
32	IE0142	TagIds in tag list are duplicated.	タグIDが重複している場合	タグIDをご確認の上、再度お試しください。	400
33	IE0143	SKU specified tags can be registered, only when this is SKU inventory item (variantSelectors is set).	SKU商品ではないのにSKUタグIDを指定した場合	SKUタグIDを削除の上、再度お試しください。	400
34	IE0144	${invalidValue} is invalid ${fieldName}.	無効なタグIDを指定した場合

${fieldName}: 項目名
${invalidValue}: 不正な値	タグIDをご確認の上、再度お試しください。	400
35	IE0145	${fieldName} cannot be registered within same tag group.	同じタググループのSKUタグIDを指定した場合

${fieldName}: 項目名	SKUタグIDをご確認の上、再度お試しください。	400
36	IE0146	Failed to get the genre info.	不正なジャンルIDを指定した場合	ジャンルIDをご確認の上、再度お試しください。	400
37	IE0147	genreId cannot be updated, since SKU specified tags are being registered.	登録したSKUタグが所属してないタググループのジャンルIDを指定していた場合	ジャンルIDをご確認の上、再度お試しください。	400
38	GE0011	Request body is missing or is empty without any attributes.	リクエストボディが存在していないか空である場合
	リクエストボディを設定の上、再度お試しください。	400
39	IE0151	When ${fieldName} is ${fieldValue}, ${invalidField} cannot be set ${invalidValue}.	表示価格種別にSHOP_SETTING及びOPEN_PRICEを指定したが、表示価格文言も指定した場合

${fieldName}: 項目名
${fieldName}: ${fieldName}の値
${invalidField}: 不正な値が入っている項目名
${invalidValue}: 不正な値	表示価格文言を削除の上、再度お試しください。	400
40	IE0153	Cannot set ${fieldName} when shipping.postageIncluded is true.	送料無料フラグにtrueを指定したが、個別送料、地域別個別送料管理番号、送料区分のいずれかを設定した場合

${fieldName}: 項目名	個別送料、地域別個別送料管理番号、送料区分を削除の上、再度お試しください。	400
41	IE0154	Cannot update pointCampaign during ${applicablePeriod.start} ~ ${applicablePeriod.end}.	ポイント変倍適用期間内にポイント変倍の更新をしようとした場合

${applicablePeriod.start}: ポイント変倍適用期間開始時刻
${applicablePeriod.end}: ポイント変倍適用期間終了時刻	ポイント変倍適用期間中にポイント変倍の更新はできません。	400
42	IE0156	Number of variants.selectorValues should be equal to number of variantSelector.values	variants.{variantId}.selectorValuesとvariantSelector.valuesの数が合わない場合	variants.{variantId}.selectorValuesとvariantSelector.valuesをご確認の上、再度お試しください。	400
43	IE0157	${fieldName} cannot be set ${invalidValue} when unlimitedInventoryFlag was ${value}.	unlimitedInventoryFlagの設定の影響で指定できない項目が設定されていた場合

${fieldName}: 項目名
${invalidValue}: 不正な値
${value}: unlimitedInventoryFlagの設定値	それぞれのパターンをご確認の上、再度お試しください。	400
44	IE0158	When variantSelector is null, ${fieldName} cannot be set ${invalidValue}	商品バリエーション項目がNullで、かつ以下の項目が指定されていた場合
variants.{variantId}.selectorValues
variants.{variantId}.images
variants.{variantId}.tags
variants.{variantId}.horizontalNumber
variants.{variantId}.verticalNumber

${fieldName}: 項目名
${invalidValue}: 不正な値	それぞれの項目をご確認の上、再度お試しください。	400
45	IE0159	${fieldName} cannot be set ${invalidValue}, when item type is ${value}.	商品種別の設定の影響で指定できない項目が設定されていた場合

${fieldName}: 項目名
${invalidValue}: 不正な値
${value}: 商品種別	それぞれの条件をご確認の上、再度お試しください。	400
46	IE0160	Cannot convert item type ${value} to ${invalidValue}.	商品のフィールド設定の影響で商品種別を変更できないが、変更しようとした場合

${value}: 元々の商品種別
${invalidValue}: 不正な商品種別	それぞれの条件をご確認の上、再度お試しください。	400
47	IE0162	When features.inventoryDisplay is "DISPLAY_LOW_STOCK", features.lowStockThreshold is mandatory.	在庫数表示にDISPLAY_LOW_STOCKを指定したが、残り在庫数表示閾値を指定しなかった場合	残り在庫数表示閾値を指定して再度お試しください。	400
48	IE0163	When features.lowStockThreshold is set, features.inventoryDisplay should be "DISPLAY_LOW_STOCK".	残り在庫数表示閾値を指定したが、在庫数表示にDISPLAY_LOW_STOCKを指定しなかった場合	在庫数表示を"DISPLAY_LOW_STOCK"に指定して再度お試しください。	400
49	IE0164	When variants.${variantId}.backOrderFlag is true, variants.${variantId}.backOrderDeliveryDateId must be registered.	variants.${variantId}.backOrderFlagにtrueを指定したが、variants.${variantId}.backOrderDeliveryDateIdが指定されていない場合	variants.${variantId}.backOrderDeliveryDateIdを指定して再度お試しください。	400
50	IE0165	Variants.${sku}.backOrderFlag can not be set ${value} when item.unlimitedInventoryFlag was ${unlimitedInventoryFlag} and variants.${sku}.backOrderDeliveryDateId was ${backOrderDeliveryDateId}.	unlimitedInventoryFlagとvariants.${sku}.backOrderDeliveryDateIdの設定の影響で指定できない値がvariants.${sku}.backOrderFlagに設定されている場合

${sku}: SKU管理番号
${value}: 不正な値
${unlimitedInventoryFlag}: unlimitedInventoryFlagの設定値
${backOrderDeliveryDateId}: variants.${sku}.backOrderDeliveryDateIdの設定値	それぞれの条件をご確認の上、再度お試しください。	400
51	IE0166	When ${fieldName} is ${value}, features.restockNotification can not be set true.	${fieldName}の設定の影響で指定できない値(true)がfeatures.restockNotificationに設定されている場合

${fieldName}: 項目名
${value}: ${fieldName}の値	それぞれの条件をご確認の上、再度お試しください。	400
52	IE0173	PointCampaign should start later than {value} hours from current TimeStamp.	ポイント変倍の開始日時に今より2時間以内を指定した場合

{value}: 開始可能時間	ポイント変倍の開始日時に２時間より先の時間を指定し、再度お試しください。	400
53	IE0177	${fieldName} cannot include new line.	改行コードが入力できない項目に改行コードを入力した場合

${fieldName}: 項目名	改行コードをご削除の上、再度お試しください。	400
54	IE0178	The url of ${fieldName} is not allowed.	URLが入力できない項目にURLを入力した場合

${fieldName}: 項目名	URLをご削除の上、再度お試しください。	400
55	IE0179	One of the subscription.shippingDateFlag or subscription.shippingIntervalFlag must be true.	定期購入商品設定を指定したが、shippingWeekFlag、shippingIntervalFlagのいずれかをtrueに指定しなかった場合	shippingDateFlag、shippingIntervalFlagのいずれかをtrueに設定の上、再度お試しください。	400
56	IE0180	The release date should between current day and ${configValue}.	予約商品発売日を当日から365日までに指定しなかった場合

${configValue}: 予約商品発売日設定可能な最大日数	予約商品発売日を365日以内に指定の上、再度お試しください。	400
57	IE0181	The merchant can not use unlimited inventory.	在庫設定なしをtrueに指定した場合	店舗情報で在庫設定なしをnullやfalseに指定の上、再度お試しください。	400
58	IE0182	The exemption reason only allows integer of ${config}.	カタログIDなしの理由が誤っている場合

${config}: 選択可能な値(1,2,3,4,5,6)	カタログIDなしの理由をご確認の上、再度お試しください。	400
59	IE0184	SizeChartId is not allowed. allow integer as below: ${configValue}.	サイズ表リンクが誤っている場合

${configValue}: 選択可能な値(10101,10201,10301,10401,10501)	サイズ表リンクをご確認の上、再度お試しください。	400
60	IE0185	The merchant can not register adult item.	年齢認証許可できない店舗が年齢認証をtrueに指定した場合	年齢認証についてご確認の上、再度お試しください。	400
61	IE0190	${invalidValue} is invalid because it is not defined in ${fieldName} of shop setting.	店舗情報に${fieldName}の項目が設定されていないため、{invalidValue}の値が不正となった場合

${fieldName}: 項目名
${invalidValue}: 不正な値	それぞれのパターンを店舗情報でご確認の上、再度お試しください。	400
62	IE0191	shipping.singleItemShipping can be set 1~6, when shipping.postageIncluded is true, or shipping.fee && shipping.shopAreaSoryoPatternId are not null.	送料無料フラグがtrue、あるいは、個別送料と地域別個別送料管理番号が指定されているが、単品配送設定に値が指定されている場合	単品配送設定をご確認の上、再度お試しください。	400
63	IE0193	Can not set referencePrice.value, if item.referencePrice.displayType is OPEN_PRICE.	表示価格種別にOPEN_PRICEを指定したが、表示価格を設定した場合	表示価格を削除の上、再度お試しください。	400
64	IE0194	${fieldName} is invalid value: ${invalidValue}. This field only allows integer of ${configValue}.	単品配送設定が0～6ではない場合

${fieldName}: 項目名
${invalidValue}: 不正な値
${configValue}: 設定可能な値	単品配送設定をご確認の上、再度お試しください。	400
65	IE0197	Cannot register item, because number of  items in this shop has been maximum ${constraintValue}.	店舗の最大商品数を超えた場合

${constraintValue}: 最大商品数	新しい商品は登録できません。	400
66	IE0199	genreId cannot be medicine genre, because this shop does not apply medicine permission.	医薬品販売を許可されていない店舗が、ジャンルIDに医薬品ジャンルを指定した場合	ジャンルIDをご確認の上、再度お試しください。	400
67	IE0200	Failed to get the shop info.	楽天側で店舗のステータス確認に失敗した場合	時間を空けて再度お試しください。	400
68	IE0203	Cannot register pre-order item, because this shop plan does not support.	予約商品を販売できない出店プランの店舗が、予約商品発売日を指定した場合	予約商品発売日をご削除の上、再度お試しください。	400
69	IE0204	When the itemType is NORMAL with features.displaySubscriptionCartButton = true, or PRE_ORDER or BUYING_CLUB, ${fieldName} : ${invalidValue} is not allowed a medicine genreId.	通常商品（定期購入設定あり）・頒布会商品・予約商品に対し、第三類医薬品以外の医薬品をジャンルIDに指定した場合

${fieldName}: 項目名
${invalidValue}: 不正な値	ジャンルIDをご確認の上、再度お試しください。	400
70	IE0207	The end date should be after start date.	販売終了日時が販売開始日時より早かった場合	販売終了日時を販売開始日時より後に設定の上、再度お試しください。	400
71	IE0209	Cannot set ${fieldName}, when ${fieldName} object is set.	定期購入商品に、予約商品発売日を指定した場合

${fieldName}: 項目名	予約商品発売日をご削除の上、再度お試しください。	400
72	IE0211	Cannot set same value in ${fieldName}.	variantSelectors.valuesが重複している場合

${fieldName}: 項目名	variantSelectors.valuesを一意に設定の上、再度お試しください。	400
73	IE0212	Only integer number can be set in ${fieldName}.	ジャンルIDが数字ではない場合

${fieldName}: 項目名	ジャンルIDをご確認の上、再度お試しください。	400
74	IE0215	Cannot set ${invalidaHtmlTag} in ${fieldName}.	禁止しているHTMLタグを指定している場合

${invalidHtmlTag}: HTMLタグ
${fieldName}: 項目名	該当項目をご確認の上、再度お試しください。	400
75	IE0216	Cannot set attribute ${invalidaHtmlAttribute} to ${invalidaHtmlTag} in ${fieldName}.	HTMLタグに禁止している属性を指定している場合

${invalidHtmlAttribute}: 禁止しているHtml属性
${invalidHtmlTag}: HTMLタグ
${fieldName}: 項目名	該当項目をご確認の上、再度お試しください。	400
76	IE0217	Cannot set attribute ${invalidaHtmlAttribute} in ${fieldName}.	禁止しているHTML属性を指定している場合

${fieldName}: 項目名
${invalidHtmlAttribute}: 禁止しているHtml属性	該当項目をご確認の上、再度お試しください。	400
77	IE0218	HTML not allowed in ${fieldName}.	HTMLタグが指定されている場合

${fieldName}: 項目名	該当項目をご確認の上、再度お試しください。	400
78	IE0219	When purchasablePeriod is set, ${fieldName} cannot be null.	販売期間指定を指定しているが、販売開始日時と販売終了日時のいずれも指定していない場合

${fieldName}: 項目名	販売開始日時か販売終了日時を設定の上、再度お試しください。	400
79	IE0220	manageNumber is only allowed alphanumeric, "-" and "_". 	商品管理番号に英数字または"-", "_"以外を指定している場合	商品管理番号をご確認の上、再度お試しください。	400
80	IE0223	${fieldName} may only contain alphanumeric characters, hyphen, underscore, period, colon, and forward slashes.	英数字または"-", "_", ":", "/", "."以外を指定している場合

${fieldName}: 項目名	該当項目をご確認の上、再度お試しください。	400
81	IE0224	Invalid file extension. Only gif, jpg, jpeg, and png are allowed.	拡張子に"jpg", "jpeg", "gif", "png"以外を指定している場合	該当項目をご確認の上、再度お試しください。	400
82	IE0226	${fieldName} has an invalid video URL format.	無効な動画URLを指定している場合

${fieldName}: 項目名	動画URLをご確認の上、再度お試しください。	400
83	IE0227	Cannot set features.inventoryDisplay to "DISPLAY_LOW_STOCK", when variantSelectors is null.	在庫設定なしがfalse、かつ、商品バリエーション項目がnullで、在庫数表示にDISPLAY_LOW_STOCKが指定されている場合	在庫数表示をご確認の上、再度お試しください。	400
84	IE0228	Invalid articleNumber is set.	カタログID（製品情報のJANコード）が不正な場合	カタログIDをご確認の上、再度お試しください。	400
85	IE0229	Either articleNumber.value or articleNumber.exemptionReason should be mandatory.	カタログIDとカタログIDなしの理由のいずれも指定しなかった場合	カタログIDとカタログIDなしの理由をご確認の上、再度お試しください。	400
86	IE0230	Cannot update ${fieldName}, since it's fixed.	楽天側でデータ補正したため、カタログIDまたはジャンルIDの更新ができません。

${fieldName}: 項目名	楽天側に解除するようご連絡ください。	400
87	IE0235	Cannot convert to subscription item, because this item is applied in SuperDeal.	楽天スーパーDEALの対象商品を定期購入商品に更新しようとした場合	定期購入商品設定をご削除の上、再度お試しください。	400
88	IE0244	Cannot set variantSelectors.values as null, when variantSelector.key is set.	商品バリエーション項目のキーを指定しているが、商品バリエーション項目の選択肢を指定していない場合	variantSelectors.valuesをご確認の上、再度お試しください。	400
89	IE0252	Unsupported protocol is set in ${fieldName}.	商品画像URLに不正なスキーマが設定されている場合

${fieldName}: 項目名	商品画像URLをご確認の上、再度お試しください。	400
90	IE0257	Cannot register more than ${value} <${tagName}> tags to ${fieldName}.	<img>タグが20個を超えた場合

${value}: 最大個数
${tagName}: HTMLタグ
${fieldName}: 項目名	<img>タグをご確認の上、再度お試しください。	400
91	IE0259	PointCampaign.applicablePeriod.start can not be set later than 60 days from now	ポイント変倍開始日時に当日から60日以内を指定しなかった場合	ポイント変倍開始日時をご確認の上、再度お試しください。	400
92	IE0265	${fieldName} is mandatory when item type was ${value}.	商品種別に${value}が設定されているが、${fieldName}が指定されなかった場合

${value}: 商品種別
${fieldName}: 項目名	${fieldName}をご指定の上、再度お試しください。	400
93	IE0267	${fieldName} is invalid, the value is allowed alphanumeric, "-" and "_".	闇市パスワードに英数字または"-", "_"以外を指定している場合

${fieldName}: 項目名	闇市パスワードをご確認の上、再度お試しください。	400
94	IE0269	When variantSelectors is null, only can set max 1 variants.	商品バリエーションを指定してないが、SKUを2つ以上指定した場合	SKUをご確認の上、再度お試しください。	400
95	IE0270	Machine dependent characters cannot be registered.	機種依存文字を指定している場合	機種依存文字をご削除の上、再度お試しください。	400
96	IE0271	"${invalidHtmlTag}" should be set with start tag.	開始タグを指定してない場合

${invalidHtmlTag}: HTMLタグ	開始タグを指定して再度お試しください。	400
97	IE0272	"${invalidHtmlTag}" should be set with end tag.	終了タグを指定してない場合

${invalidHtmlTag}: HTMLタグ	終了タグを指定して再度お試しください。	400
98	IE0273	Cannot set comment tag for ${fieldName}.	医薬品説明文にコメントタグを指定している場合

${fieldName}: 項目名	コメントタグをご削除の上、再度お試しください。	400
99	IE0274	The genreId is merged genre and already expired, cannot register it to an item.	指定したジャンルIDが不正な場合	ジャンルIDをご確認の上、再度お試しください。	400
100	IE0275	[${invalidHtmlAttribute}] attributes are mandatory for "${invalidHtmlTag}" HTML tag.	医薬品注意事項に指定したHTMLタグにtype属性とname属性が指定されていなかった場合

${invalidHtmlAttribute}: 必要な属性
${invalidHtmlTag}: HTMLタグ	HTML属性をご確認の上、再度お試しください。	400
101	IE0276	Cannot set full width space in {HTML tag} tag.	HTMLタグに全角スペースが含まれている場合

${HTML tag}: HTMLタグ	全角スペースをご削除の上、再度お試しください。	400
102	IE0278	Invalid character is set in {fieldName}.	選択肢にコロンを指定している場合

${fieldName}: 項目名	コロンをご削除の上、再度お試しください。	400
103	IE0281	If "referencePriceVerified" is not true, "referencePriceVerifiedDetail" should be null, or not present.	表示価格のチェック結果フラグがtrueではない場合に、表示価格のチェックの詳細情報を指定した場合	表示価格をご確認の上、再度お試しください。	400
104	IE0290	benefits.pointRate should be same value with optimization.maxPointRate.	ポイント変倍率とポイント上限倍率の値が不一致の場合	ポイント変倍率とポイント上限倍率をご確認の上、再度お試しください。	400
105	IE0291	optimization.maxPointRate must be between ${minValue} and ${maxValue}.	ポイント上限倍率が範囲外の場合

${minValue}: 最小値
${maxValue}: 最大値	ポイント上限倍率をご確認の上、再度お試しください。	400
106	IE0292	This shop cannot set optimization.maxPointRate, since the shop has not applied for point optimization entry.	運用型ポイント変倍に申し込んでいないが、運用型ポイント変倍の項目を指定した場合	運用型ポイント変倍に申し込んでいない場合、運用型ポイント変倍の項目は利用できません。	400
107	IE0293	Cannot set optimization.maxPointRate for ${value} item.	運用型ポイント変倍の項目を、利用できない商品種別に指定した場合

${value}: 商品種別	予約商品・定期購入商品には運用型ポイント変倍の項目は利用できません。	400
108	IE0294	Cannot set item to be ${value} item, when optimization.maxPointRate has been registered.	ポイント上限倍率が指定されている商品を、予約商品あるいは定期購入商品に更新しようとした場合

${value}: 商品種別	ポイント上限倍率が指定されている商品は予約商品や定期購入商品に更新できません。	400
109	IE0400	The size of ${fieldName} must be between ${minValue} and ${maxValue}.	セット商品内訳情報と内訳商品SKUのサイズが範囲内ではない場合

${fieldName}: 項目名
${minValue}: 最小値
${maxValue}: 最大値	セット商品内訳情報と内訳商品SKUのサイズをご確認の上、再度お試しください。	400
110	IE0411	Cannot set variants.articleNumberForSet, when variants.articleNumber.value is registered.	カタログIDとセット商品用カタログIDを指定した場合	セット商品用カタログIDをご削除の上、再度お試しください。	400
111	IE0412	Cannot set variants.articleNumberForSet, when variants.articleNumber.exemptionReason is not registered as 1 (Set Item).	SKUカタログIDなしの理由が「1: セット商品 (Set item)」以外の場合に、セット商品用カタログIDを指定した場合	セット商品用カタログIDをご削除の上、再度お試しください。	400
112	IE0414	Cannot set duplicate value in articleNumberForSet list.	重複のセット商品用カタログIDを指定した場合	セット商品用カタログIDをご確認の上、再度お試しください。	400
113	IE0418	Invalid attribute or genreId is set.	variants.{variantId}.attributes[n]に指定したattributeに関するエラー	下記3. details中のエラーコード定義をご確認の上、再度お試しください。	400
114	IE0422	When unlimitedInventoryFlag is true, features.restockNotification cannot be set true.	在庫設定しない場合に、再入荷お知らせボタン表示をtrueに指定した場合	再入荷お知らせボタン表示をfalseかnullに設定の上、再度お試しください。	400
115	IE0423	When accessControl.accessPassword is ${value}, features.restockNotification cannot be set true.	闇市商品に対し、再入荷お知らせボタン表示をtrueに指定した場合

${value}: 闇市パスワード	再入荷お知らせボタン表示をfalseかnullに設定の上、再度お試しください。	400
116	IE0424	When variants.${variantId}.backOrderFlag is true, features.restockNotification cannot be set true.	在庫切れ時の注文を受け付ける場合に、再入荷お知らせボタン表示をtrueに指定した場合	再入荷お知らせボタン表示をfalseかnullに設定の上、再度お試しください。	400
117	IE1001	Could not find the corresponding attributes data of the genreId: {genreId}.	genreIdにvariants.{variantId}.attributes[n]に該当しない値を指定した場合

${genreId}: 不正なgenreId	genreIdとvariants.{variantId}.attributes[n]の組み合わせをご確認の上、再度お試しください。	400
118	IE1002	Could not find the attribute data of the name.	variants.{variantId}.attributes[n].nameに存在しないattributeを指定した場合	variants.{variantId}.attributes[n].nameをご確認の上、再度お試しください。	400
119	IE1003	Only one of offset and cursorMark can be registered.	offsetとcursorMarkの両方を指定した場合	offsetとcursorMarkのいずれか片方を指定の上、再度お試しください。	400
120	IE1004	When cursorMark is set, {fieldName} cannot be registered.	cursorMarkを指定した場合に、ソートキー・ソート順を指定した場合。

${fieldName}: 項目名	ソートキー・ソート順を指定せず、再度お試しください。	400
121	IE1005	Invalid request parameter.	items.searchにて不正なquery parameterを指定した場合。	指定したquery parameterをご確認の上、再度お試しください。	400
122	GE0014	Not found for inputs; manageNumber=${manageNumber}	商品が存在しない場合

${invalidValue}: 不正な商品管理番号	商品管理番号をご確認の上、再度お試しください。	404
123	CE0001	Your request could not be processed due to a conflict with another process. Please try again after a short while.	リクエストが現在のサーバーの状態と競合した場合	時間を空けて再度お試しください。	409
124	-	URI length exceeds the configured limit of ${value} characters	URLの長さが${value}文字以上の場合	URLの長さを短くして、再度お試しください。	414
125	GE0012	Media Type ${mediaType} is not supported	メディアタイプが"application/json"ではない場合	メディアタイプをご確認の上、再度お試しください。	415
126	GE0019	Failed to get the shop status.	楽天側で店舗のステータス確認に失敗した場合	時間を空けて再度お試しください。	500
127	X0000	システムエラー	-	-	500
128	-	-	サービスが一時的に過負荷やメンテナンスで使用不可能	-	503
129	IE0425	${fieldName} cannot be blank or space only.	必須項目に空白のみ入力された場合	空白のみを避けるよう有効な文字を入力した上、再度お試しください。	400
130	IE0426	When inputType is ${inputType}, the max size of ${fieldName} is ${max}.	商品オプションに入力可能の上限数を超えた場合
・タイプが「セレクトボックス」の場合、100
・タイプが「チェックボックス」の場合、40

${inputType}: 商品オプションのタイプ
${fieldName}: 商品オプションの項目名
${max}: 入力可能の上限数	入力した商品オプションの数を確認した上、再度お試しください。	400
131	IE0427	Cannot set itemType ${itemType} when inventory data has operationLeadTime information.	operationLeadTimeを指定して商品種別を通常商品以外で指定した場合	例：2 is invalid because it is not defined in shipFromIds of shop setting.

項目の値をご確認の上、再度お試しください。	400
132	IE0428	${fieldName} cannot be set, when the shop is non-permitted medicine shop.	医薬品不許可店舗に医薬品の注意事項や説明文が登録された場合	医薬品注意事項や説明文を削除した上、再度お試しください。	400
133	GE0020	The size of item is too large. Please reduce the data.	商品データが制限を超えている場合	テキストの文字数を削減したりした上、再度お試しください。	400
134	IE1105	This endpoint is disabled for the shop not migrated to SKU.	SKU移行前に登録、更新または削除しようとした場合	SKU移行前の場合ItemAPI(商品API)をご利用ください。	400
135	IE0429	When the articleNumber.exemptionReason is 1, the articleNumberForSet is mandatory.	必須商品属性の入力猶予期間が終了後、カタログIDなしの理由に「1：セット商品」が指定され、セット商品用カタログIDを設定しない場合	カタログIDなしの理由またはセット商品用カタログIDをご確認の上、再度お試しください。	400
136	IE0416	Cannot update selectorValues for the same variantId.	SKU管理番号を変更せず、SKU情報のバリエーション項目を変更しようとした場合	SKU管理番号を変更した上、再度お試しください。	400
137	IE1101	${fieldName} exceeds the maximum number of entries allowed.	リストの要素数が上限に超えてリクエストしようとした場合	リストの要素数を削減した上、再度お試しください。	400
138	IE1106	There are multiple occurrences of the same manageNumber : ${invalidValue}	一括取得（items.bulk.get）の際、商品管理番号が重複してリクエストしようとした場合	重複した値を削除した上、再度お試しください。	400
139	IE0117	Both subscription and buyingClub cannot be set at the same time.	定期購入商品設定と頒布会商品設定を同時に指定した場合	定期購入商品設定か頒布会商品設定のいずれかを設定の上、再度お試しください。	400
140	IE0127	If buyingClub.displayItems is true, buyingClub.items is mandatory.	商品内訳情報の表示がtrueに指定されているが、商品内訳情報に値が指定されていない場合	商品内訳情報の値をご確認の上、再度お試しください。	400
141	IE0186	If buyingClub.items field is set, amount of buyingClub.Items and numberOfDeliveries should be same.	お届け回数に設定されている値と、商品内訳情報に設定されている個数が異なる場合	お届け回数と商品内訳情報の値をご確認の上、再度お試しください。	400
142	IE0187	BuyingClub, set one of shippingDateFlag and shippingIntervalFlag to be true.	頒布会商品設定を指定したが、shippingDateFlag、shippingIntervalFlagのいずれかをtrueに指定しなかった場合	shippingDateFlag、shippingIntervalFlagのいずれかをtrueに設定の上、再度お試しください。	400
143	IE0430	For SKU sold as subscription, basePrice or firstPrice should be 5% off from standardPrice.	商品種別が通常商品で定期購入・頒布会ボタンがtrueに指定されているが、定期購入販売価格および初回価格の値が販売価格より低い価格に指定されていない場合	定期購入販売価格と初回価格の値をご確認の上、再度お試しください。	400
144	IE0431	For SKU sold as subscription, ${fieldName} cannot be 0 when basePrice is set.	商品種別が通常商品で定期購入・頒布会ボタンがtrueに指定されているが、販売価格の値が0の場合

${fieldName}: 項目名	販売価格の値をご確認の上、再度お試しください。	400
145	IE0432	features.displaySubscriptionCartButton cannot be true, when features.displayNormalCartButton is false.	商品種別が通常商品で定期購入・頒布会ボタンがtrueに指定されているが、注文ボタンの値がfalseの場合	定期購入・頒布会ボタンと注文ボタンの値をご確認の上、再度お試しください。	400
146	IE0433	For the item sold as subscription which itemType is "NORMAL" and displaySubscriptionCartButton is true, at least 1 variant of basePrice is mandatory.	商品種別が通常商品で定期購入・頒布会ボタンがtrueに指定されているが、定期購入販売価格がいずれのSKUにも設定されていない場合	定期購入価格の値をご確認の上、再度お試しください。	400
147	IE0434	firstPrice cannot be registered when basePrice is null.	初回価格が指定されているが、定期購入価格・頒布会価格が設定されていない場合	定期購入価格・頒布会価格と初回価格の値をご確認の上、再度お試しください。	400
148	IE0457	Pre-order and buying club items cannot set socialGiftFlag as true.	商品種別が通常商品以外でsocialGiftFlagをtrueに設定した場合	socialGiftFlagの設定をご確認の上、 再度お試しください。	400
149	IE0458	shipping.postageIncluded must be true for all SKU if socialGiftFlag is set to true.	socialGiftFlagをtrue に設定しているときに、いずれかの SKU の送料無料フラグがfalseに設定されている場合	すべての SKU で送料無料が true に設定されていることを確認するか、socialGiftFlag 設定を変更して、再度お試しください。	400
※200番以外のHTTP Status Codeについては、HTTPの規格で規定されているものに従います。

details中のエラーコード定義
No	エラーコード	エラーメッセージ	原因	対応方法
1	notUniqueAttributeId	Cannot set duplicate value in attributes list.	attributes内に重複がある場合	重複するattributeがないかご確認の上、再度お試しください。
2	invalidAllUnifyAttributes	The SKU unified attributes are missing. attributeNames: {attributeNames}.	rmsSkuUnifyFlgがtrueのattributeが設定されていない場合	rmsSkuUnifyFlgがtrueのattributeをご確認の上、再度お試しください。
3	invalidRCategoryIdAttributeId	The combination of genreId and attributes.name is invalid.	genreIdとattributeの組み合わせが正しくない場合	genreIdとattributeの組み合わせをご確認の上、再度お試しください。
4	invalidMandatoryValue	attributes.values is mandatory.	必須のattribute内でvaluesが設定されていない場合	必須のattribute内のvaluesをご確認の上、再度お試しください。
5	invalidNumberOfValue	The size of attributes.values must be within {rmsMultiValueLimit}.	valuesに設定した値が{rmsMultiValueLimit}以上の場合	valuesに設定した値をご確認の上、再度お試しください。
6	invalidSelectiveValue	The attributes.values is not defined as dictionary value.	選択式のattributeを設定した場合に、values内に正しい選択肢が設定されていない場合	選択式のattributeのvaluesの値をご確認の上、再度お試しください。
7	invalidStringValue	The length of attributes.values is invalid.	記述式のattributeでvalues内の値が文字列形式の場合に、正しい長さの値が設定されていない場合	記述式のattributeのvaluesの値をご確認の上、再度お試しください。
8	invalidNumberValue	attributes.values is invalid.	記述式のattributeでvalues内の値が数値形式の場合に、

・数値でない値を設定した場合
・最大値と最小値に反する値を設定した場合
・小数点以下の桁数が7桁を超過した場合	記述式のattributeのvaluesの値をご確認の上、再度お試しください。
9	invalidDateValue	attributes.values is invalid date format.	記述式のattributeでvalues内の値が日付形式の場合に、正しい日付の値が設定されていない場合	記述式のattributeのvaluesの値をご確認の上、再度お試しください。
10	invalidNoInputUnit	Cannot input attributes.unit when the attributes.values is input.	記述式のattributeでvalues内の値が文字列形式または日付形式の場合に、unitが設定されていた場合	記述式のattributeのvaluesの値をご確認の上、再度お試しください。
11	invalidUnit	Max length of attributes.unit is {unitCharLimit}.	記述式のattributeでvalues内の値が数値形式の場合に、unitが {unitCharLimit}以上の場合	記述式のattributeのunitの値をご確認の上、再度お試しください。
12	invalidNoUnitAndValues	attributes.unit and attributes.values are mandatory when the target attribute has a base unit.	記述式のattributeでベースとなるunitがある場合に、unitまたはvaluesに値が設定されていない場合	記述式のattributeのunitまたはvaluesの値をご確認の上、再度お試しください。
13	invalidUnitAndNoValues	attributes.values is mandatory when the attributes.unit is input.	記述式のattributeでunitが設定されているが、valuesに値が設定されていない場合	記述式のattributeのvaluesの値をご確認の上、再度お試しください。
14	invalidAllSameValue	All the values of attributes.values should be same.	同一のattributes.nameで異なる値がvaluesに設定されている場合	valuesに設定した値をご確認の上、再度お試しください。
15	invalidAllSameUnit	All the attributes.unit should be same.	同一のattributes.nameで異なる値がunitに設定されている場合	unitに設定した値をご確認の上、再度お試しください。
16	invalidAllSelectableMandatoryAttributes	At least one of the following selectable mandatory attributes is required. attributeNames: {attributeNames}	いずれか必須のattribute内でvaluesが設定されていない場合	いずれか必須のattribute内のvaluesをご確認の上、再度お試しください。
17	invalidUnitWhenNoBaseUnit	attributes.unit cannot be input when the target attribute has no base unit.	記述式のattributeで、valuesが数値形式であり、ベースとなるunitがない場合に、unitが設定されている場合	記述式のattributeのunitの値をご確認の上、再度お試しください。
