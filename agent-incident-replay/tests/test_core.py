from agent_incident_replay.core import normalize,build_fixture,evaluate,evidence_pack

def test_normalize_common_tool_call():
    e=normalize({"tool_calls":[{"name":"send_email","arguments":{"to":"x"}}]})
    assert e==[{"seq":0,"action":"send_email","context":{"to":"x"}}]

def test_regression_failure_and_evidence():
    f=build_fixture([{"seq":0,"action":"delete_db","context":{}}],"inc-1")
    f["assertions"]=[{"type":"must_not_occur","action":"delete_db"}]
    r=evaluate(f)
    assert not r["passed"] and r["failures"]
    assert evidence_pack(f,r)["result"]["fixture_sha256"]

def test_positive_assertions():
    f=build_fixture([{"seq":0,"action":"read","context":{}}])
    f["assertions"]=[{"type":"must_occur","action":"read"},{"type":"max_occurrences","action":"read","max":1}]
    assert evaluate(f)["passed"]
