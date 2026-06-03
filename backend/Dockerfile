FROM python:3.13-slim

# C 컴파일러 (greenlet 등 일부 패키지 빌드용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# --prefer-binary: 바이너리 휠 우선 사용 → tokenizers/onnxruntime 등 컴파일 불필요
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
