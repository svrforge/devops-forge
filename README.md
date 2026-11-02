# DevOps Forge

[![CI](https://github.com/svrforge/devops-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/svrforge/devops-forge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

By [SVR Forge](https://github.com/svrforge). New to DevOps? Start with [DevOps First Pipeline](https://github.com/svrforge/devops-first-pipeline), then come back here.

DevOps fundamentals, a working project that goes from laptop to Kubernetes, and a free tool that audits Jenkins pipelines.

| Folder | What it is |
| --- | --- |
| [`basics/`](basics) | Nine hands-on modules: do it, break it, explain it |
| [`projects/`](projects) | End-to-end projects, starting with a URL shortener |
| [`plugins/pipeline-doctor/`](plugins/pipeline-doctor) | An offline Jenkins pipeline audit, for the command line, Claude Code and Codex |
| [`jenkins-local/`](jenkins-local) | Adds a Docker-capable agent to a Jenkins that runs in a container |

## Start here

- **Learning DevOps?** Start with [`basics/`](basics) and do the modules in order.
- **Want to see a full delivery path?** Open [Project 1](projects/01-url-shortener).
- **Run Jenkins?** Audit your pipelines in one command:

  ```bash
  python3 plugins/pipeline-doctor/skills/audit/scripts/pipeline_doctor.py /path/to/your/repo
  ```

  It reads files only, sends nothing anywhere and needs no Jenkins server. On Windows, use `python` if `python3` is not found. See a [sample report](plugins/pipeline-doctor/examples/sample-report.md).

## Install Pipeline Doctor as an agent skill

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

Then ask your agent to audit the Jenkins pipelines in your repository.

## Licence

[MIT](LICENSE)
