# 1. Linux

Every container and every node is Linux. When a tool fails, these commands show what is really happening.

## Do it

```bash
# Processes: who started what?
ps -ef --forest | less
pstree -p "$$"

# Files: a name points to an inode, and the inode holds the permissions.
stat /etc/passwd
ls -li /etc/passwd

# Disk: free blocks and free inodes are separate limits.
df -h
df -i
du -xh / 2>/dev/null | sort -h | tail -20

# Network: which process is listening?
sudo ss -tlnp

# Logs: read a service's history.
journalctl -u ssh --since "1 hour ago"
```

Write a systemd unit that runs `python3 -m http.server 8080`. Start it, enable it, kill the process with `kill -9`, and add `Restart=on-failure` so it returns on its own.

## Break it

**A deleted file that still uses disk space.**

```bash
python3 -c "import time; f=open('/tmp/held','w'); f.write('x'*10**8); f.flush(); time.sleep(600)" &
df -h /tmp
rm /tmp/held
df -h /tmp          # The space is still in use.
du -sh /tmp         # du no longer counts it.
sudo lsof +L1 | grep held
kill %1
df -h /tmp          # Now the space returns.
```

**A signal that cannot be caught.**

```bash
python3 -c "
import signal, time
signal.signal(signal.SIGTERM, lambda *_: print('caught, ignoring'))
time.sleep(600)" &
kill %1          # Prints the message and keeps running.
kill -9 %1       # Ends it. SIGKILL cannot be caught.
```

## Explain it

- What is the difference between a process and a thread?
- What does a load average of 8 mean on a 4-core machine? Can load be high while CPU is idle?
- What is a zombie process, and why can you not kill one?
- Why can `df` show free space while writes fail with "No space left on device"?
- What does `chmod 640` mean, bit by bit?
- Why does Kubernetes send SIGTERM before SIGKILL?

## Done when

You can find the process holding a port, the file filling a disk and the reason a service restarted, using only the commands above.
