import argparse,json,sys
from .core import ReplayError,normalize,build_fixture,evaluate,evidence_pack,load,dump

def main(argv=None):
    p=argparse.ArgumentParser(prog="air"); s=p.add_subparsers(dest="cmd",required=True)
    n=s.add_parser("normalize"); n.add_argument("trace"); n.add_argument("--incident-id",default="incident"); n.add_argument("--out",default="fixture.json")
    r=s.add_parser("replay"); r.add_argument("fixture"); r.add_argument("--json",action="store_true"); r.add_argument("--evidence")
    a=p.parse_args(argv)
    try:
        if a.cmd=="normalize":
            f=build_fixture(normalize(load(a.trace)),a.incident_id); dump(a.out,f); print(f"events={len(f['events'])} fixture={a.out}"); return 0
        f=load(a.fixture); report=evaluate(f)
        if a.evidence: dump(a.evidence,evidence_pack(f,report))
        print(json.dumps(report,indent=2) if a.json else f"passed={str(report['passed']).lower()} events={report['event_count']} failures={len(report['failures'])}")
        return 0 if report["passed"] else 2
    except (OSError,json.JSONDecodeError,ReplayError,ValueError) as e:
        print(f"error: {e}",file=sys.stderr); return 4

if __name__=="__main__": raise SystemExit(main())
