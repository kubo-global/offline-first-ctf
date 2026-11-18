# syntax=docker/dockerfile:1
# The player box: one per player, reached over SSH through sshpiper.
# The challenge files come from the pack, as the extra build context `pack`
# (see docker-compose.yml), and are baked in. Builds for amd64 and arm64 alike (laptop, Mac with Apple chip, Pi).

# --- the reversing binaries, rebuilt for this machine's architecture ---------------
# The downloads on the CTF site stay the x86-64 originals; inside the box the same
# sources are compiled natively, with the same flags, so they run on an ARM server too.
FROM debian:trixie-slim AS bins
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*
COPY --from=pack . /src
# compile, then delete the sources: they hold the answers, and players only ever get
# the compiled program. The last line fails the build if a source is left behind.
RUN set -e; for c in /src/*/*.c; do \
      d=$(dirname "$c"); b=$(basename "$c" .c); \
      if [ -f "$d/$b" ]; then gcc -O0 -o "$d/$b" "$c"; fi; \
    done; \
    find /src -name '*.c' -delete; \
    ! find /src -name '*.c' | grep -q .

# --- the box ------------------------------------------------------------------------
FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
# man pages are useful here, so keep them (slim images drop them by default; the base
# commands are reinstalled below to get theirs back)
RUN rm -f /etc/dpkg/dpkg.cfg.d/docker /etc/dpkg/dpkg.cfg.d/excludes 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends \
      openssh-server ca-certificates locales-all \
      bash-completion less nano vim-tiny man-db manpages tree jq bc \
      file binutils xxd bsdextrautils coreutils grep sed gawk diffutils findutils \
      tar gzip bzip2 xz-utils zip unzip p7zip-full \
      python3 python3-pil python3-requests \
      curl wget netcat-openbsd sqlite3 \
      libimage-exiftool-perl poppler-utils binwalk foremost pngcheck zbar-tools \
      steghide imagemagick sox multimon-ng \
      tshark \
      gdb ltrace strace \
      ruby \
 && apt-get install -y --no-install-recommends --reinstall coreutils grep sed tar gzip findutils diffutils bash \
 && gem install --no-document zsteg \
 && rm -rf /var/lib/apt/lists/* \
 && mandb -q || true

# challenge files, read-only master copy; each player gets their own copy on first start
COPY --from=bins /src /opt/challenges
RUN chmod -R a+rX /opt/challenges

COPY sshd_config /etc/ssh/sshd_config.d/ctf.conf
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
COPY ctf-help /usr/local/bin/ctf-help
COPY motd.sh /usr/local/sbin/motd.sh
COPY ai /usr/local/bin/ai
# The box network has no route out. Web tools go through the room's allowlist proxy,
# which reaches only the game, the tutorials, the web challenges and the AI helper.
# /etc/environment is read for every SSH login (pam_env), profile.d for other shells.
RUN printf '%s\n' http_proxy=http://boxproxy:3128 HTTP_PROXY=http://boxproxy:3128 \
      no_proxy=localhost,127.0.0.1 NO_PROXY=localhost,127.0.0.1 >> /etc/environment \
 && sed 's/^/export /' /etc/environment | grep -i proxy > /etc/profile.d/ctf-proxy.sh
# zbarimg tries to reach a desktop message bus that a box does not have; keep it quiet
RUN echo "alias zbarimg='zbarimg --nodbus'" >> /etc/bash.bashrc
RUN chmod 755 /usr/local/sbin/entrypoint.sh /usr/local/bin/ctf-help /usr/local/sbin/motd.sh /usr/local/bin/ai \
 && rm -f /etc/ssh/ssh_host_* /etc/update-motd.d/* /etc/legal \
 && mkdir -p /run/sshd

EXPOSE 22
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]
