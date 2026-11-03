"""Run from the plugin directory: python3 -m unittest discover -s tests -v"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "audit" / "scripts" / "pipeline_doctor.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

spec = importlib.util.spec_from_file_location("pipeline_doctor", SCRIPT)
pd = importlib.util.module_from_spec(spec)
sys.modules["pipeline_doctor"] = pd
spec.loader.exec_module(pd)


def audit(text):
    return pd.Audit("Jenkinsfile", text).run()


def rules(text):
    return sorted({finding.rule for finding in audit(text)})


class Fixtures(unittest.TestCase):
    def test_insecure_fixture_triggers_every_rule(self):
        findings, _ = pd.audit_targets([str(FIXTURES / "insecure.Jenkinsfile")])
        self.assertEqual({f.rule for f in findings}, set(pd.RULES))

    def test_clean_fixture_has_no_findings(self):
        findings, _ = pd.audit_targets([str(FIXTURES / "clean.Jenkinsfile")])
        self.assertEqual([(f.rule, f.line, f.detail) for f in findings], [])

    def test_findings_point_at_the_right_line(self):
        findings, _ = pd.audit_targets([str(FIXTURES / "insecure.Jenkinsfile")])
        lines = {f.rule: f.line for f in findings if f.rule in ("PD003", "PD005", "PD012")}
        self.assertEqual(lines["PD003"], 25)
        self.assertEqual(lines["PD005"], 52)
        self.assertIn(lines["PD012"], (62, 63))


class Scanner(unittest.TestCase):
    def test_comments_are_not_code(self):
        source = pd.GroovySource("// sh 'x'\n/* sh 'y' */\nsh 'z'\n")
        self.assertEqual([s.value for s in source.strings], ["z"])

    def test_nested_quotes_inside_gstring(self):
        source = pd.GroovySource('sh "a ${foo("b")} c"\nsh \'next\'\n')
        self.assertEqual(len(source.strings), 2)
        self.assertEqual(source.strings[1].value, "next")

    def test_triple_quoted_string_keeps_line_numbers(self):
        source = pd.GroovySource("x = '''\none\ntwo\n'''\nsh 'y'\n")
        last = source.strings[-1]
        self.assertEqual(source.line_of(last.start), 5)

    def test_regex_with_quote_does_not_derail_scanner(self):
        source = pd.GroovySource("def m = value =~ /it's/\nsh 'still-found'\n")
        self.assertEqual([s.value for s in source.strings], ["still-found"])

    def test_division_is_not_a_regex(self):
        source = pd.GroovySource("def a = b / c\ndef d = e / f\nsh 'found'\n")
        self.assertEqual([s.value for s in source.strings], ["found"])


class Interpolation(unittest.TestCase):
    CREDS = "environment { C = credentials('x') }\n"

    def test_double_quoted_secret(self):
        self.assertIn("PD002", rules(self.CREDS + 'sh "echo ${C_PSW}"'))

    def test_bare_dollar_secret(self):
        self.assertIn("PD002", rules(self.CREDS + 'sh "echo $C"'))

    def test_env_prefix(self):
        self.assertIn("PD002", rules(self.CREDS + 'sh "echo ${env.C}"'))

    def test_single_quoted_secret_is_safe(self):
        self.assertNotIn("PD002", rules(self.CREDS + "sh 'echo $C_PSW'"))

    def test_escaped_dollar_is_safe(self):
        self.assertNotIn("PD002", rules(self.CREDS + 'sh "echo \\$C_PSW"'))

    def test_username_alone_is_not_secret(self):
        self.assertNotIn("PD002", rules(self.CREDS + 'sh "echo ${C_USR}"'))

    def test_withcredentials_binding(self):
        text = "withCredentials([string(credentialsId: 'x', variable: 'TOK')]) { sh \"curl $TOK\" }"
        self.assertIn("PD002", rules(text))

    def test_script_label_form(self):
        self.assertIn("PD002", rules(self.CREDS + 'sh(returnStdout: true, script: "echo ${C}")'))

    def test_non_secret_value_is_ignored(self):
        self.assertEqual(rules('sh "echo ${env.BUILD_NUMBER}"'), [])

    def test_param_and_branch_are_untrusted(self):
        self.assertIn("PD006", rules('sh "x ${params.V}"'))
        self.assertIn("PD006", rules('sh "x ${env.CHANGE_TITLE}"'))
        self.assertIn("PD006", rules('sh "x $BRANCH_NAME"'))


class Secrets(unittest.TestCase):
    def test_token_is_redacted_in_output(self):
        token = "ghp_" + "a1B2" * 10
        findings = audit(f"def x = '{token}'\n")
        self.assertEqual({f.rule for f in findings}, {"PD001"})
        self.assertNotIn(token, json.dumps([f.__dict__ for f in findings]))

    def test_literal_password_value_is_redacted(self):
        findings = audit("password = 'pR7vXq92LmZtK4'\n")
        self.assertEqual([f.rule for f in findings], ["PD001"])
        self.assertNotIn("pR7vXq92LmZtK4", findings[0].evidence)

    def test_url_password(self):
        findings = audit("git url: 'https://bob:s3cr3tvalue@git.example.com/a.git'\n")
        self.assertIn("PD001", {f.rule for f in findings})
        self.assertNotIn("s3cr3tvalue", findings[0].evidence)

    def test_credential_ids_are_not_secrets(self):
        self.assertEqual(rules("credentialsId: 'prod-api-token'\ntokenCredentialId = 'gh-token-2'\n"), [])

    def test_placeholders_are_not_secrets(self):
        self.assertEqual(rules("password = 'changeme123'\ntoken = '<your-token-here>'\n"), [])

    def test_kubernetes_secret_reference_is_not_a_secret(self):
        self.assertEqual(rules("secretEnvVar(key: 'T', secretName: 'ci-tokens', secretKey: 'kKf29xQmZ')\n"), [])

    def test_vault_path_is_not_a_secret(self):
        self.assertEqual(rules("DOCKER_SECRET = 'secret/team/ci/docker-registry'\n"), [])

    def test_key_delimiter_in_code_is_not_a_private_key(self):
        self.assertEqual(rules('k = k.replace("-----BEGIN RSA PRIVATE KEY-----\\n", "")\n'), [])

    def test_real_private_key_block_is_found(self):
        body = "MIIEowIBAAKCAQEA" + "x8Kd" * 12
        self.assertEqual(rules(f"k = \"\"\"-----BEGIN RSA PRIVATE KEY-----\n{body}\n\"\"\"\n"), ["PD001"])

    def test_file_binding_is_a_path_not_a_secret(self):
        text = "withCredentials([file(credentialsId: 'k', variable: 'KEY_PATH')]) { sh \"cat $KEY_PATH\" }"
        self.assertNotIn("PD002", rules(text))

    def test_variable_reference_is_not_a_secret(self):
        self.assertEqual(rules('password = "${env.DB_PASSWORD}"\n'), [])


class StructuralRules(unittest.TestCase):
    def test_library_versions(self):
        self.assertIn("PD008", rules("@Library('lib') _"))
        self.assertIn("PD008", rules("@Library('lib@master') _"))
        self.assertIn("PD008", rules("@Library(['a@1.0', 'b@main']) _"))
        self.assertIn("PD008", rules("library 'lib@develop'"))
        self.assertNotIn("PD008", rules("@Library('lib@v2.1.0') _"))
        self.assertNotIn("PD008", rules("@Library('lib@9fceb02') _"))
        self.assertNotIn("PD008", rules("@Library(\"lib@${VERSION}\") _"))

    def test_images(self):
        self.assertIn("PD009", rules("agent { docker { image 'node' } }"))
        self.assertIn("PD009", rules("docker.image('node:latest').inside { }"))
        self.assertIn("PD009", rules("x = '''\ncontainers:\n- image: nginx\n'''\n"))
        self.assertNotIn("PD009", rules("image 'registry:5000/node:20.11'"))
        self.assertNotIn("PD009", rules("image 'node@sha256:abc123'"))

    def test_scripted_pipeline_needs_timeout(self):
        self.assertIn("PD011", rules("node('linux') { sh 'make' }"))
        self.assertNotIn("PD011", rules("node('linux') { timeout(5) { sh 'make' } }"))

    def test_scripted_step_in_a_library_leaves_timeouts_to_the_caller(self):
        finding_rules = {f.rule for f in pd.Audit("vars/build.groovy", "node { sh 'make' }").run()}
        self.assertEqual(finding_rules, set())

    def test_controller_in_a_label_expression(self):
        self.assertIn("PD005", rules("node('master || linux') { }"))

    def test_library_file_without_pipeline_has_no_option_findings(self):
        self.assertEqual(rules("def call(String name) { sh 'make' }\n"), [])

    def test_scripted_input_inside_node(self):
        self.assertIn("PD013", rules("timeout(1) { node { input 'ok?' } }"))
        self.assertNotIn("PD013", rules("node { sh 'a' }\ninput 'ok?'\nnode { sh 'b' }"))

    def test_declarative_input_directive_is_fine(self):
        text = "pipeline { agent none\nstages { stage('x') { input { message 'ok' }\nsteps { sh 'a' } } } }"
        self.assertNotIn("PD013", rules(text))

    def test_deploy_guard(self):
        self.assertIn("PD014", rules("stage('Deploy') { sh 'x' }"))
        self.assertNotIn("PD014", rules("stage('Deploy') { lock('prod') { sh 'x' } }"))
        self.assertNotIn("PD014", rules("stage('Unit tests') { sh 'x' }"))
        self.assertNotIn("PD014", rules("stage('Create Release Branch') { sh 'x' }"))
        self.assertIn("PD014", rules("stage('Release') { sh 'x' }"))

    def test_masked_failure_needs_a_check_tool(self):
        self.assertIn("PD015", rules("sh 'pytest || true'"))
        self.assertNotIn("PD015", rules("sh 'rm -f old.txt || true'"))

    def test_curl_flag_detection(self):
        self.assertIn("PD007", rules("sh 'curl -sSk https://x '"))
        self.assertNotIn("PD007", rules("sh 'curl -sS https://kube.example.com/ok'"))


class Suppression(unittest.TestCase):
    def test_same_line(self):
        self.assertEqual(rules("sh 'chmod 777 x' // pipeline-doctor:ignore PD019\n"), [])

    def test_previous_line(self):
        self.assertEqual(rules("// pipeline-doctor:ignore PD019\nsh 'chmod 777 x'\n"), [])

    def test_other_rule_is_not_suppressed(self):
        self.assertEqual(rules("sh 'chmod 777 x' // pipeline-doctor:ignore PD003\n"), ["PD019"])

    def test_whole_file(self):
        self.assertEqual(rules("// pipeline-doctor:ignore-file\nsh 'chmod 777 x'\n"), [])


class Cli(unittest.TestCase):
    def run_main(self, *argv):
        return pd.main(list(argv))

    def test_exit_codes(self):
        bad = str(FIXTURES / "insecure.Jenkinsfile")
        good = str(FIXTURES / "clean.Jenkinsfile")
        with tempfile.TemporaryDirectory() as folder:
            out = str(Path(folder) / "r.txt")
            self.assertEqual(self.run_main(bad, "--output", out), 1)
            self.assertEqual(self.run_main(bad, "--fail-on", "none", "--output", out), 0)
            self.assertEqual(self.run_main(good, "--fail-on", "low", "--output", out), 0)

    def test_unknown_rule_and_missing_path(self):
        self.assertEqual(self.run_main(".", "--ignore", "PD999"), 2)
        self.assertEqual(self.run_main("/no/such/path"), 2)

    def test_sarif_is_valid_json_with_results(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "r.sarif"
            self.run_main(str(FIXTURES / "insecure.Jenkinsfile"), "--format", "sarif", "--output", str(out))
            data = json.loads(out.read_text())
        self.assertEqual(data["version"], "2.1.0")
        self.assertTrue(data["runs"][0]["results"])

    def test_discovery_finds_a_library_in_a_subfolder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "library" / "vars").mkdir(parents=True)
            (root / "library" / "src" / "org").mkdir(parents=True)
            (root / "tools" / "src").mkdir(parents=True)
            (root / "library" / "src" / "org" / "Helper.groovy").write_text("class Helper {}", encoding="utf-8")
            (root / "tools" / "src" / "Other.groovy").write_text("class Other {}", encoding="utf-8")
            found = {path.name for path, _ in pd.discover([folder], [])}
            self.assertEqual(found, {"Helper.groovy"})

    def test_discovery_finds_pipelines_and_skips_noise(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "vars").mkdir()
            (root / "src" / "org").mkdir(parents=True)
            (root / "node_modules").mkdir()
            for name in ("Jenkinsfile", "deploy.Jenkinsfile", "vars/build.groovy", "src/org/Util.groovy"):
                (root / name).write_text("sh 'x'\n")
            (root / "node_modules" / "Jenkinsfile").write_text("sh 'x'\n")
            (root / "Jenkinsfile.md").write_text("docs\n")
            (root / "unrelated.groovy").write_text("x\n")
            _, scanned = pd.audit_targets([folder])
        names = sorted(Path(item).relative_to(folder).as_posix() for item in scanned)
        self.assertEqual(names, ["Jenkinsfile", "deploy.Jenkinsfile", "src/org/Util.groovy", "vars/build.groovy"])

    def test_non_ascii_evidence_survives_a_windows_console(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "Jenkinsfile"
            target.write_text("sh 'chmod 777 \u23f3'\n", encoding="utf-8")
            env = dict(os.environ, PYTHONIOENCODING="cp1252")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(target), "--fail-on", "none"],
                capture_output=True, env=env,
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertIn(b"PD019", result.stdout)

    def test_rules_reference_is_in_sync(self):
        document = ROOT / "skills" / "audit" / "references" / "rules.md"
        self.assertEqual(document.read_text().strip(), pd.render_rules_markdown().strip())

    def test_every_severity_is_known(self):
        self.assertTrue(set(Counter(r.severity for r in pd.RULES.values())) <= set(pd.SEVERITIES))


if __name__ == "__main__":
    unittest.main()
