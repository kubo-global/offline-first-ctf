FROM python:3.12-slim
WORKDIR /app
COPY app.py .
EXPOSE 8081
# run as a non-root user; the app needs nothing but a port
RUN useradd -m runner
USER runner
CMD ["python", "app.py"]
