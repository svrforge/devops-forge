# Run the pipeline on your local Jenkins

Use this if Jenkins already runs as a Docker container on your machine. You keep your Jenkins as it is and add one agent beside it.

The project pipeline needs an agent labelled `docker` with the Docker CLI, Compose, Python and Trivy. The official Jenkins image does not include those tools, so a build would wait in the queue until it times out.

```text
Your Jenkins container  <---- WebSocket ----  agent container  ---- TLS ---->  private Docker daemon
(unchanged)                                   (this folder)                    (this folder)
```

Builds run on the private daemon. This keeps them away from your host's containers without mounting the host's Docker socket, which would hand every build root on your machine.

## Find your Jenkins first

Start Docker Desktop and your Jenkins container, then run this in PowerShell or a terminal:

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"
```

Look for the Jenkins row. `0.0.0.0:8080->8080/tcp` means Jenkins is on host port 8080. If the host port is different, or no port is published, fix that first and set `JENKINS_URL` in `.env` to match. `host.docker.internal` works on Docker Desktop for Windows and macOS, and on Linux through the `extra_hosts` line in `compose.yaml`.

## Set it up

1. **Create the agent in Jenkins.** Go to **Manage Jenkins > Nodes > New Node**, name it `docker-agent` and choose **Permanent Agent**. Then set:
   - **Number of executors:** `2`
   - **Remote root directory:** `/home/jenkins/agent`
   - **Labels:** `docker`
   - **Launch method:** Launch agent by connecting it to the controller

   The agent connects over WebSocket because `compose.yaml` sets `JENKINS_WEB_SOCKET`, so you do not need to publish port 50000.

2. **Copy the secret.** Open the new node's page and copy the secret from the command shown there.

3. **Start the agent.**

   ```bash
   cd jenkins-local
   cp .env.example .env     # Then set JENKINS_URL and paste the secret into .env.
   docker compose up -d --build
   docker compose logs -f agent
   ```

   The node should show as connected in Jenkins within a minute.

4. **Stop builds running on the controller.** Go to **Manage Jenkins > Nodes > Built-In Node > Configure** and set **Number of executors** to `0`. Code on the controller can read its credentials and configuration, so builds belong on agents.

5. **Create the job.** Go to **New Item > Pipeline**. Under **Pipeline**, choose **Pipeline script from SCM**, enter your Git repository URL, and set **Script Path** to `projects/01-url-shortener/Jenkinsfile`. Then select **Build Now**.

## If it does not connect

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Failed to connect` in the agent log | Jenkins is not on host port 8080 | Run `docker ps` to find the published port, then correct `JENKINS_URL` in `.env` |
| `403` or `Incorrect secret` in the agent log | The secret or agent name is wrong | Copy the secret again, and make sure the name matches the node exactly |
| The build waits for `docker` | The agent is offline or the label is missing | Check the node page in Jenkins |
| `Cannot connect to the Docker daemon` | The private daemon is still starting | Run `docker compose ps` and wait until `dind` is healthy |

To avoid the host network path, attach the agent to your Jenkins container's Docker network instead, and set `JENKINS_URL` to `http://<jenkins-container-name>:8080`.
