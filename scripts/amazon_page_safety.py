"""Read-only Amazon page safety checks, shared by ordering and stock checks."""

HUMAN_VERIFICATION_JS = r"""() => {
    const visible = el => !!el && el.getClientRects().length > 0
        && getComputedStyle(el).visibility !== 'hidden'
        && !el.closest('[hidden], [aria-hidden="true"]');
    const selectors = [
        '#checkpointForm', '#tmms-challenge', '#captchacharacters',
        'input[name="cvf_captcha_input"]',
        'iframe[src*="captcha"]', 'iframe[src*="challenge-platform"]'
    ];
    if (selectors.some(s => [...document.querySelectorAll(s)].some(visible))) return true;
    const text = document.body?.innerText || '';
    return /下に表示されている文字を入力してください|文字を入力して.*確認してください/.test(text)
        || /(?:^|\n)\s*(?:私は人間です|ロボットではありません|I am human|I'm not a robot)\s*(?:$|\n)/im.test(text);
}"""

ORDER_CONFIRMATION_JS = r"""() => {
    const visible = el => !!el && el.getClientRects().length > 0
        && getComputedStyle(el).visibility !== 'hidden'
        && !el.closest('[hidden], [aria-hidden="true"]');
    const selectors = [
        '#widget-purchaseConfirmationStatus', '#widget-purchaseConfirmationDetails',
        '#typ-body-container', '#thank-you-page', '#thank-you-box', '#orderConfirmation'
    ];
    const success = /注文(?:が|は)確定しました|ご注文ありがとうございます|ご注文ありがとうございました|ご注文を承りました|Thank you.*(?:order|purchase)/i;
    const submit = [...document.querySelectorAll('input[name="placeYourOrder1"], input[name="placeYourOrder"], #submitOrderButtonId, #placeYourOrder')]
        .some(el => visible(el) && !el.disabled);
    if (submit) return {confirmed:false, order_number:''};
    for (const selector of selectors) {
        const root = document.querySelector(selector);
        if (!visible(root) || !success.test(root.innerText || '')) continue;
        const numbers = new Set();
        for (const input of document.querySelectorAll('input#purchaseId')) {
            if (/^\d{3}-\d{7}-\d{7}$/.test(input.value || '')) numbers.add(input.value);
        }
        for (const match of (root.innerText || '').matchAll(/(?:注文番号|Order\s*(?:number|#))\s*[:：]?\s*(\d{3}-\d{7}-\d{7})/gi)) {
            numbers.add(match[1]);
        }
        return {confirmed:true, source:selector, order_number:numbers.size === 1 ? [...numbers][0] : ''};
    }
    return {confirmed:false, order_number:''};
}"""


class HumanVerificationRequired(RuntimeError):
    def __init__(self):
        super().__init__(
            "Amazonの認証画面が表示されています。注文完了にはしていません。"
            "手動で認証し、注文履歴を確認してから再開してください。"
        )


def check_human_verification(page):
    if page.evaluate(HUMAN_VERIFICATION_JS) is True:
        raise HumanVerificationRequired()


async def check_human_verification_async(page):
    if await page.evaluate(HUMAN_VERIFICATION_JS) is True:
        raise HumanVerificationRequired()


def block_verification_result(result):
    """Preserve saved product data; a challenge says nothing about availability."""
    result.update(
        human_verification_required=True, amazon_confirmation_waiting=True,
        system_error=True, business_ng=False, available_qty=None,
        amazon_price=None, gift_available=None, shipping_status="",
        skip_product_persistence=True, defer_retry_seconds=900,
        page_needs_reset=True, ng_reason="Amazon認証待ち: 商品情報・在庫は更新していません",
    )
    return result
