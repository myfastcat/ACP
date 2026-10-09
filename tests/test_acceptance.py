"""Public CLI boundary and false-green regressions, using real subprocesses."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import hashlib

from agent_control_plane.cli import main
from agent_control_plane.integration import default_config, render_github_actions, report_sha256
from agent_control_plane.zero_code_runner import run_zero_code

CONTRACT = {"schema_version": "1", "agent": {"name": "support"},
            "rules": [{"id": "read", "decision": "ALLOW", "when": [{"field": "action", "value": "read"}]},
                      {"id": "write", "decision": "REQUIRE_APPROVAL", "when": [{"field": "action", "value": "write"}]}]}


class Acceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old = Path.cwd()
        os.chdir(self.root)
        self.write('.acp/config.json', default_config())
        self.write('.acp/authority.json', CONTRACT)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def write(self, path, value):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value))

    def check(self, expected):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(['check', '--json'])
        self.assertEqual(code, expected, stderr.getvalue() + stdout.getvalue())
        if expected != 4:
            report = json.loads(stdout.getvalue())
            self.assertEqual(report['summary']['acp_version'], '0.2.0')
            self.assertRegex(report['summary']['contract_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(report['summary']['ci_pass'], expected == 0)
            self.assertEqual(report['summary']['exit_code'], expected)
        return stdout.getvalue()

    def test_exit_semantics(self):
        for action, code in [('read', 0), ('write', 3), ('delete', 2)]:
            self.write('.acp/traces/run.json', [{'action': action}])
            self.check(code)
        self.write('.acp/traces/run.json', [{'action': 'write'}, {'action': 'delete'}])
        self.check(2)
        config = default_config(); config['fail_on_approval'] = False
        self.write('.acp/config.json', config)
        self.write('.acp/traces/run.json', [{'action': 'write'}]); self.check(0)

    def test_report_binds_each_source_to_normalized_observations(self):
        self.write('.acp/traces/run.json', [{'action': 'read', 'context': {'id': 'C-1'}}])
        first = json.loads(self.check(0))
        source = first['sources'][0]
        self.assertRegex(source['normalized_events_sha256'], r'^[0-9a-f]{64}$')

        self.write('.acp/traces/run.json', [{'context': {'id': 'C-1'}, 'action': 'read'}])
        reordered = json.loads(self.check(0))
        self.assertEqual(source['normalized_events_sha256'], reordered['sources'][0]['normalized_events_sha256'])

        self.write('.acp/traces/run.json', [{'action': 'read', 'context': {'id': 'C-2'}}])
        changed = json.loads(self.check(0))
        self.assertNotEqual(source['normalized_events_sha256'], changed['sources'][0]['normalized_events_sha256'])

    def test_check_writes_tamper_evident_evidence_without_overwrite(self):
        self.write('.acp/traces/run.json', [{'action': 'read', 'context': {'id': 'C-1'}}])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(['check', '--json', '--evidence', 'acp-evidence.json']), 0)
        printed = json.loads(stdout.getvalue())
        saved = json.loads(Path('acp-evidence.json').read_text())
        self.assertEqual(saved['schema'], 'acp-check-evidence/v1')
        self.assertEqual(saved['report'], printed)
        canonical = json.dumps(printed, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        self.assertEqual(saved['report_sha256'], hashlib.sha256(canonical).hexdigest())
        before = Path('acp-evidence.json').read_bytes()
        self.assertEqual(main(['check', '--evidence', 'acp-evidence.json']), 4)
        self.assertEqual(Path('acp-evidence.json').read_bytes(), before)

    def test_verify_evidence_recomputes_hash_and_rejects_tampering(self):
        self.write('.acp/traces/run.json', [{'action': 'read', 'context': {'id': 'C-1'}}])
        self.assertEqual(main(['check', '--evidence', 'acp-evidence.json']), 0)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(['verify-evidence', 'acp-evidence.json']), 0)
        self.assertRegex(stdout.getvalue(), r'^VALID schema=acp-check-evidence/v1 report_sha256=[0-9a-f]{64}\n$')

        pack = json.loads(Path('acp-evidence.json').read_text())
        pack['report']['summary']['events'] += 1
        self.write('tampered.json', pack)
        self.assertEqual(main(['verify-evidence', 'tampered.json']), 4)

        pack['schema'] = 'acp-check-evidence/v2'
        self.write('unsupported.json', pack)
        self.assertEqual(main(['verify-evidence', 'unsupported.json']), 4)

    def test_verify_evidence_rejects_hash_consistent_wrapper_forgery(self):
        self.write('.acp/traces/run.json', [{'action': 'read'}])
        self.assertEqual(main(['check', '--evidence', 'valid.json']), 0)
        original = json.loads(Path('valid.json').read_text())

        mutations = (
            lambda pack: pack.update(extra='untrusted'),
            lambda pack: pack.pop('check_command'),
            lambda pack: pack.update(check_command='acp check --json --no-enforcement'),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                pack = json.loads(json.dumps(original))
                mutate(pack)
                self.write('forged.json', pack)
                self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

    def test_verify_evidence_rejects_hash_consistent_non_reports(self):
        for report in ({}, {"summary": {}, "results": [], "sources": [], "incidents": []}):
            with self.subTest(report=report):
                canonical = json.dumps(
                    report, sort_keys=True, separators=(',', ':'), ensure_ascii=False
                ).encode()
                pack = {
                    "schema": "acp-check-evidence/v1",
                    "report_sha256": hashlib.sha256(canonical).hexdigest(),
                    "report": report,
                }
                self.write('forged.json', pack)
                self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

    def test_verify_evidence_rejects_hash_consistent_impossible_exit_states(self):
        for action, changes in (
            ('read', {'exit_code': 2, 'ci_pass': False}),
            ('delete', {'exit_code': 0, 'ci_pass': True}),
            ('write', {'exit_code': 3, 'ci_pass': True}),
            ('read', {'exit_code': 3, 'ci_pass': False}),
        ):
            with self.subTest(action=action, changes=changes):
                self.write('.acp/traces/run.json', [{'action': action}])
                main(['check', '--evidence', 'valid.json'])
                pack = json.loads(Path('valid.json').read_text())
                pack['report']['summary'].update(changes)
                pack['report_sha256'] = report_sha256(pack['report'])
                self.write('forged.json', pack)
                self.assertEqual(main(['verify-evidence', 'forged.json']), 4)
                Path('valid.json').unlink()

    def test_verify_evidence_binds_exit_status_to_approval_enforcement(self):
        self.write('.acp/traces/run.json', [{'action': 'write'}])
        self.assertEqual(main(['check', '--evidence', 'strict.json']), 3)
        strict = json.loads(Path('strict.json').read_text())
        self.assertTrue(strict['report']['summary']['fail_on_approval'])

        forged = json.loads(json.dumps(strict))
        forged['report']['summary'].update(exit_code=0, ci_pass=True)
        forged['report_sha256'] = report_sha256(forged['report'])
        self.write('forged.json', forged)
        self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

        config = default_config()
        config['fail_on_approval'] = False
        self.write('.acp/config.json', config)
        self.assertEqual(main([
            'check', '--config', '.acp/config.json', '--evidence', 'permissive.json'
        ]), 0)
        permissive = json.loads(Path('permissive.json').read_text())
        self.assertFalse(permissive['report']['summary']['fail_on_approval'])
        self.assertEqual(main(['verify-evidence', 'permissive.json']), 0)

    def test_verify_evidence_rejects_hash_consistent_incident_summary_mismatch(self):
        self.write('.acp/traces/run.json', [{'action': 'read'}])
        self.assertEqual(main(['check', '--evidence', 'valid.json']), 0)
        pack = json.loads(Path('valid.json').read_text())
        pack['report']['summary']['incident_regressions'] = 1
        pack['report_sha256'] = report_sha256(pack['report'])
        self.write('forged.json', pack)
        self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

    def test_verify_evidence_rejects_hash_consistent_incident_report_forgery(self):
        self.write('.acp/traces/run.json', [{'action': 'read'}])
        self.write('.acp/incidents/INC-1.json', {
            'schema': 'acp-incident/v1',
            'incident_id': 'INC-1',
            'incident_events': [{'action': 'read'}],
            'assertions': [{'type': 'must_occur', 'action': 'read'}],
        })
        self.assertEqual(main(['check', '--evidence', 'valid.json']), 0)
        original = json.loads(Path('valid.json').read_text())

        mutations = (
            lambda item: item.update(extra='untrusted'),
            lambda item: item.update(incident_id=' '),
            lambda item: item.update(incident_id='INC-1\nforged'),
            lambda item: item.update(incident_id='Cafe\u0301'),
            lambda item: item.update(passed=False),
            lambda item: item.update(failures=['']),
            lambda item: item.update(failures=['mismatch\u0000hidden']),
            lambda item: item.update(failures=[' mismatch']),
            lambda item: item.update(event_count=2),
            lambda item: item.update(incident_event_count=True),
            lambda item: item.update(mode='incident_evidence'),
            lambda item: item.update(fixture_sha256='NOT-A-DIGEST'),
            lambda item: item.update(path=[]),
            lambda item: item.update(path='../INC-1.json'),
            lambda item: item.update(path='/tmp/INC-1.json'),
            lambda item: item.update(path='.acp/incidents/INC-1.json\n'),
            lambda item: item.update(path='.acp/incidents/ INC-1.json'),
            lambda item: item.update(path='.acp/incidents/Cafe\u0301.json'),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                pack = json.loads(json.dumps(original))
                mutate(pack['report']['incidents'][0])
                pack['report_sha256'] = report_sha256(pack['report'])
                self.write('forged.json', pack)
                self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

    def test_verify_evidence_rejects_hash_consistent_result_count_mismatch(self):
        self.write('.acp/traces/run.json', [{'action': 'read'}])
        self.assertEqual(main(['check', '--evidence', 'valid.json']), 0)
        pack = json.loads(Path('valid.json').read_text())
        pack['report']['results'][0]['decision'] = 'DENY'
        pack['report_sha256'] = report_sha256(pack['report'])
        self.write('forged.json', pack)
        self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

    def test_verify_evidence_rejects_hash_consistent_source_range_forgery(self):
        self.write('.acp/traces/first.json', [{'action': 'read'}])
        self.write('.acp/traces/second.json', [{'action': 'read'}])
        self.assertEqual(main(['check', '--evidence', 'valid.json']), 0)
        original = json.loads(Path('valid.json').read_text())

        mutations = (
            lambda sources: sources.clear(),
            lambda sources: sources[0].update(events=2),
            lambda sources: sources[1].update(start_index=0),
            lambda sources: sources[1].update(path=sources[0]['path']),
            lambda sources: sources[0].update(normalized_events_sha256='NOT-A-DIGEST'),
            lambda sources: sources[0].update(extra='untrusted'),
            lambda sources: sources[0].update(path='../run.json'),
            lambda sources: sources[0].update(path='/tmp/run.json'),
            lambda sources: sources[0].update(path='.acp\\traces\\run.json'),
            lambda sources: sources[0].update(path='.acp/traces/run.json\u0000'),
            lambda sources: sources[0].update(path='.acp/traces/run.json '),
            lambda sources: sources[0].update(path='.acp/traces/Cafe\u0301.json'),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                pack = json.loads(json.dumps(original))
                mutate(pack['report']['sources'])
                pack['report_sha256'] = report_sha256(pack['report'])
                self.write('forged.json', pack)
                self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

        pack['report']['results'][0]['decision'] = 'UNKNOWN'
        pack['report_sha256'] = report_sha256(pack['report'])
        self.write('forged.json', pack)
        self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

    def test_verify_evidence_rejects_hash_consistent_result_schema_and_metric_forgery(self):
        self.write('.acp/traces/run.json', [
            {'action': 'read'},
            {'action': 'write'},
        ])
        self.assertEqual(main(['check', '--evidence', 'valid.json']), 3)
        original = json.loads(Path('valid.json').read_text())

        mutations = (
            lambda report: report.update(extra='untrusted'),
            lambda report: report['summary'].update(extra='untrusted'),
            lambda report: report['summary']['counts'].update(UNKNOWN=0),
            lambda report: report['results'][0].update(extra='untrusted'),
            lambda report: report['results'][0].update(index=1),
            lambda report: report['results'][0].update(action='   '),
            lambda report: report['results'][0].update(action='read\nDENY'),
            lambda report: report['results'][0].update(action='Cafe\u0301'),
            lambda report: report['results'][0].update(rule_id=[]),
            lambda report: report['results'][0].update(rule_id=' read'),
            lambda report: report['results'][0].update(reason=''),
            lambda report: report['results'][0].update(reason='ok\u0000hidden'),
            lambda report: report['results'][0].update(risk_score=True),
            lambda report: report['results'][0].update(risk_score=101),
            lambda report: report['results'][0].update(blast_radius='planet'),
            lambda report: report['results'][0].update(irreversible=1),
            lambda report: report['results'][0].update(approval_group=[]),
            lambda report: report['results'][1].update(approval_group='ops\nadmin'),
            lambda report: report['summary'].update(acp_version='0.2.0 '),
            lambda report: report['summary'].update(approval_load=0),
            lambda report: report['summary'].update(average_risk=99),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                pack = json.loads(json.dumps(original))
                mutate(pack['report'])
                pack['report_sha256'] = report_sha256(pack['report'])
                self.write('forged.json', pack)
                self.assertEqual(main(['verify-evidence', 'forged.json']), 4)

    def test_missing_empty_malformed_and_mixed_trace(self):
        self.check(4)
        config = default_config(); config['require_events'] = False
        self.write('.acp/config.json', config); self.check(4)
        for value in ([], {}, [None], [{'action': None}], [{'action': 'read', 'context': []}]):
            self.write('.acp/traces/run.json', value); self.check(4)
        self.write('.acp/traces/run.json', [{'action': 'read'}])
        self.write('.acp/traces/broken.json', {}); self.check(4)

    def test_historical_trace_is_not_current_evidence(self):
        self.write('incidents/raw-trace.json', [{'action': 'read'}])
        self.check(4)
        config = default_config(); config['trace_globs'] = ['**/*trace*.json']
        self.write('.acp/config.json', config); self.check(4)

    def test_import_assert_current_regression_and_original_replay(self):
        self.write('raw.json', [{'action': 'read'}, {'action': 'read'}])
        fixture = '.acp/incidents/INC-1.json'
        self.assertEqual(main(['incident', 'import', 'raw.json', '--incident-id', 'INC-1']), 0)
        self.write('.acp/traces/run.json', [{'action': 'read'}])
        self.check(4)  # Imported without a business invariant is not a regression check.
        self.assertEqual(main(['incident', 'assert', fixture, '--max-occurrences', 'read', '--max', '1']), 0)
        before = Path(fixture).read_bytes()
        self.check(0)
        self.assertEqual(main(['incident', 'replay', fixture]), 2)
        self.write('.acp/traces/run.json', [{'action': 'read'}, {'action': 'read'}])
        self.check(2)
        self.assertEqual(before, Path(fixture).read_bytes())
        self.assertEqual(main(['incident', 'import', 'raw.json', '--incident-id', 'INC-1']), 4)
        self.assertEqual(main(['incident', 'import', 'raw.json', '--incident-id', '../outside']), 4)
        self.assertEqual(main(['incident', 'assert', fixture, '--max-occurrences', 'read', '--max', '-1']), 4)

    def test_bad_config_and_contract(self):
        self.write('.acp/traces/run.json', [{'action': 'read'}])
        for config in ([], {'trace_globs': '*.json'}, {'fail_on_approval': 'false'}):
            self.write('.acp/config.json', config); self.check(4)
        self.write('.acp/config.json', default_config())
        for contract in ([], {}, {**CONTRACT, 'rules': [None]}, {**CONTRACT, 'default': {'decision': 'BAD'}}):
            self.write('.acp/authority.json', contract); self.check(4)

    def test_init_has_no_fixtures_and_preserves_configuration(self):
        Path('agent.py').write_text('@tool\ndef read(): pass\n')
        self.assertEqual(main(['init', '.', '--out', 'draft.json', '--ci']), 4)
        self.assertFalse(Path('draft.json').exists())
        Path('.acp/config.json').unlink(); Path('.acp/authority.json').unlink()
        self.assertEqual(main(['init', '.', '--ci', '--test-command', 'python -m unittest']), 0)
        self.assertTrue(Path('.acp/incidents').is_dir())
        self.assertEqual(list(Path('.acp/incidents').iterdir()), [])
        before = Path('.acp/authority.json').read_bytes()
        self.assertEqual(main(['init', '.', '--ci', '--test-command', 'python -m unittest']), 4)
        self.assertEqual(before, Path('.acp/authority.json').read_bytes())

    def test_bootstrap_propagates_test_failure_and_rejects_stale_trace(self):
        self.assertEqual(run_zero_code([sys.executable, '-c', 'raise SystemExit(7)']), 7)
        self.write('.acp/traces/stale.json', [{'action': 'read'}])
        with self.assertRaises(ValueError):
            run_zero_code([sys.executable, '-c', 'pass'])

    def test_real_cli_process_missing_input_exits_four(self):
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
        result = subprocess.run([sys.executable, '-m', 'agent_control_plane.cli', 'check'], env=env, capture_output=True)
        self.assertEqual(result.returncode, 4)
        self.assertIn(b'No tool-call events', result.stderr)

    def test_generated_yaml_preserves_customer_command(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML is installed in product CI')
        command = 'python -c "print(\'value: test\')"\npython -m unittest'
        workflow = yaml.safe_load(render_github_actions(command))
        script = workflow['jobs']['authority-and-regression']['steps'][3]['run']
        import shlex
        self.assertEqual(shlex.split(script)[-1], command)


class RealSDK(unittest.TestCase):
    def test_supported_sdk_captured_by_public_bootstrap(self):
        try:
            import agents
        except ImportError:
            self.skipTest('openai-agents is installed in product CI')
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
            script = "from agents.tracing import trace, function_span;\nwith trace('offline'):\n with function_span(name='read', input='{}'):\n  pass\n"
            result = subprocess.run([sys.executable, '-m', 'agent_control_plane.zero_code_runner', '--', sys.executable, '-c', script], cwd=tmp, env=env, capture_output=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            files = list(Path(tmp).glob('.acp/traces/*.json'))
            self.assertTrue(files, result.stderr.decode())
            self.assertEqual(json.loads(files[0].read_text())[0]['tool'], 'read')
