FROM python:3.12-slim

# FFmpeg kur (muzik sistemi icin)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Calisma dizini
WORKDIR /app

# Veri dizini (volume mount icin)
RUN mkdir -p /app/data

# Bagimliliklar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalari
COPY . .

# Veri dizini (Railway volume mount edilirse /app/data kullanilir)
ENV DATA_DIR=/app/data

# Port
EXPOSE 8000

# Headless baslatici
CMD ["python", "bot_headless.py"]
