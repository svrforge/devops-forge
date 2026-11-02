# 5. Kubernetes

Kubernetes keeps comparing what you asked for with what exists, and keeps correcting the difference. Debugging means finding which step of that loop is stuck.

Install [kind](https://kind.sigs.k8s.io/) and kubectl, then use the manifests in [`projects/01-url-shortener/k8s`](../projects/01-url-shortener/k8s).

## Do it

```bash
cd projects/01-url-shortener
docker build --target runtime -t url-shortener:0.1.0 .
kind create cluster --name lab
kind load docker-image url-shortener:0.1.0 --name lab

kubectl apply -f k8s/namespace.yaml
PW=$(openssl rand -hex 16)
kubectl -n shortener create secret generic shortener-db \
  --from-literal=password="$PW" \
  --from-literal=url="postgresql://shortener:$PW@postgres:5432/shortener"

kubectl apply -k k8s
kubectl -n shortener get pods -w
kubectl -n shortener port-forward svc/shortener 8000:80
curl localhost:8000/readyz
```

Then read each manifest and explain every field in [`deployment.yaml`](../projects/01-url-shortener/k8s/deployment.yaml). Why two probes? Why does the app have a memory limit but no CPU limit? Why does the migration run in an init container?

## Break it

Fix each one using only `kubectl get`, `describe`, `logs` and `events`.

```bash
# ImagePullBackOff
kubectl -n shortener set image deployment/shortener app=url-shortener:does-not-exist
kubectl -n shortener get pods
kubectl -n shortener rollout status deployment/shortener --timeout=30s
kubectl -n shortener rollout undo deployment/shortener

# OOMKilled
kubectl -n shortener patch deployment shortener --type=json \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"8Mi"}]'
kubectl -n shortener get pods -w
kubectl -n shortener rollout undo deployment/shortener

# Running, but not ready
kubectl -n shortener scale statefulset postgres --replicas=0
kubectl -n shortener get pods
kubectl -n shortener get endpointslices
kubectl -n shortener scale statefulset postgres --replicas=1

# A rollout that protects you: the old pods keep serving.
kubectl -n shortener set env deployment/shortener DATABASE_URL=postgresql://wrong@nowhere/none
kubectl -n shortener get pods
kubectl -n shortener rollout undo deployment/shortener
```

In the last exercise, notice that `maxUnavailable: 0` kept the service up during a bad release.

## Explain it

- What happens, step by step, between `kubectl apply` and a container running?
- What is the difference between liveness and readiness? Why must liveness not check the database?
- How does a Service find its pods?
- What is the difference between requests and limits? What happens at each limit for CPU and for memory?
- What is the difference between a Deployment and a StatefulSet?
- What does a PodDisruptionBudget protect against?
- A pod is `CrashLoopBackOff`. What are your first three commands?

## Done when

You can cause and fix each failure above without notes, and explain why the service stayed up.
