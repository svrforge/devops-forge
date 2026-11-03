# Pipeline Doctor

An offline audit for Jenkins pipelines. It reads Jenkinsfiles and shared-library Groovy, then reports security and reliability problems with the exact line and a fix.

- **No Jenkins server needed.** It reads files only, so it works on a laptop or in any CI system.
- **No dependencies.** It is one Python 3.8+ file that uses the standard library.
- **Nothing leaves your machine.** It makes no network calls and never runs the code it reads.
- **Detected secrets are redacted** from every report format.

See a [sample report](examples/sample-report.md) and the [19 rules](skills/audit/references/rules.md).

## Use it from the command line

From a clone of `svrforge/devops-forge`, first change into the plugin directory:

```bash
cd plugins/pipeline-doctor
```

Pass the path to the repository you want to audit; `.` scans the current directory.

```bash
python3 skills/audit/scripts/pipeline_doctor.py .
python3 skills/audit/scripts/pipeline_doctor.py Jenkinsfile --format markdown --output report.md
python3 skills/audit/scripts/pipeline_doctor.py . --format sarif --output results.sarif
```

On Windows, use `python` if `python3` is not found.

The exit code is 1 when a finding is at or above `--fail-on` (default `high`), so it can gate a CI stage.

Exit code `2` means a usage error or no matching pipeline files were scanned.
An empty scan is **NOT ASSESSED**, including when all files are excluded.
`--fail-on none` disables finding-based failures only; it does not allow empty scans.
JSON reports include `status` (`assessed` or `not_assessed`); SARIF reports include
the status and file count in run properties, and mark empty invocations unsuccessful.

## Use it as an agent skill

**Claude Code**

```bash
claude plugin marketplace add svrforge/devops-forge
claude plugin install pipeline-doctor@devops-forge
```

Then ask "audit my Jenkins pipelines" or run `/pipeline-doctor:audit`.

**Codex**

```bash
codex plugin marketplace add svrforge/devops-forge
codex plugin add pipeline-doctor@devops-forge
```

Then ask "audit my Jenkins pipelines".

Both integrations load `skills/audit/SKILL.md` from this plugin. These commands
install the free scanner. Pro is a separate private-repository distribution;
the free scanner reports suggested fixes and does not automatically edit pipelines.

## What it does not do

- It does not parse Groovy fully. It uses a purpose-built scanner, so unusual code can be missed.
- It cannot see job, folder or controller settings. A pipeline with no timeout in the file may have one set elsewhere.
- It checks Jenkins pipelines only.

A clean report means none of these 19 patterns were found. It does not mean the pipeline is secure.

## Tests

Run from the plugin directory used above:

```bash
python3 -m unittest discover -s tests
```

## Licence

MIT
