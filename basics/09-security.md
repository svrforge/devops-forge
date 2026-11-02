# 9. Security

Security here means reducing what an attacker gets when something fails: fewer permissions, fewer secrets and less software.

## Do it

```bash
cd projects/01-url-shortener

# What does the image contain, and what is vulnerable?
docker build --target runtime -t url-shortener:0.1.0 .
trivy image --severity HIGH,CRITICAL url-shortener:0.1.0

# Are the Dockerfile and manifests safe?
trivy config .
```

Use a Trivy release that is not affected by the 2026 compromise. Check [the advisory](https://osv.dev/vulnerability/GHSA-69fq-xp46-6x23) and prefer pinning by digest.

Go through [`k8s/deployment.yaml`](../projects/01-url-shortener/k8s/deployment.yaml) and state what each of these prevents:

- `runAsNonRoot` and `runAsUser`
- `readOnlyRootFilesystem`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: ["ALL"]`
- `automountServiceAccountToken: false`
- `seccompProfile: RuntimeDefault`
- The `pod-security.kubernetes.io/enforce: restricted` label on the namespace

Then read [`k8s/networkpolicy.yaml`](../projects/01-url-shortener/k8s/networkpolicy.yaml) and draw which pod can reach which.

## Break it

**Prove the namespace rejects an unsafe pod.**

```bash
kubectl -n shortener run bad --image=alpine:3.20 --privileged -- sleep 60
```

Read the error. Admission control stopped the pod before it ran.

**Prove the network policy works.** It needs a CNI that enforces policies, so check that yours does. Then start a throwaway pod and try to reach Postgres on port 5432. It should fail, because only pods labelled `app: shortener` may connect.

**Find a fake secret.** Add a made-up `AKIA` value to a test Jenkinsfile and run pipeline-doctor. Notice that the report does not print the value. Reports get pasted into tickets, so they must never repeat a secret.

## Build on it

- Pin `python:3.13-slim` to a digest, and use Renovate or Dependabot to keep it current.
- Generate an SBOM with `trivy image --format cyclonedx`.
- Sign the image with cosign, and verify the signature before deploying.

## Explain it

- A key leaked. Why do you rotate it before you delete it from Git?
- What is the principle of least privilege? Give an example from this repository.
- Why is mounting the Docker socket equivalent to giving root on the host?
- What is the difference between authentication and authorisation?
- Kubernetes Secrets are base64 encoded. Is that encryption? What would you do about it?
- What is a software supply chain attack? Name two controls against it from this repository.

## Done when

You can read a Dockerfile, manifest or pipeline and list its three biggest risks in five minutes.
