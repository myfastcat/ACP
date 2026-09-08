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

from agent_control_plane.cli import main
from agent_control_plane.integration import default_config, render_github_actions
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
