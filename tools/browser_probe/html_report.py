"""Re-evaluate saved candidate evidence; no network or DB access."""
import json
from pathlib import Path
import sys
from html_probe import price_number, compare
from probe_support import atomic_json


def report(folder):
    result = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    shell = json.loads((folder / "shell.json").read_text(encoding="utf-8"))
    references = {case['asin']: case.get('baseline') for case in shell.get('cases', [])}
    counts = {}
    for case in result['cases']:
        case['candidates']['amazon_price'] = price_number(case['evidence']['price'])
        case['comparison'] = compare(case, references.get(case['requested_asin']))
        for field, state in case['comparison']['fields'].items():
            counts.setdefault(field, {})
            counts[field][state] = counts[field].get(state, 0) + 1
    result['field_counts'] = counts
    result['reanalysis'] = 'Saved evidence only; currency-aware parser; no additional requests'
    atomic_json(folder / 'reviewed_summary.json', result)
    print(json.dumps(counts, indent=2))
    for case in result['cases'][:3]:
        reference = references.get(case['requested_asin']) or {}
        print(case['requested_asin'], 'HTML', case['candidates'], 'Shell', {
            k: reference.get(k) for k in case['candidates']})


if __name__ == '__main__':
    report(Path(sys.argv[1]))
