FROM python:3.10-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота
COPY . .

# Команда запуска (замени main.py на твой главный файл)
CMD ["python", "main.py"]