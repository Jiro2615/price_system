# HTML feasibility comparison (experimental)

This does not change production workers. No Keepa, DB writes, credential/cookie
reuse, cart or purchase operations. DB selection uses the existing read-only
selector; three mandatory controls including B07QP2L8LC are always included.
The existing guarded Shell probe supplies the reference.

From the repository root, using the existing probe environment:

```powershell
.\tools\browser_probe\.venv\Scripts\python.exe tools/browser_probe/html_probe.py --db-limit 10 --output C:\rakuten\html_probe_trial_01
```

Use a new output directory each time. `--use-stats` uses due check-stat entries;
`--db-limit 0` tests controls only. `--html-only` skips the Shell reference.
Create a `STOP` file in the output directory to stop the probe (HTTP requests
can take up to the configured timeout before the next stop check).

Outputs: `summary.json`, plus `shell.json` and resource files when Shell runs.
`python tools/browser_probe/html_report.py <output-directory>` produces
`reviewed_summary.json` by re-evaluating saved evidence with the current parser,
including per-field counts. No additional network requests are made.
HTTP errors, unsafe redirects, challenge pages and unknown identity stop the
probe; no challenge bypass or automatic HTTP retry. Raw HTML/cookies are not
saved. Evidence is limited to product-related text.

Candidate matches are NOT certified production equivalence. Anonymous sessions
can have different destinations and selected offers, and HTML is fetched before
the Shell phase rather than simultaneously. Missing values remain null, not zero
or false. A quantity dropdown is not treated as actual stock. Gift eligibility
is deliberately unknown until a reliable interpretation is validated. Every
case still requires Shell; this first probe measures feasibility/coverage only.

The five comparable candidates are title, price, points, explicit remaining stock,
and gift availability. Seller, shipper, delivery and destination are retained as
raw evidence, not yet normalized or scored. CPU/memory measurements are phase
diagnostics, not an isolated paired benchmark; do not use them to claim savings
or an operational fallback rate. DB samples may be skewed toward particular
categories. Broader stratified and delivery-condition-matched testing is required.

Offline tests:
`python -m unittest discover -s tools/browser_probe -p test_html_probe.py -v`
