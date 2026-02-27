FROM python:3.10-slim
RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота
COPY . .

# Команда запуска (замени main.py на твой главный файл)
CMD ["python", "main.py"]