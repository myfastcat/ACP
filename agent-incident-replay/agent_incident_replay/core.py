from __future__ import annotations
import hashlib, json
from pathlib import Path

class ReplayError(ValueError): pass

def normalize(raw):
    if isinstance(raw, dict):
        raw = raw.get("events") or raw.get("trace") or raw.get("tool_calls")
    if not isinstance(raw, list): raise ReplayError("trace must contain a list of events")
    out=[]
    for i,e in enumerate(raw):
        if not isinstance(e,dict): raise ReplayError(f"event {i} must be an object")
        action=e.get("action") or e.get("tool") or e.get("name")
        if not action and isinstance(e.get("function"),dict): action=e["function"].get("name")
        if not action: raise ReplayError(f"event {i} has no action/tool/name")
        ctx=e.get("context") or e.get("arguments") or e.get("args") or {}
        out.append({"seq":i,"action":str(action),"context":ctx})
    return out

def build_fixture(events, incident_id="incident"):
    return {"schema":"air/v1","incident_id":incident_id,"events":events,"assertions":[]}

def evaluate(fixture):
    failures=[]
    events=fixture.get("events",[])
    for a in fixture.get("assertions",[]):
        kind=a.get("type"); action=a.get("action")
        matches=[e for e in events if e.get("action")==action]
        if kind=="must_not_occur" and matches: failures.append(f"{action} occurred {len(matches)} time(s)")
        elif kind=="must_occur" and not matches: failures.append(f"{action} did not occur")
        elif kind=="max_occurrences" and len(matches)>int(a.get("max",0)): failures.append(f"{action} occurred {len(matches)} > {a.get('max')}")
    canonical=json.dumps(fixture,sort_keys=True,separators=(",",":"))
    return {"incident_id":fixture.get("incident_id"),"passed":not failures,"failures":failures,"event_count":len(events),"fixture_sha256":hashlib.sha256(canonical.encode()).hexdigest()}

def evidence_pack(fixture, report):
    return {"schema":"air-evidence/v1","fixture":fixture,"result":report,"replay_command":"air replay fixture.json --json"}

def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def dump(path,obj):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
