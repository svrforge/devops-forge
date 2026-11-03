#!/usr/bin/env python3
"""pipeline-doctor: offline static audit for Jenkins pipelines.

Reads Jenkinsfiles and shared-library Groovy, then reports security and
reliability problems with a concrete fix for each. It needs no Jenkins server,
no network access and no third-party packages, and it never executes the code
it reads.

    python3 pipeline_doctor.py .
    python3 pipeline_doctor.py Jenkinsfile --format markdown --output report.md
    python3 pipeline_doctor.py . --format sarif --output results.sarif
    python3 pipeline_doctor.py --list-rules

Exit codes: 0 no findings at or above --fail-on, 1 findings, 2 usage error.
"""
from __future__ import annotations

import argparse
import bisect
import fnmatch
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

__version__ = "1.0.0"

SEVERITIES = ("critical", "high", "medium", "low")
SEVERITY_RANK = {name: len(SEVERITIES) - i for i, name in enumerate(SEVERITIES)}
SARIF_LEVEL = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}

DOCS = "https://www.jenkins.io/doc/book"


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    title: str
    why: str
    fix: str
    ref: str


RULES: Dict[str, Rule] = {
    rule.id: rule
    for rule in (
        Rule(
            "PD001", "critical", "Hardcoded secret",
            "A secret committed to source control is readable by everyone with "
            "repository access and stays in git history after it is deleted.",
            "Rotate the secret first, then store it in the Jenkins credentials "
            "store and bind it with withCredentials or credentials().",
            f"{DOCS}/using/using-credentials/",
        ),
        Rule(
            "PD002", "high", "Secret interpolated into a shell step by Groovy",
            "A double-quoted string lets Groovy substitute the secret before the "
            "shell starts, so the value lands in the command line and can appear "
            "in process listings on the agent.",
            "Use single quotes so the shell expands the variable: "
            "sh 'curl -u $USER:$TOKEN https://example.com'.",
            f"{DOCS}/pipeline/jenkinsfile/#string-interpolation",
        ),
        Rule(
            "PD003", "high", "Remote script piped into a shell",
            "The build runs whatever the remote host serves at that moment, with "
            "the agent's credentials and no integrity check.",
            "Download to a file, verify a pinned checksum, then run it, or install "
            "the tool in a versioned agent image.",
            f"{DOCS}/security/",
        ),
        Rule(
            "PD004", "high", "Privileged container or Docker socket mount",
            "--privileged and a mounted Docker socket both give the build "
            "root-equivalent control of the host, and of other builds on it.",
            "Build images with rootless BuildKit or Kaniko on an isolated agent "
            "and drop the privileged flag.",
            f"{DOCS}/security/",
        ),
        Rule(
            "PD005", "high", "Build runs on the Jenkins controller",
            "Code on the built-in node can read the controller's filesystem, "
            "including stored credentials and job configuration.",
            "Set the built-in node's executors to 0 and run builds on a labelled "
            "agent.",
            f"{DOCS}/security/controller-isolation/",
        ),
        Rule(
            "PD006", "medium", "Untrusted value interpolated into a shell step",
            "Build parameters and values such as branch names or pull request "
            "titles can be set by someone other than the pipeline author, so a "
            "crafted value becomes shell commands.",
            "Pass the value through the environment and quote it in the shell: "
            "withEnv([\"VERSION=${params.VERSION}\"]) { sh 'deploy \"$VERSION\"' }.",
            f"{DOCS}/pipeline/jenkinsfile/#injection-via-interpolation",
        ),
        Rule(
            "PD007", "medium", "TLS or host-key verification disabled",
            "Turning off verification lets anyone on the network path impersonate "
            "the server and tamper with what the build downloads or pushes.",
            "Trust the correct CA or pin the known host key instead of disabling "
            "the check.",
            f"{DOCS}/security/",
        ),
        Rule(
            "PD008", "medium", "Shared library not pinned to a release",
            "A library loaded from a moving branch can change every build without "
            "a change to this repository, which also makes old builds impossible "
            "to reproduce.",
            "Load a tag or commit: @Library('my-lib@v1.4.2') _.",
            f"{DOCS}/pipeline/shared-libraries/#library-versions",
        ),
        Rule(
            "PD009", "medium", "Container image not pinned",
            "A missing tag or :latest means the build environment can change "
            "between runs without any commit.",
            "Pin a version tag or, better, a digest: image 'maven:3.9.9-eclipse-temurin-21'.",
            f"{DOCS}/pipeline/docker/",
        ),
        Rule(
            "PD010", "medium", "Jenkins internal API used from a pipeline",
            "Jenkins.instance runs against the controller's internals, needs "
            "script approval, and tends to break during upgrades.",
            "Replace it with a pipeline step, or move it into a tested plugin or "
            "administrator script.",
            f"{DOCS}/managing/script-approval/",
        ),
        Rule(
            "PD011", "medium", "Pipeline has no timeout",
            "A hung command holds an executor forever and quietly starves every "
            "other build in the queue.",
            "Add options { timeout(time: 30, unit: 'MINUTES') } or wrap scripted "
            "stages in timeout().",
            f"{DOCS}/pipeline/syntax/#options",
        ),
        Rule(
            "PD012", "medium", "Pipeline step called inside @NonCPS",
            "Steps need the CPS engine, which @NonCPS methods bypass, so the "
            "method can silently stop after the first step.",
            "Remove @NonCPS from the method, or return data from it and call the "
            "step from CPS code.",
            f"{DOCS}/pipeline/cps-method-mismatches/",
        ),
        Rule(
            "PD013", "medium", "input step holds an executor",
            "While waiting for a person, the step keeps its agent and workspace "
            "busy, sometimes for days.",
            "Use a stage-level input directive with agent none at the top level, "
            "or move the input outside the node block.",
            f"{DOCS}/pipeline/syntax/#input",
        ),
        Rule(
            "PD014", "medium", "Deployment can run concurrently",
            "Two overlapping builds can deploy out of order and leave an older "
            "version live.",
            "Add options { disableConcurrentBuilds() } or guard the stage with "
            "lock() and milestone().",
            f"{DOCS}/pipeline/syntax/#options",
        ),
        Rule(
            "PD015", "medium", "Test or scan failure is hidden",
            "|| true turns a failing test or security scan into a green build, so "
            "the check no longer protects anything.",
            "Let the command fail, or record the result and mark the build "
            "unstable with unstable() or junit.",
            f"{DOCS}/pipeline/jenkinsfile/#handling-failure",
        ),
        Rule(
            "PD016", "low", "No build retention policy",
            "Old builds and artifacts accumulate on the controller until the disk "
            "fills and Jenkins stops.",
            "Add options { buildDiscarder(logRotator(numToKeepStr: '30')) } unless "
            "retention is set at job or folder level.",
            f"{DOCS}/pipeline/syntax/#options",
        ),
        Rule(
            "PD017", "low", "agent any",
            "The pipeline can land on any agent, including one without the "
            "required tools, which produces failures that depend on scheduling.",
            "Use a label or a pinned container so every run gets the same "
            "environment.",
            f"{DOCS}/pipeline/syntax/#agent",
        ),
        Rule(
            "PD018", "low", "Cron trigger without H",
            "A fixed minute makes many jobs start together and spikes load on the "
            "controller.",
            "Use the H symbol to spread the start time: cron('H 2 * * *').",
            f"{DOCS}/pipeline/syntax/#cron-syntax",
        ),
        Rule(
            "PD019", "low", "World-writable permissions",
            "chmod 777 lets any process on a shared agent change the file, "
            "including one that belongs to another build.",
            "Grant only the permission needed, for example chmod 750.",
            f"{DOCS}/security/",
        ),
    )
}


@dataclass
class Finding:
    rule: str
    severity: str
    title: str
    file: str
    line: int
    evidence: str
    detail: str
    fix: str
    ref: str


@dataclass(frozen=True)
class GroovyString:
    quote: str
    value: str
    start: int
    end: int

    @property
    def interpolates(self) -> bool:
        return self.quote in ('"', '"""')


class GroovySource:
    """Separates code from strings and comments, and maps offsets to lines."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.strings: List[GroovyString] = []
        self.masked = self._scan()
        self._line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
        self.lines = text.splitlines()
        self.blocks = self._find_blocks()

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self._line_starts, offset)

    def line_text(self, line: int) -> str:
        return self.lines[line - 1] if 0 < line <= len(self.lines) else ""

    def before(self, offset: int, width: int = 160) -> str:
        """Masked code immediately before an offset."""
        return self.masked[max(0, offset - width):offset]

    def _end_of_string(self, start: int, quote: str) -> int:
        text, size = self.text, len(self.text)
        triple = len(quote) == 3
        interpolates = quote[0] == '"'
        i = start + len(quote)
        while i < size:
            char = text[i]
            if char == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                return i + len(quote)
            if char == "\n" and not triple:
                return i
            if interpolates and text.startswith("${", i):
                i = self._end_of_expression(i + 2)
                continue
            i += 1
        return size

    def _end_of_expression(self, start: int) -> int:
        text, size = self.text, len(self.text)
        depth, i = 1, start
        while i < size and depth:
            char = text[i]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char in "'\"":
                quote = text[i:i + 3] if text[i:i + 3] in ("'''", '"""') else char
                i = self._end_of_string(i, quote)
                continue
            i += 1
        return i

    def _slashy_end(self, start: int, previous: str) -> Optional[int]:
        """Return the end of a /regex/ literal, or None if this is division."""
        if previous and previous not in "=(,~:[!&|?{};\n":
            return None
        line_end = self.text.find("\n", start)
        line_end = len(self.text) if line_end < 0 else line_end
        i = start + 1
        while i < line_end:
            if self.text[i] == "\\":
                i += 2
                continue
            if self.text[i] == "/":
                return i + 1
            i += 1
        return None

    def _scan(self) -> str:
        text = self.text
        size = len(text)
        out = list(text)

        def blank(begin: int, end: int) -> None:
            for k in range(begin, min(end, size)):
                if text[k] != "\n":
                    out[k] = " "

        i = 0
        previous = ""
        if text.startswith("#!"):
            end = text.find("\n")
            i = size if end < 0 else end
            blank(0, i)
        while i < size:
            char = text[i]
            pair = text[i:i + 2]
            triple = text[i:i + 3]
            if pair == "//":
                end = text.find("\n", i)
                end = size if end < 0 else end
                blank(i, end)
                i = end
            elif pair == "/*":
                end = text.find("*/", i + 2)
                end = size if end < 0 else end + 2
                blank(i, end)
                i = end
            elif triple in ("'''", '"""') or char in "'\"":
                quote = triple if triple in ("'''", '"""') else char
                end = self._end_of_string(i, quote)
                closed = text.startswith(quote, end - len(quote)) and end - i >= 2 * len(quote)
                inner_end = end - len(quote) if closed else end
                self.strings.append(GroovyString(quote, text[i + len(quote):inner_end], i, end))
                blank(i + len(quote), inner_end)
                i = end
                previous = char
            elif pair == "$/":
                end = text.find("/$", i + 2)
                end = size if end < 0 else end + 2
                blank(i, end)
                i = end
                previous = "'"
            elif char == "/":
                end = self._slashy_end(i, previous)
                if end is None:
                    previous = char
                    i += 1
                else:
                    blank(i, end)
                    i = end
                    previous = "'"
            else:
                if not char.isspace():
                    previous = char
                elif char == "\n" and previous in ("", "{", "}", ";"):
                    previous = "\n"
                i += 1
        return "".join(out)

    def _find_blocks(self) -> List[Tuple[int, int, str]]:
        stack: List[Tuple[int, str]] = []
        blocks: List[Tuple[int, int, str]] = []
        for i, char in enumerate(self.masked):
            if char == "{":
                header = re.split(r"[;{}\n]", self.masked[max(0, i - 200):i])[-1].strip()
                stack.append((i, header))
            elif char == "}" and stack:
                start, header = stack.pop()
                blocks.append((start, i, header))
        return blocks

    def enclosing(self, offset: int) -> List[str]:
        """Block headers around an offset, outermost first."""
        found = [b for b in self.blocks if b[0] < offset < b[1]]
        return [b[2] for b in sorted(found, key=lambda b: b[0])]


SHELL_STEP = re.compile(
    r"(?<![\w.])(?:(?:steps|script|this|ctx|context|pipeline)\.)?(?:sh|bat|powershell|pwsh)\b"
    r"\s*(?:\(\s*)?(?:\w+\s*:\s*[^,()]*,\s*)*(?:script\s*:\s*)?$"
)
INTERPOLATION = re.compile(r"\$(?:\{|([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*))")
DOTTED_NAME = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")
SECRET_BINDING = re.compile(
    r"\b(variable|passwordVariable|passphraseVariable|tokenVariable|"
    r"secretKeyVariable|accessKeyVariable)\s*:\s*$"
)
CREDENTIAL_ENV = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*credentials\s*\(")

TOKEN_PATTERNS = (
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("GitHub token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
)
PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----(?:\\n|\r?\n)[ \t]*[A-Za-z0-9+/=]{40,}"
)
K8S_SECRET_REFERENCE = re.compile(r"secretEnvVar|secretName|secretKeyRef|secretVolume")
LOWERCASE_PATH = re.compile(r"^[a-z0-9_.-]+(?:/[a-z0-9_.-]+)+/?$")
URL_PASSWORD = re.compile(r"\b[a-z][a-z0-9+.-]*://([^/\s:@$'\"{}<>]+):([^@\s$'\"{}<>/]+)@")
SENSITIVE_KEY = re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key)")
SAFE_KEY_ENDING = re.compile(
    r"(?i)(id|ids|name|names|file|path|url|uri|variable|var|param|credential|credentials|cred|creds|"
    r"header|field|prefix|suffix|type|env|ref|location|dir|key_?id|policy|role|length|expiry|ttl)$"
)
PLACEHOLDER = re.compile(
    r"(?i)^(<.*>|\*+|x+|\.+|none|null|nil|true|false|todo|tbd|n/?a)$|"
    r"change.?me|example|sample|your|dummy|placeholder|redacted|not.?a.?real|fake|test|default"
)
SLUG = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)+$")
SHELL_SECRET = re.compile(
    r"(?:--(?:password|passwd|token|api-key|secret)[= ]|\b(?:PASSWORD|PASSWD|API_KEY|SECRET|TOKEN)=)"
    r"(['\"]?)([^\s'\"$%`{}<>]{6,})"
)

PIPE_TO_SHELL = re.compile(r"\b(?:curl|wget)\b[^\n|;]*\|\s*(?:sudo\s+(?:-\w+\s+)*)?(?:ba|z|da)?sh\b")
PRIVILEGED = re.compile(r"--privileged\b|/var/run/docker\.sock")
TLS_OFF = (
    re.compile(r"\bcurl\b[^\n|;]*\s(?:--insecure\b|-[a-zA-Z]*k[a-zA-Z]*(?=\s))"),
    re.compile(r"\bwget\b[^\n|;]*--no-check-certificate"),
    re.compile(r"StrictHostKeyChecking[= ]+no\b"),
    re.compile(r"NODE_TLS_REJECT_UNAUTHORIZED=['\"]?0"),
    re.compile(r"GIT_SSL_NO_VERIFY=(?:true|1)"),
    re.compile(r"http\.sslVerify[= ]+false"),
    re.compile(r"--insecure-skip-tls-verify\b(?!=false)"),
    re.compile(r"--tls-verify=false|--skip-tls-verify\b"),
    re.compile(r"--trusted-host\b"),
)
UNTRUSTED_ENV = {
    "BRANCH_NAME", "GIT_BRANCH", "TAG_NAME", "CHANGE_BRANCH", "CHANGE_TITLE",
    "CHANGE_AUTHOR", "CHANGE_AUTHOR_DISPLAY_NAME", "CHANGE_AUTHOR_EMAIL", "CHANGE_FORK",
    "CHANGE_URL", "CHANGE_TARGET",
}
CONTROLLER_LABELS = {"master", "built-in", "built_in", "controller"}
MOVING_REFS = {"main", "master", "develop", "dev", "trunk", "head", "latest", "stable", "default"}
DEPLOY_STAGE = re.compile(r"(?i)\b(deploy\w*|publish\w*|promote\w*|rollout|prod|production)\b|^release(\s+to\b.*)?$")
CHECK_TOOL = re.compile(
    r"\b(pytest|go test|cargo test|npm (?:run )?test|yarn test|pnpm test|ctest|"
    r"mvnw?\b[^\n]*\b(?:test|verify)|gradlew?\b[^\n]*\b(?:test|check)|"
    r"eslint|flake8|ruff|pylint|mypy|golangci-lint|tflint|tfsec|checkov|trivy|grype|snyk|"
    r"semgrep|bandit|npm audit|pip-audit|terraform validate|kubeconform|hadolint|shellcheck)\b"
)
MASKED_FAILURE = re.compile(r"\|\|\s*(?:true\b|:(?=\s|$)|exit 0\b|echo\b)")
WORLD_WRITABLE = re.compile(r"\bchmod\s+(?:-[A-Za-z]+\s+)*(?:0?777|a\+rwx)\b")
JENKINS_API = re.compile(
    r"\b(?:Jenkins\s*\.\s*(?:instance\b|get\s*\(|getInstance\s*\(|getActiveInstance\s*\()|"
    r"Hudson\s*\.\s*(?:instance\b|getInstance\s*\())"
)
NONCPS_STEP = re.compile(
    r"(?<![\w.])(?:(?:steps|script|this|ctx|context)\.)?"
    r"(sh|bat|powershell|echo|node|stage|input|sleep|readFile|writeFile|withCredentials|withEnv|"
    r"timeout|retry|dir|checkout|build|parallel|archiveArtifacts|stash|unstash|error)"
    r"\s*(?:\(|'|\"|\{)"
)
INPUT_STEP = re.compile(r"(?<![\w.])input\s*(?:\(|message\s*:|id\s*:|'|\")")
HAS_TIMEOUT = re.compile(r"(?<![\w.])timeout\s*[({]|(?<![\w.])timeout\s+\w+\s*:")
HAS_GUARD = re.compile(r"\b(disableConcurrentBuilds|milestone)\b|(?<![\w.])lock\s*[({]|(?<![\w.])lock\s+\w+\s*:")
HAS_RETENTION = re.compile(r"\b(buildDiscarder|logRotator)\b")
PIPELINE_BLOCK = re.compile(r"(?<![\w.])pipeline\s*\{")
NODE_BLOCK = re.compile(r"(?<![\w.])node\s*(?:\([^)\n]*\))?\s*\{")
POD_IMAGE = re.compile(r"^\s*(?:-\s*)?image:\s*['\"]?([^\s'\"#]+)", re.M)
IGNORE = re.compile(r"pipeline-doctor:ignore(-file)?(?:\s+([A-Z0-9, ]+))?")


def shannon_entropy(value: str) -> float:
    counts = Counter(value)
    return -sum(n / len(value) * math.log2(n / len(value)) for n in counts.values())


def interpolations(value: str) -> Iterator[Tuple[int, List[str]]]:
    """Yield (position, dotted names) for each unescaped Groovy interpolation."""
    for match in INTERPOLATION.finditer(value):
        backslashes = 0
        i = match.start() - 1
        while i >= 0 and value[i] == "\\":
            backslashes += 1
            i -= 1
        if backslashes % 2:
            continue
        if match.group(1):
            yield match.start(), [match.group(1)]
            continue
        depth, i = 1, match.end()
        while i < len(value) and depth:
            depth += {"{": 1, "}": -1}.get(value[i], 0)
            i += 1
        expression = re.sub(r"'[^']*'|\"[^\"]*\"", " ", value[match.end():i - 1])
        yield match.start(), DOTTED_NAME.findall(expression)


def plain_name(name: str) -> str:
    return name[4:] if name.startswith("env.") else name


class Audit:
    def __init__(self, display_path: str, text: str) -> None:
        self.path = display_path
        self.src = GroovySource(text)
        self.findings: List[Finding] = []
        self.shell_strings = [s for s in self.src.strings if SHELL_STEP.search(self.src.before(s.start))]
        self.shell_offsets = {s.start for s in self.shell_strings}
        self.top_level_agent = self._top_level_agent()
        self.is_pipeline = bool(PIPELINE_BLOCK.search(self.src.masked))
        self.is_scripted = bool(NODE_BLOCK.search(self.src.masked))

    def _top_level_agent(self) -> Optional[Tuple[str, int]]:
        for match in re.finditer(r"(?<![\w.])agent\s+(any|none|\{)", self.src.masked):
            headers = self.src.enclosing(match.start())
            if len(headers) >= 1 and re.search(r"\bpipeline$", headers[-1]) :
                return match.group(1), match.start()
        return None

    def report(self, rule_id: str, offset: int, detail: str, evidence: Optional[str] = None,
               line: Optional[int] = None) -> None:
        rule = RULES[rule_id]
        number = line if line is not None else self.src.line_of(offset)
        shown = self.src.line_text(number).strip() if evidence is None else evidence
        if len(shown) > 140:
            shown = shown[:137] + "..."
        self.findings.append(Finding(
            rule=rule.id, severity=rule.severity, title=rule.title, file=self.path,
            line=number, evidence=shown, detail=detail, fix=rule.fix, ref=rule.ref,
        ))

    def string_line(self, item: GroovyString, inner_offset: int) -> int:
        return self.src.line_of(item.start + len(item.quote) + inner_offset)

    def run(self) -> List[Finding]:
        for check in (
            self.check_hardcoded_secrets, self.check_shell_interpolation, self.check_shell_commands,
            self.check_privileged, self.check_controller, self.check_libraries, self.check_images,
            self.check_internal_api, self.check_noncps, self.check_input, self.check_cron,
            self.check_pipeline_options,
        ):
            check()
        return self.apply_suppressions(self.dedupe())

    def dedupe(self) -> List[Finding]:
        seen: Set[Tuple[str, int, str]] = set()
        unique = []
        for finding in sorted(self.findings, key=lambda f: (f.line, f.rule)):
            key = (finding.rule, finding.line, finding.detail)
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        return unique

    def apply_suppressions(self, findings: List[Finding]) -> List[Finding]:
        per_line: Dict[int, Optional[Set[str]]] = {}
        for number, line in enumerate(self.src.lines, start=1):
            match = IGNORE.search(line)
            if not match:
                continue
            ids = set(re.findall(r"PD\d{3}", match.group(2) or "")) or None
            if match.group(1):
                if ids is None:
                    return []
                findings = [f for f in findings if f.rule not in ids]
                continue
            for target in (number, number + 1):
                per_line[target] = ids

        def suppressed(finding: Finding) -> bool:
            if finding.line not in per_line:
                return False
            ids = per_line[finding.line]
            return ids is None or finding.rule in ids

        return [f for f in findings if not suppressed(f)]

    def check_hardcoded_secrets(self) -> None:
        src = self.src
        for number, line in enumerate(src.lines, start=1):
            for label, pattern in TOKEN_PATTERNS:
                if pattern.search(line):
                    self.report("PD001", 0, f"Looks like a {label}.", f"[{label} redacted]", number)
            for match in URL_PASSWORD.finditer(line):
                user, password = match.group(1), match.group(2)
                if PLACEHOLDER.search(password) or password.lower() in {"pass", "password", "pwd"} or user == password:
                    continue
                self.report("PD001", 0, "URL contains an embedded password.", "[URL password redacted]", number)
        for match in PRIVATE_KEY.finditer(src.text):
            self.report("PD001", 0, "Looks like a private key.", "[private key redacted]", src.line_of(match.start()))

        for item in src.strings:
            if "$" in item.value or len(item.value) < 8 or " " in item.value.strip():
                continue
            key = re.search(r"([\w.-]+)['\"]?\s*(?:=|:)\s*$", src.before(item.start, 80))
            if not key:
                continue
            name = key.group(1).rsplit(".", 1)[-1]
            if not SENSITIVE_KEY.search(name) or SAFE_KEY_ENDING.search(name):
                continue
            if K8S_SECRET_REFERENCE.search(src.before(item.start, 160)):
                continue
            value = item.value.strip()
            if PLACEHOLDER.search(value) or SLUG.match(value) or value.startswith(("/", "http")):
                continue
            if LOWERCASE_PATH.match(value):  # A Vault path such as secret/team/ci/token.
                continue
            if shannon_entropy(value) < 2.5:
                continue
            self.report("PD001", item.start, f"Literal value assigned to '{name}'.",
                        f"{name} = [value redacted]")

        for item in self.shell_strings:
            for match in SHELL_SECRET.finditer(item.value):
                value = match.group(2)
                if PLACEHOLDER.search(value):
                    continue
                self.report("PD001", 0, "Literal secret passed on a command line.",
                            "[command-line secret redacted]", self.string_line(item, match.start()))

    def credential_names(self) -> Set[str]:
        names: Set[str] = set()
        for match in CREDENTIAL_ENV.finditer(self.src.masked):
            names.update({match.group(1), match.group(1) + "_PSW"})
        if "withCredentials" in self.src.masked:
            for item in self.src.strings:
                before = self.src.before(item.start, 120)
                if SECRET_BINDING.search(before) and not re.search(r"\bfile\s*\([^()]*$", before):
                    names.add(item.value)  # file() binds a path, not the secret itself.
        return names

    def check_shell_interpolation(self) -> None:
        secrets = self.credential_names()
        for item in self.shell_strings:
            if not item.interpolates:
                continue
            for position, names in interpolations(item.value):
                line = self.string_line(item, position)
                for name in names:
                    bare = plain_name(name)
                    if bare in secrets or bare.split(".")[0] in secrets:
                        self.report("PD002", 0, f"'{bare}' is a credential.", line=line)
                    elif bare.startswith("params."):
                        self.report("PD006", 0, f"Build parameter '{bare}' reaches the shell.", line=line)
                    elif bare in UNTRUSTED_ENV:
                        self.report("PD006", 0, f"'{bare}' can be set from outside the pipeline.", line=line)

    def check_shell_commands(self) -> None:
        for item in self.shell_strings:
            value = item.value
            for match in PIPE_TO_SHELL.finditer(value):
                self.report("PD003", 0, "Download is piped straight into a shell.",
                            line=self.string_line(item, match.start()))
            for pattern in TLS_OFF:
                for match in pattern.finditer(value):
                    self.report("PD007", 0, f"Found '{match.group(0).strip()[:50]}'.",
                                line=self.string_line(item, match.start()))
            for match in WORLD_WRITABLE.finditer(value):
                self.report("PD019", 0, "chmod grants write access to everyone.",
                            line=self.string_line(item, match.start()))
            offset = 0
            for segment in value.split("\n"):
                if CHECK_TOOL.search(segment) and MASKED_FAILURE.search(segment):
                    tool = CHECK_TOOL.search(segment).group(1)
                    self.report("PD015", 0, f"Failure of '{tool[:30]}' is ignored.",
                                line=self.string_line(item, offset))
                offset += len(segment) + 1

    def check_privileged(self) -> None:
        for item in self.src.strings:
            for match in PRIVILEGED.finditer(item.value):
                self.report("PD004", 0, f"Found '{match.group(0)}'.", line=self.string_line(item, match.start()))

    def check_controller(self) -> None:
        for item in self.src.strings:
            labels = {part.strip().lower() for part in re.split(r"\|\||&&|[()!]", item.value)}
            if not labels & CONTROLLER_LABELS:
                continue
            before = self.src.before(item.start, 40)
            if re.search(r"(?<![\w.])node\s*\(\s*$|\blabel\s*:?\s*\(?\s*$", before):
                self.report("PD005", item.start, f"Label '{item.value}' selects the controller.")

    def library_refs(self) -> Iterator[GroovyString]:
        masked = self.src.masked
        for match in re.finditer(r"@Library\s*\(", masked):
            depth, i = 1, match.end()
            while i < len(masked) and depth:
                depth += {"(": 1, ")": -1}.get(masked[i], 0)
                i += 1
            for item in self.src.strings:
                if match.end() <= item.start < i and not re.search(r"changelog\s*=\s*$", self.src.before(item.start, 20)):
                    yield item
        for item in self.src.strings:
            if re.search(r"(?<![\w.@])library\s*\(?\s*(?:identifier\s*:\s*)?$", self.src.before(item.start, 40)):
                yield item

    def check_libraries(self) -> None:
        for item in self.library_refs():
            value = item.value.strip()
            if not value or "$" in value:
                continue
            name, _, version = value.partition("@")
            if not version:
                self.report("PD008", item.start, f"'{name}' has no version, so it uses the configured default.")
            elif version.lower() in MOVING_REFS:
                self.report("PD008", item.start, f"'{name}' tracks the moving ref '{version}'.")

    def image_problem(self, reference: str) -> Optional[str]:
        if "$" in reference or "@sha256:" in reference or not reference:
            return None
        last = reference.rsplit("/", 1)[-1]
        if ":" not in last:
            return f"'{reference}' has no tag."
        if last.rsplit(":", 1)[1].lower() == "latest":
            return f"'{reference}' uses :latest."
        return None

    def check_images(self) -> None:
        for item in self.src.strings:
            before = self.src.before(item.start, 40)
            if re.search(r"\bimage\s*[:=(]?\s*$|docker\.image\s*\(\s*$", before):
                problem = self.image_problem(item.value.strip())
                if problem:
                    self.report("PD009", item.start, problem)
            if item.start not in self.shell_offsets and "\n" in item.value:
                for match in POD_IMAGE.finditer(item.value):
                    problem = self.image_problem(match.group(1))
                    if problem:
                        self.report("PD009", 0, problem, line=self.string_line(item, match.start(1)))

    def check_internal_api(self) -> None:
        for match in JENKINS_API.finditer(self.src.masked):
            self.report("PD010", match.start(), "Reaches into the controller's object model.")

    def check_noncps(self) -> None:
        masked = self.src.masked
        for match in re.finditer(r"@NonCPS\b", masked):
            body = next((b for b in sorted(self.src.blocks) if match.end() < b[0] < match.end() + 300), None)
            if body is None:
                continue
            for step in NONCPS_STEP.finditer(masked, body[0], body[1]):
                self.report("PD012", step.start(), f"Calls the '{step.group(1)}' step.")

    def check_input(self) -> None:
        for match in INPUT_STEP.finditer(self.src.masked):
            headers = self.src.enclosing(match.start())
            in_node = any(re.match(r"node\b", h) for h in headers)
            in_pipeline = any(re.search(r"\bpipeline$", h) for h in headers)
            holds_agent = in_pipeline and self.top_level_agent and self.top_level_agent[0] != "none"
            if in_node or holds_agent:
                self.report("PD013", match.start(), "Waits for a person while holding an agent.")

    def check_cron(self) -> None:
        for item in self.src.strings:
            if not re.search(r"(?<![\w.])(?:cron|pollSCM)\s*\(?\s*(?:spec\s*:\s*)?$", self.src.before(item.start, 30)):
                continue
            for raw in item.value.splitlines():
                spec = raw.strip()
                fields = spec.split()
                if len(fields) == 5 and not spec.startswith(("#", "TZ=", "@")) and "H" not in fields[0]:
                    self.report("PD018", item.start, f"Schedule '{spec}' fixes the minute.")

    def check_pipeline_options(self) -> None:
        masked = self.src.masked
        in_library = bool({"vars", "src"}.intersection(Path(self.path).parts))
        if self.is_pipeline or (self.is_scripted and not in_library):
            match = PIPELINE_BLOCK.search(masked) or NODE_BLOCK.search(masked)
            anchor = match.start()
            if not HAS_TIMEOUT.search(masked):
                self.report("PD011", anchor, "No timeout found anywhere in this file.")
            if not HAS_RETENTION.search(masked):
                self.report("PD016", anchor, "No buildDiscarder found in this file.")
        if self.top_level_agent and self.top_level_agent[0] == "any":
            self.report("PD017", self.top_level_agent[1], "Pipeline-level agent is 'any'.")
        if not HAS_GUARD.search(masked):
            for item in self.src.strings:
                is_stage = re.search(r"(?<![\w.])stage\s*\(\s*$", self.src.before(item.start, 20))
                if is_stage and DEPLOY_STAGE.search(item.value):
                    self.report("PD014", item.start, f"Stage '{item.value}' has no concurrency guard.")
                    break


SKIP_DIRS = {".git", "node_modules", "vendor", "target", "build", "dist", ".venv", "venv", "__pycache__", ".gradle"}
PIPELINE_DIRS = {"vars", "jenkins", ".jenkins", "pipelines", "pipeline", "ci", ".ci"}
NOT_PIPELINE_SUFFIX = {".md", ".txt", ".rst", ".png", ".svg", ".html", ".json", ".yml", ".yaml"}


def is_pipeline_file(path: Path, root: Path) -> bool:
    name = path.name.lower()
    if "jenkinsfile" in name:
        return path.suffix.lower() not in NOT_PIPELINE_SUFFIX
    if path.suffix != ".groovy":
        return False
    parts = path.relative_to(root).parts[:-1]
    if PIPELINE_DIRS.intersection(parts):
        return True
    return any(part == "src" and root.joinpath(*parts[:i], "vars").is_dir() for i, part in enumerate(parts))


def discover(targets: Sequence[str], exclude: Sequence[str]) -> Iterator[Tuple[Path, str]]:
    seen: Set[Path] = set()

    def excluded(display: str) -> bool:
        normalised = display.replace("\\", "/")
        return any(fnmatch.fnmatch(normalised, pattern) for pattern in exclude)

    for target in targets:
        path = Path(target)
        if path.is_file():
            if path.resolve() not in seen and not excluded(str(path)):
                seen.add(path.resolve())
                yield path, str(path)
        elif path.is_dir():
            for candidate in sorted(path.rglob("*")):
                relative = candidate.relative_to(path)
                if SKIP_DIRS.intersection(relative.parts) or not candidate.is_file():
                    continue
                if is_pipeline_file(candidate, path) and candidate.resolve() not in seen:
                    display = str(candidate)
                    if not excluded(display) and not excluded(str(relative)):
                        seen.add(candidate.resolve())
                        yield candidate, display
        else:
            raise FileNotFoundError(target)


def audit_targets(targets: Sequence[str], exclude: Sequence[str] = (), ignore: Iterable[str] = ()) -> Tuple[List[Finding], List[str]]:
    ignored = set(ignore)
    findings: List[Finding] = []
    scanned: List[str] = []
    for path, display in discover(targets, exclude):
        text = path.read_text(encoding="utf-8", errors="replace")
        scanned.append(display)
        findings.extend(f for f in Audit(display, text).run() if f.rule not in ignored)
    findings.sort(key=lambda f: (-SEVERITY_RANK[f.severity], f.file, f.line, f.rule))
    return findings, scanned


def summarise(findings: Sequence[Finding]) -> Dict[str, int]:
    counts = Counter(f.severity for f in findings)
    return {severity: counts.get(severity, 0) for severity in SEVERITIES}


def render_text(findings: Sequence[Finding], scanned: Sequence[str]) -> str:
    out: List[str] = []
    for finding in findings:
        out.append(f"{finding.file}:{finding.line}  {finding.severity.upper()}  {finding.rule}  {finding.title}")
        out.append(f"    {finding.detail}")
        out.append(f"    > {finding.evidence}")
        out.append(f"    Fix: {finding.fix}")
    totals = summarise(findings)
    if out:
        out.append("")
    out.append(f"Scanned {len(scanned)} file(s): " + ", ".join(f"{totals[s]} {s}" for s in SEVERITIES))
    return "\n".join(out)


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(findings: Sequence[Finding], scanned: Sequence[str]) -> str:
    totals = summarise(findings)
    out = [
        "# Pipeline audit report", "",
        f"Scanned **{len(scanned)}** file(s) with pipeline-doctor {__version__}.", "",
        "| Severity | Findings |", "| --- | --- |",
    ]
    out += [f"| {severity.title()} | {totals[severity]} |" for severity in SEVERITIES]
    out.append("")
    if not findings:
        out.append("No problems found.")
        return "\n".join(out)
    by_rule = Counter(f.rule for f in findings)
    out += ["## Fix these first", ""]
    ordered = sorted(by_rule, key=lambda r: (-SEVERITY_RANK[RULES[r].severity], -by_rule[r], r))
    for rule_id in ordered[:5]:
        rule = RULES[rule_id]
        out.append(f"1. **{rule.title}** ({rule.severity}, {by_rule[rule_id]} found). {rule.fix}")
    out += ["", "## Findings by rule", ""]
    for rule_id in ordered:
        rule = RULES[rule_id]
        out += [f"### {rule.id}: {rule.title}", "", f"**Severity:** {rule.severity}", "",
                f"**Why it matters:** {rule.why}", "", f"**Fix:** {rule.fix}", "",
                f"**Reference:** {rule.ref}", "", "| Location | Detail |", "| --- | --- |"]
        for finding in (f for f in findings if f.rule == rule_id):
            out.append(f"| `{finding.file}:{finding.line}` | {escape_cell(finding.detail)} |")
        out.append("")
    return "\n".join(out)


def render_sarif(findings: Sequence[Finding]) -> str:
    used = sorted({f.rule for f in findings})
    document = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "pipeline-doctor",
                "version": __version__,
                "rules": [{
                    "id": rule_id,
                    "name": RULES[rule_id].title,
                    "shortDescription": {"text": RULES[rule_id].title},
                    "fullDescription": {"text": RULES[rule_id].why},
                    "help": {"text": RULES[rule_id].fix},
                    "helpUri": RULES[rule_id].ref,
                    "defaultConfiguration": {"level": SARIF_LEVEL[RULES[rule_id].severity]},
                } for rule_id in used],
            }},
            "results": [{
                "ruleId": f.rule,
                "level": SARIF_LEVEL[f.severity],
                "message": {"text": f"{f.detail} {f.fix}"},
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": f.file.replace("\\", "/")},
                    "region": {"startLine": f.line},
                }}],
            } for f in findings],
        }],
    }
    return json.dumps(document, indent=2)


def render_rules_markdown() -> str:
    out = [
        "# pipeline-doctor rules", "",
        "Generated by `pipeline_doctor.py --list-rules --format markdown`. Do not edit by hand.", "",
    ]
    for rule in RULES.values():
        out += [f"## {rule.id}: {rule.title}", "", f"**Severity:** {rule.severity}", "",
                f"**Why it matters:** {rule.why}", "", f"**Fix:** {rule.fix}", "",
                f"**Reference:** {rule.ref}", ""]
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pipeline-doctor", description="Offline static audit for Jenkins pipelines.")
    parser.add_argument("paths", nargs="*", default=["."], help="files or directories to scan (default: .)")
    parser.add_argument("--format", choices=("text", "json", "markdown", "sarif"), default="text")
    parser.add_argument("--output", help="write the report to this file")
    parser.add_argument("--fail-on", choices=SEVERITIES + ("none",), default="high",
                        help="exit 1 if a finding is at or above this severity (default: high)")
    parser.add_argument("--ignore", default="", help="comma-separated rule IDs to skip")
    parser.add_argument("--exclude", action="append", default=[], help="glob of paths to skip; repeatable")
    parser.add_argument("--list-rules", action="store_true", help="print every rule and exit")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Windows consoles often cannot print every character found in a pipeline.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    if args.list_rules:
        if args.format == "markdown":
            print(render_rules_markdown())
        elif args.format == "json":
            print(json.dumps([asdict(rule) for rule in RULES.values()], indent=2))
        else:
            for rule in RULES.values():
                print(f"{rule.id}  {rule.severity:<8}  {rule.title}")
        return 0

    ignored = [item.strip() for item in args.ignore.split(",") if item.strip()]
    unknown = [item for item in ignored if item not in RULES]
    if unknown:
        print(f"pipeline-doctor: unknown rule ID: {', '.join(unknown)}", file=sys.stderr)
        return 2
    try:
        findings, scanned = audit_targets(args.paths, args.exclude, ignored)
    except FileNotFoundError as error:
        print(f"pipeline-doctor: path not found: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        report = json.dumps({
            "tool": "pipeline-doctor", "version": __version__, "files_scanned": scanned,
            "summary": summarise(findings), "findings": [asdict(f) for f in findings],
        }, indent=2)
    elif args.format == "markdown":
        report = render_markdown(findings, scanned)
    elif args.format == "sarif":
        report = render_sarif(findings)
    else:
        report = render_text(findings, scanned)

    if args.output:
        Path(args.output).write_text(report + "\n", encoding="utf-8")
    else:
        print(report)

    if args.fail_on == "none":
        return 0
    threshold = SEVERITY_RANK[args.fail_on]
    return 1 if any(SEVERITY_RANK[f.severity] >= threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
