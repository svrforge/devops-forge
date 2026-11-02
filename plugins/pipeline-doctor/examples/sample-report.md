# Pipeline audit report

Scanned **1** file(s) with pipeline-doctor 1.0.0. This report comes from a deliberately insecure test pipeline.

| Severity | Findings |
| --- | --- |
| Critical | 1 |
| High | 6 |
| Medium | 14 |
| Low | 4 |

## Fix these first

1. **Hardcoded secret** (critical, 1 found). Rotate the secret first, then store it in the Jenkins credentials store and bind it with withCredentials or credentials().
1. **Secret interpolated into a shell step by Groovy** (high, 2 found). Use single quotes so the shell expands the variable: sh 'curl -u $USER:$TOKEN https://example.com'.
1. **Privileged container or Docker socket mount** (high, 2 found). Build images with rootless BuildKit or Kaniko on an isolated agent and drop the privileged flag.
1. **Remote script piped into a shell** (high, 1 found). Download to a file, verify a pinned checksum, then run it, or install the tool in a versioned agent image.
1. **Build runs on the Jenkins controller** (high, 1 found). Set the built-in node's executors to 0 and run builds on a labelled agent.

## Findings by rule

### PD001: Hardcoded secret

**Severity:** critical

**Why it matters:** A secret committed to source control is readable by everyone with repository access and stays in git history after it is deleted.

**Fix:** Rotate the secret first, then store it in the Jenkins credentials store and bind it with withCredentials or credentials().

**Reference:** https://www.jenkins.io/doc/book/using/using-credentials/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:12` | Literal value assigned to 'API_PASSWORD'. |

### PD002: Secret interpolated into a shell step by Groovy

**Severity:** high

**Why it matters:** A double-quoted string lets Groovy substitute the secret before the shell starts, so the value lands in the command line and can appear in process listings on the agent.

**Fix:** Use single quotes so the shell expands the variable: sh 'curl -u $USER:$TOKEN https://example.com'.

**Reference:** https://www.jenkins.io/doc/book/pipeline/jenkinsfile/#string-interpolation

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:22` | 'REGISTRY_CREDS_PSW' is a credential. |
| `tests/fixtures/insecure.Jenkinsfile:41` | 'API_TOKEN' is a credential. |

### PD004: Privileged container or Docker socket mount

**Severity:** high

**Why it matters:** --privileged and a mounted Docker socket both give the build root-equivalent control of the host, and of other builds on it.

**Fix:** Build images with rootless BuildKit or Kaniko on an isolated agent and drop the privileged flag.

**Reference:** https://www.jenkins.io/doc/book/security/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:20` | Found '/var/run/docker.sock'. |
| `tests/fixtures/insecure.Jenkinsfile:54` | Found '--privileged'. |

### PD003: Remote script piped into a shell

**Severity:** high

**Why it matters:** The build runs whatever the remote host serves at that moment, with the agent's credentials and no integrity check.

**Fix:** Download to a file, verify a pinned checksum, then run it, or install the tool in a versioned agent image.

**Reference:** https://www.jenkins.io/doc/book/security/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:25` | Download is piped straight into a shell. |

### PD005: Build runs on the Jenkins controller

**Severity:** high

**Why it matters:** Code on the built-in node can read the controller's filesystem, including stored credentials and job configuration.

**Fix:** Set the built-in node's executors to 0 and run builds on a labelled agent.

**Reference:** https://www.jenkins.io/doc/book/security/controller-isolation/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:52` | Label 'master' selects the controller. |

### PD006: Untrusted value interpolated into a shell step

**Severity:** medium

**Why it matters:** Build parameters and values such as branch names or pull request titles can be set by someone other than the pipeline author, so a crafted value becomes shell commands.

**Fix:** Pass the value through the environment and quote it in the shell: withEnv(["VERSION=${params.VERSION}"]) { sh 'deploy "$VERSION"' }.

**Reference:** https://www.jenkins.io/doc/book/pipeline/jenkinsfile/#injection-via-interpolation

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:23` | Build parameter 'params.VERSION' reaches the shell. |
| `tests/fixtures/insecure.Jenkinsfile:24` | 'BRANCH_NAME' can be set from outside the pipeline. |

### PD007: TLS or host-key verification disabled

**Severity:** medium

**Why it matters:** Turning off verification lets anyone on the network path impersonate the server and tamper with what the build downloads or pushes.

**Fix:** Trust the correct CA or pin the known host key instead of disabling the check.

**Reference:** https://www.jenkins.io/doc/book/security/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:32` | Found 'curl -k'. |
| `tests/fixtures/insecure.Jenkinsfile:43` | Found 'StrictHostKeyChecking=no'. |

### PD008: Shared library not pinned to a release

**Severity:** medium

**Why it matters:** A library loaded from a moving branch can change every build without a change to this repository, which also makes old builds impossible to reproduce.

**Fix:** Load a tag or commit: @Library('my-lib@v1.4.2') _.

**Reference:** https://www.jenkins.io/doc/book/pipeline/shared-libraries/#library-versions

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:2` | 'platform-lib' tracks the moving ref 'main'. |
| `tests/fixtures/insecure.Jenkinsfile:3` | 'shared-steps' has no version, so it uses the configured default. |

### PD015: Test or scan failure is hidden

**Severity:** medium

**Why it matters:** || true turns a failing test or security scan into a green build, so the check no longer protects anything.

**Fix:** Let the command fail, or record the result and mark the build unstable with unstable() or junit.

**Reference:** https://www.jenkins.io/doc/book/pipeline/jenkinsfile/#handling-failure

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:31` | Failure of 'pytest' is ignored. |
| `tests/fixtures/insecure.Jenkinsfile:33` | Failure of 'trivy' is ignored. |

### PD009: Container image not pinned

**Severity:** medium

**Why it matters:** A missing tag or :latest means the build environment can change between runs without any commit.

**Fix:** Pin a version tag or, better, a digest: image 'maven:3.9.9-eclipse-temurin-21'.

**Reference:** https://www.jenkins.io/doc/book/pipeline/docker/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:20` | 'maven:latest' uses :latest. |

### PD010: Jenkins internal API used from a pipeline

**Severity:** medium

**Why it matters:** Jenkins.instance runs against the controller's internals, needs script approval, and tends to break during upgrades.

**Fix:** Replace it with a pipeline step, or move it into a tested plugin or administrator script.

**Reference:** https://www.jenkins.io/doc/book/managing/script-approval/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:46` | Reaches into the controller's object model. |

### PD011: Pipeline has no timeout

**Severity:** medium

**Why it matters:** A hung command holds an executor forever and quietly starves every other build in the queue.

**Fix:** Add options { timeout(time: 30, unit: 'MINUTES') } or wrap scripted stages in timeout().

**Reference:** https://www.jenkins.io/doc/book/pipeline/syntax/#options

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:5` | No timeout found anywhere in this file. |

### PD012: Pipeline step called inside @NonCPS

**Severity:** medium

**Why it matters:** Steps need the CPS engine, which @NonCPS methods bypass, so the method can silently stop after the first step.

**Fix:** Remove @NonCPS from the method, or return data from it and call the step from CPS code.

**Reference:** https://www.jenkins.io/doc/book/pipeline/cps-method-mismatches/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:63` | Calls the 'sh' step. |

### PD013: input step holds an executor

**Severity:** medium

**Why it matters:** While waiting for a person, the step keeps its agent and workspace busy, sometimes for days.

**Fix:** Use a stage-level input directive with agent none at the top level, or move the input outside the node block.

**Reference:** https://www.jenkins.io/doc/book/pipeline/syntax/#input

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:38` | Waits for a person while holding an agent. |

### PD014: Deployment can run concurrently

**Severity:** medium

**Why it matters:** Two overlapping builds can deploy out of order and leave an older version live.

**Fix:** Add options { disableConcurrentBuilds() } or guard the stage with lock() and milestone().

**Reference:** https://www.jenkins.io/doc/book/pipeline/syntax/#options

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:36` | Stage 'Deploy to prod' has no concurrency guard. |

### PD016: No build retention policy

**Severity:** low

**Why it matters:** Old builds and artifacts accumulate on the controller until the disk fills and Jenkins stops.

**Fix:** Add options { buildDiscarder(logRotator(numToKeepStr: '30')) } unless retention is set at job or folder level.

**Reference:** https://www.jenkins.io/doc/book/pipeline/syntax/#options

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:5` | No buildDiscarder found in this file. |

### PD017: agent any

**Severity:** low

**Why it matters:** The pipeline can land on any agent, including one without the required tools, which produces failures that depend on scheduling.

**Fix:** Use a label or a pinned container so every run gets the same environment.

**Reference:** https://www.jenkins.io/doc/book/pipeline/syntax/#agent

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:6` | Pipeline-level agent is 'any'. |

### PD018: Cron trigger without H

**Severity:** low

**Why it matters:** A fixed minute makes many jobs start together and spikes load on the controller.

**Fix:** Use the H symbol to spread the start time: cron('H 2 * * *').

**Reference:** https://www.jenkins.io/doc/book/pipeline/syntax/#cron-syntax

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:8` | Schedule '0 2 * * *' fixes the minute. |

### PD019: World-writable permissions

**Severity:** low

**Why it matters:** chmod 777 lets any process on a shared agent change the file, including one that belongs to another build.

**Fix:** Grant only the permission needed, for example chmod 750.

**Reference:** https://www.jenkins.io/doc/book/security/

| Location | Detail |
| --- | --- |
| `tests/fixtures/insecure.Jenkinsfile:26` | chmod grants write access to everyone. |

