FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    -r /app/requirements.txt

COPY synth_engine /app/synth_engine
COPY frontend /app/frontend
COPY configs /app/configs
RUN mkdir -p /app/configs /app/runs

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "synth_engine.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
