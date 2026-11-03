<div align="center">

<img src="assets/hero.svg" width="100%" alt="Pipeline Doctor by SVR Forge: find the Jenkins mistakes that leak secrets, stall builds and break releases." />

<br />

[![CI](https://github.com/svrforge/devops-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/svrforge/devops-forge/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/svrforge/devops-forge?color=0F827B)](https://github.com/svrforge/devops-forge/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-0F827B.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-101A30.svg)
![Dependencies: none](https://img.shields.io/badge/Dependencies-none-101A30.svg)
![Rules: 19](https://img.shields.io/badge/Rules-19-101A30.svg)

**Audit every Jenkins pipeline in seconds. No Jenkins server, no install and nothing leaves your machine.**

[Quick start](#quick-start) &nbsp;·&nbsp; [What it finds](#what-it-finds) &nbsp;·&nbsp; [Use it in CI](#use-it-in-ci) &nbsp;·&nbsp; [Agent skill](#use-it-as-an-agent-skill) &nbsp;·&nbsp; [Pro](#pipeline-doctor-pro) &nbsp;·&nbsp; [Professional audit](#professional-audit)

</div>

<br />

<img src="assets/demo.svg" width="100%" alt="Terminal output showing findings with line numbers, severity and a fix for each one." />

<sub>Shortened output from a deliberately insecure test pipeline. Read the [full sample report](plugins/pipeline-doctor/examples/sample-report.md).</sub>

## Why Pipeline Doctor

Jenkins will happily run a pipeline that leaks a password, hangs forever or deploys out of order. Syntax checkers confirm that a Jenkinsfile is valid. Pipeline Doctor checks whether it is safe.

<table>
<tr>
<td width="50%" valign="top">

**Security first**

Finds hardcoded secrets, credentials leaked through Groovy interpolation, shell injection, privileged containers and builds on the controller.

</td>
<td width="50%" valign="top">

**A fix for every finding**

Each result gives the file, the line, why it matters and what to change, so a report turns straight into work.

</td>
</tr>
<tr>
<td width="50%" valign="top">

**Private by design**

It reads files and nothing else. It makes no network calls, never runs your code and redacts secrets from every report.

</td>
<td width="50%" valign="top">

**Runs anywhere**

One Python file with no dependencies. It works on Linux, macOS and Windows, on a laptop or in any CI system.

</td>
</tr>
</table>

## Quick start

```bash
curl -fsSLO https://raw.githubusercontent.com/svrforge/devops-forge/main/plugins/pipeline-doctor/skills/audit/scripts/pipeline_doctor.py
python3 pipeline_doctor.py /path/to/your/repo
```

On Windows, use `curl.exe` and `python`. It finds Jenkinsfiles and shared-library Groovy automatically.

```bash
python3 pipeline_doctor.py . --format markdown --output report.md    # A report to share
python3 pipeline_doctor.py . --format sarif --output results.sarif   # GitHub code scanning
python3 pipeline_doctor.py . --format json                           # Your own tooling
```

## What it finds

| Severity | Rule | Finding |
| :--- | :--- | :--- |
| Critical | PD001 | Hardcoded secret |
| High | PD002 | Secret interpolated into a shell step by Groovy |
| High | PD003 | Remote script piped into a shell |
| High | PD004 | Privileged container or Docker socket mount |
| High | PD005 | Build runs on the Jenkins controller |
| Medium | PD006 | Untrusted value interpolated into a shell step |
| Medium | PD007 | TLS or host-key verification disabled |
| Medium | PD008 | Shared library not pinned to a release |
| Medium | PD009 | Container image not pinned |
| Medium | PD010 | Jenkins internal API used from a pipeline |
| Medium | PD011 | Pipeline has no timeout |
| Medium | PD012 | Pipeline step called inside `@NonCPS` |
| Medium | PD013 | `input` step holds an executor |
| Medium | PD014 | Deployment can run concurrently |
| Medium | PD015 | Test or scan failure is hidden |
| Low | PD016 | No build retention policy |
| Low | PD017 | `agent any` |
| Low | PD018 | Cron trigger without `H` |
| Low | PD019 | World-writable permissions |

[Read why each rule matters and how to fix it.](plugins/pipeline-doctor/skills/audit/references/rules.md)

## Use it in CI

The exit code is 1 when a finding is at or above `--fail-on`, so one command can stop an unsafe pipeline from merging.

If no matching pipeline files are scanned, the result is **NOT ASSESSED** and
the exit code is `2`, including with `--fail-on none`. Check the target path
and exclusions; an empty scan is not a clean audit. JSON exposes `status`, and
SARIF includes scan coverage and an unsuccessful invocation for empty scans.
This behaviour is available from `v1.0.1`. Update existing `v1.0.0` pins to
receive the fix.

**GitHub Actions**

```yaml
- uses: actions/checkout@v7
- uses: svrforge/devops-forge@v1.0.1
  with:
    fail-on: high
```

The action also accepts `path`, `format`, `output` and `ignore`.

**Jenkins**

```groovy
stage('Audit pipelines') {
    steps {
        sh 'python3 pipeline_doctor.py . --fail-on high'
    }
}
```

For production CI, pin the action to a commit and keep a reviewed copy of the script in your repository for Jenkins.

To accept a finding on purpose, add a comment on the same line or the line above:

```groovy
// pipeline-doctor:ignore PD009
```

## Use it as an agent skill

Pipeline Doctor installs as a skill, so your coding agent can run the audit, confirm the findings and propose exact fixes.

**Claude Code**

```bash
claude plugin marketplace add svrforge/devops-forge
claude plugin install pipeline-doctor@devops-forge
```

**Codex**

```bash
codex plugin marketplace add svrforge/devops-forge
codex plugin add pipeline-doctor@devops-forge
```

Then ask: *"Audit the Jenkins pipelines in this repository."*

Both integrations load the free `plugins/pipeline-doctor/skills/audit/SKILL.md`
skill. Pro is distributed separately through a private repository. The free
scanner suggests fixes; it does not automatically modify your pipelines.

## Built to be trusted

- **Tested on real pipelines.** Rules were tuned against 673 public Jenkinsfiles and shared-library files.
- **Tested in CI.** A unit test suite runs on Linux, macOS and Windows, and this repository's own [Jenkinsfile](Jenkinsfile) must pass its own audit.
- **Honest about limits.** It is a fast static check for these 19 patterns. It cannot see job, folder or controller settings, so a clean report does not prove that a pipeline is secure.

## Pipeline Doctor Pro

Need more than a scan? Pro adds deeper checks, automatic fixes and client-ready PDF reports. It works from the command line and as a skill for Claude Code and Codex.

| | Free | Pro |
| :--- | :--- | :--- |
| Rules | 19 | 51 |
| Release safety checks | | Yes |
| Jenkins configuration and plugin lists | | Yes |
| Automatic fixes | | Yes |
| Client-ready PDF reports | | Yes |

**[Get Pipeline Doctor Pro for $29](https://buy.polar.sh/polar_cl_ms4jpRHOeIZXsw2d84ThGv5OAoZdyfhFSlsOk1cluxp)**

One-time payment. You need a GitHub account, because Pro is delivered through a private repository.

## Professional audit

The scanner finds known patterns. I also read your pipelines by hand and find what it cannot see, such as a release that can still ship after a failed test.

| | Quick Check | Pipeline Audit | Audit + Fixes |
| :--- | :--- | :--- | :--- |
| **Price** | **$149** | **$499** | **$999** |
| Pipelines | Up to 3 | Up to 10 | Up to 10 |
| Delivery | 2 business days | 5 business days | 10 business days |
| Scanner and manual review | Yes | Yes | Yes |
| Prioritised findings with exact fixes | Yes | Yes | Yes |
| Report for engineers and managers | | Yes | Yes |
| 30-minute walkthrough | | Yes | Yes |
| Pull requests for critical and high findings | | | Yes |

**Founding offer:** the first 3 Pipeline Audits are $299 in exchange for an honest written testimonial.

**[See a sample report (PDF)](docs/sample-audit-report.pdf)** &nbsp;·&nbsp; **[Email kavin41251@gmail.com](mailto:kavin41251@gmail.com?subject=Jenkins%20pipeline%20audit)**

More than 10 pipelines, or a team in India? Email me for a quote. Please do not send secrets or pipeline code in your first message.

## About

Built by [Vignesh Raja Sundararajan](https://github.com/svrforge), a DevOps and platform engineer, at SVR Forge.

Released under the [MIT License](LICENSE). Free to use, including at work.
