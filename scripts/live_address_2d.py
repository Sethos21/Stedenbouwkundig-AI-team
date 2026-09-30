"""Explicitly opted-in official-address BAG/BGT proof; no workflow approval."""
import argparse
from datetime import datetime, timezone
import json
from live_mastenbroekweg_2d import ROOT, run_proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', required=True)
    parser.add_argument('--live-address', action='store_true', required=True)
    parser.add_argument('--bootstrap', choices=('bag','locatieserver'), default='bag')
    parser.add_argument('--compare-address-evidence')
    args = parser.parse_args()
    comparison = None
    if args.compare_address_evidence:
        path = (ROOT / args.compare_address_evidence).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError('Comparison evidence must stay in project')
        comparison = json.loads(path.read_text(encoding='utf-8'))
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory = ROOT / 'runtime/2d-live' / run_id
    report = run_proof(directory, run_id, live_opt_in=args.live_address, address_text=args.address,
                       address_backend=args.bootstrap, comparison_evidence=comparison)
    print(json.dumps({k:v for k,v in report.items() if k not in ('collections','analysis_geometry')}, indent=2))
    print('Local evidence directory: ' + str(directory))
    return int(report['result'] not in ('PASS', 'PASS_WITH_FINDINGS'))


if __name__ == '__main__':
    raise SystemExit(main())
