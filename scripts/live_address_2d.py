"""Explicitly opted-in official-address BAG/BGT proof; no workflow approval."""
import argparse
from datetime import datetime, timezone
import json
from live_mastenbroekweg_2d import ROOT, run_proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', required=True)
    parser.add_argument('--live-address', action='store_true', required=True)
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory = ROOT / 'runtime/2d-live' / run_id
    report = run_proof(directory, run_id, live_opt_in=args.live_address, address_text=args.address)
    print(json.dumps({k:v for k,v in report.items() if k not in ('collections','analysis_geometry')}, indent=2))
    print('Local evidence directory: ' + str(directory))
    return int(report['result'] not in ('PASS', 'PASS_WITH_FINDINGS'))


if __name__ == '__main__':
    raise SystemExit(main())
