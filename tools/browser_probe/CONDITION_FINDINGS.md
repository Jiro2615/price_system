# Anonymous condition pilot — 2026-09-14

Four products: mandatory controls B07QP2L8LC, B019SKZXV8, B0F2HTH5H9,
plus price-difference case B0DV8Q76RX. Local results:
`C:\rakuten\html_conditions_20260914_01\conditions.json`.

This test uses the initial response HTML from a Shell navigation, then its
rendered BuyBox and regular-purchase selection in the same anonymous context.
It isolates parsing/purchase-method differences, but is NOT proof that an
independent HTTP client obtains equivalent content without a browser.
No production persistence, login, postal-code changes, Keepa or purchases.

## Observations

- B07QP2L8LC: response HTML and regular BuyBox both 7,226 JPY, seller JJstorE,
  Amazon fulfillment. Previous independent-HTTP candidate was 7,551 JPY.
  The earlier difference did not reproduce in this same-response comparison;
  its exact cause (session/time/destination etc.) remains unresolved.
- B019SKZXV8: HTML contains regular-purchase row 929 JPY and subscription row
  including 790 JPY. Same-context regular BuyBox is 929 JPY. This explains how
  a generic page price can select a subscription amount. Row-scoped extraction
  is required; generic core price is not sufficient.
- B0F2HTH5H9: no primary BuyBox price. Offers include Amazon-fulfilled 2,792 JPY.
  Missing initial price does not mean unavailable.
- B0DV8Q76RX: initial/regular price 1,200 JPY, shipped and sold by T&M Plaza.
  An alternative Amazon-fulfilled offer is 1,899 JPY from Nowa Style (Japanese
  seller name in raw results). Previous HTTP candidate was 1,180 JPY from
  another seller. Rejecting the top merchant must not reject the product.

The visible BuyBox showed an automatically chosen Nagoya 461-0001 destination
where present. The header merely said to update location. This is NOT a verified
production delivery address, nor proof that earlier HTTP sessions used it.
Offer lists were inspected up to the existing 20-offer limit, not certified as
exhaustive. No product-wide exclusion was established in these four cases.

## Safe decision boundary

Keep independent-HTTP results as candidates. Scope to explicit regular-new row;
unknown destination, shipping, gift, missing primary price, or ineligible primary
seller must fall through to Shell rather than become a product exclusion.
An eligible alternative offer is enough to disprove an initial exclusion;
absence among a partial offer list is not enough to prove exclusion.

Next validation needs independent HTTP regular-row extraction with a verified
matching destination/session and reliable alternative-offer coverage. The
amount of browser work saved remains unmeasured; no production rule is enabled.
