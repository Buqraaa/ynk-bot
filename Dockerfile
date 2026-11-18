FROM python:3.12-slim

# FFmpeg kur (muzik sistemi icin)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Calisma dizini
WORKDIR /app

# Bagimliliklar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalari
COPY . .

# Port
EXPOSE 8000

# Headless baslatici
CMD ["python", "bot_headless.py"]
