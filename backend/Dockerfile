FROM python:3.10-slim

# Cài đặt các package hệ thống cho Unstructured PDF parsing
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    libmagic-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Mặc định chạy API, lệnh này sẽ bị ghi đè trong docker-compose cho service worker
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
