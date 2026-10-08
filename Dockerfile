FROM python:3.14-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
# Apply available OS security updates even when the base image is digest-pinned.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home-dir /app app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --upgrade pip==26.2.1 && pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY src/features.py src/__init__.py src/
COPY config.py .
COPY web/ web/
COPY models/credit_model.joblib models/metadata.json models/manifest.json models/
RUN test -f models/manifest.json && test -f models/credit_model.joblib && test -f models/metadata.json
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=20s --start-period=60s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/ready',timeout=15)"
# Disable implicit trust of forwarded headers; application trusts only explicit CIDRs.
CMD ["sh","-c","exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers --limit-concurrency 64 --timeout-keep-alive 5"]
