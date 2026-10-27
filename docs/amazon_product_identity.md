# Amazon product identity safety

The address bar is not sufficient product identity evidence. Amazon may keep
`/dp/B08713SQHV` in the address while rendering the product whose canonical
ASIN is `B0DXPWV7XS`. The same failure mode was observed for `B09683HFBN`.

`scripts/amazon_product_identity.py` reads only product-scoped identity signals:
the selected `#ASIN`, canonical URL, and ASIN rows in product details. Any
explicit conflict blocks the product. Missing page identity also fails closed;
the requested URL alone must never authorize a listing or purchase.

The shared listing/price checker checks identity before reading product data,
and again after switching purchase options. A blocked result is business NG,
stock zero, no usable price, and an invalidated image observation. Price target
calculation also recognizes older persisted ASIN mismatch errors even when
their business-NG flag was not set. Unrelated network errors retain their
existing retry/current-stock policy.

The standalone order repository carries an identical copy at
`Rakuten/python/amazon_product_identity.py`; update/distribute both copies.
It verifies identity before offer selection, after purchase-option selection,
and immediately before Buy Now or either cart-add route. These reads add no
page navigation, image download, or deliberate sleep. Existing cart/checkout
content validation remains separate; this guard is for product-detail pages.

Regression tests use mock pages and the exact production DOM expression. Live
verification can read public canonical metadata and replay that observation
through the guards without a browser click, cart addition, DB write, or order.
An unchanged *actual* ASIN with a changed catalog description is a different
problem and still needs title/image comparison and human review.
