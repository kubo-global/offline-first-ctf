# The browser terminal: a web page with a terminal that logs in to the player's own
# box over SSH, for laptops without an ssh client or where it is blocked.
FROM debian:trixie-slim
ARG TARGETARCH
ARG TTYD_VERSION=1.7.7
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client ca-certificates curl \
 && case "$TARGETARCH" in amd64) a=x86_64;; arm64) a=aarch64;; *) echo "unsupported $TARGETARCH"; exit 1;; esac \
 && curl -fsSL -o /usr/local/bin/ttyd "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.$a" \
 && curl -fsSL -o /tmp/SHA256SUMS "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/SHA256SUMS" \
 && (cd /usr/local/bin && grep " ttyd.$a\$" /tmp/SHA256SUMS | sed "s/ttyd.$a/ttyd/" | sha256sum -c -) \
 && chmod 755 /usr/local/bin/ttyd \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /tmp/SHA256SUMS \
 && useradd -m term
COPY login.sh /usr/local/bin/login.sh
RUN chmod 755 /usr/local/bin/login.sh
USER term
EXPOSE 7681
# -W: the terminal accepts typing; -m: at most this many open terminals at once
CMD ["ttyd", "-W", "-p", "7681", "-m", "120", "-t", "titleFixed=CTF terminal", "-t", "fontSize=16", "/usr/local/bin/login.sh"]
