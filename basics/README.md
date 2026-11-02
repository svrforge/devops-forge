# DevOps basics

Nine hands-on modules, in order. Each one builds on the URL shortener in [`projects/01-url-shortener`](../projects/01-url-shortener).

| # | Module | You can answer |
| --- | --- | --- |
| 1 | [Linux](01-linux.md) | Why does the disk look full when `du` disagrees? |
| 2 | [Networking](02-networking.md) | What is the difference between refused and timed out? |
| 3 | [Git](03-git.md) | How do you recover from a bad reset? |
| 4 | [Docker](04-docker.md) | What does exit code 137 mean? |
| 5 | [Kubernetes](05-kubernetes.md) | Why is a pod running but receiving no traffic? |
| 6 | [Terraform](06-terraform.md) | What happens when state and reality disagree? |
| 7 | [CI/CD](07-cicd.md) | How does a pipeline leak a secret? |
| 8 | [Observability](08-observability.md) | Why should a metric label never hold a user ID? |
| 9 | [Security](09-security.md) | Why is rotating a leaked key more urgent than deleting it? |

**On Windows,** run these modules in a WSL Ubuntu terminal (`wsl --install -d Ubuntu`), because the commands assume Linux. Keep your clone inside WSL, for example under `~/projects`.

## How to work through a module

1. **Do it.** Type the commands yourself. Do not paste them.
2. **Break it.** Cause the failure on purpose and read the real error.
3. **Explain it.** Answer the questions aloud without notes, as if in an interview.
4. **Write it down.** Add a `notes/` file in your own words with what surprised you.

A module is done when you can reproduce the failure and explain the cause from memory.
