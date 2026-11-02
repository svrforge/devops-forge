# 7. CI/CD

A pipeline is code with production credentials. Treat it with the same care as production.

This repository has two real examples: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) and the project's [`Jenkinsfile`](../projects/01-url-shortener/Jenkinsfile).

## Do it

Run Jenkins in a container and connect an agent that can use Docker. If Jenkins is already running, follow [`jenkins-local/`](../jenkins-local) to add the agent and create the job. Then:

1. Read the Jenkinsfile and explain each `options` entry.
2. Run the audit stage and read its output:

   ```bash
   python3 plugins/pipeline-doctor/skills/audit/scripts/pipeline_doctor.py projects/01-url-shortener/Jenkinsfile
   ```

3. Move the test stage into a shared library step, tag the library `v1.0.0`, and load it with `@Library('my-lib@v1.0.0') _`.
4. Read every workflow job in `ci.yml` and explain why actions are pinned to a full commit SHA.

The SHA pinning is not theoretical. On 19 March 2026, attackers force-pushed malicious commits to the `trivy-action` version tags, so pipelines that referenced those tags ran the attacker's code. A full commit SHA cannot be moved in that way. See [GHSA-69fq-xp46-6x23](https://osv.dev/vulnerability/GHSA-69fq-xp46-6x23).

## Break it

Audit the deliberately bad pipeline, then fix every finding in a copy of it:

```bash
cp plugins/pipeline-doctor/tests/fixtures/insecure.Jenkinsfile /tmp/Jenkinsfile
python3 plugins/pipeline-doctor/skills/audit/scripts/pipeline_doctor.py /tmp/Jenkinsfile
```

For each rule, explain the risk in one sentence before you change anything. Rules that are hardest to understand are the ones to practise, and [`rules.md`](../plugins/pipeline-doctor/skills/audit/references/rules.md) explains each one.

Then see the most important one for yourself: in a test job, bind a dummy secret and run `sh "echo ${SECRET}"` and `sh 'echo $SECRET'`. Compare the warning Jenkins shows for each.

## Explain it

- What is the difference between continuous delivery and continuous deployment?
- Why is `sh "curl -u ${USER}:${PASS} ..."` unsafe when `sh 'curl -u $USER:$PASS ...'` is safe?
- How can a pull request from a fork steal secrets, and how do you prevent it?
- Why must a shared library be pinned to a tag?
- Why does `@NonCPS` break when a method calls a pipeline step?
- How would you roll back a bad deployment? What about a database change?
- What is the difference between blue-green and canary deployment?

## Done when

Your own Jenkinsfile passes `--fail-on medium`, and you can explain every rule without reading it.
