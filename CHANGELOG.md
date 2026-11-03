# Changelog

## 1.0.1 - 2026-11-03

- Return exit code `2` and report `NOT ASSESSED` when no matching pipeline files
  are scanned, even with `--fail-on none`.
- Include assessment status in JSON and scan coverage in SARIF, with an
  unsuccessful SARIF invocation for empty scans.
- Test empty, excluded and unrelated-file scans, clean reports and both plugin
  skill paths; clarify installation scope and the required working directory.

## 1.0.0 - 2026-11-03

First stable release.

### Added

- 19 security and reliability rules for Jenkinsfiles and shared-library Groovy
- Text, JSON, Markdown and SARIF reports, with secrets redacted from all of them
- `--fail-on` to stop unsafe pipelines in CI
- `--ignore`, `--exclude` and an inline `pipeline-doctor:ignore` comment for accepted findings
- A GitHub Action, `svrforge/devops-forge@v1.0.0`
- A skill for Claude Code and Codex
- A [sample audit report](docs/sample-audit-report.pdf)
