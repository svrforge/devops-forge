# 2. Networking

Most "the app is down" tickets are DNS, routing, a firewall or TLS. Learn to test each layer on its own.

## Do it

```bash
# DNS: name to address.
dig +short example.com
dig +trace example.com
getent hosts example.com       # What programs on this host actually use.

# Routing: which way does the traffic leave?
ip addr
ip route
ip route get 1.1.1.1

# TCP: is the port open?
nc -vz example.com 443

# TLS: which certificate does the server present?
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates

# HTTP: every layer together, with timings.
curl -v -o /dev/null -w 'dns %{time_namelookup}  connect %{time_connect}  tls %{time_appconnect}  total %{time_total}\n' https://example.com
```

Watch a real handshake while the shortener runs on port 8000:

```bash
sudo tcpdump -ni lo port 8000
curl http://127.0.0.1:8000/healthz     # In a second terminal. Find SYN, SYN-ACK and ACK.
```

## Break it

**Refused and timed out are different failures.**

```bash
curl --connect-timeout 3 http://127.0.0.1:9            # Refused: the host answered, nothing listens.
curl --connect-timeout 3 http://10.255.255.1           # Timed out: nothing answered at all.
```

**A firewall that drops and a firewall that rejects.**

```bash
sudo iptables -A INPUT -p tcp --dport 8000 -j REJECT
curl --connect-timeout 3 http://127.0.0.1:8000/healthz
sudo iptables -D INPUT -p tcp --dport 8000 -j REJECT

sudo iptables -A INPUT -p tcp --dport 8000 -j DROP
curl --connect-timeout 3 http://127.0.0.1:8000/healthz
sudo iptables -D INPUT -p tcp --dport 8000 -j DROP
```

**A name that lies.** Add `127.0.0.1 example.com` to `/etc/hosts`, compare `dig` with `getent hosts`, then remove the line. This shows why `dig` can look correct while the application connects somewhere else.

## Explain it

- Walk through everything that happens when you run `curl https://example.com`.
- What is the difference between TCP and UDP, and why does DNS mostly use UDP?
- What does a `/24` mean? How many usable addresses does it have?
- What is NAT, and why can a private instance reach the internet without a public address?
- What is the difference between a layer 4 and a layer 7 load balancer?
- What does SNI do, and why does the `openssl` command above pass `-servername`?

## Done when

Given "the site is unreachable", you can say which layer fails and prove it with one command per layer.
