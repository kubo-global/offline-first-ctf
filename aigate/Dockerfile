# The AI helper (gate.py) and the boxes' allowlist proxy (boxproxy.py): Python standard
# library only, so nothing to install. Same base as the web challenge, so one download.
FROM python:3.12-slim
WORKDIR /app
COPY gate.py boxproxy.py chat.html ./
RUN useradd -m -u 1500 runner && mkdir -p /data && chown runner /data
USER runner
EXPOSE 8083 3128
CMD ["python", "-u", "gate.py"]
