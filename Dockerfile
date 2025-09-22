FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем папку для статических файлов если ее нет
RUN mkdir -p static

EXPOSE 5000

CMD ["python", "main.py"]