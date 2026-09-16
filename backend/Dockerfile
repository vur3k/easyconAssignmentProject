FROM python:3.12-slim

WORKDIR /app

# Nainstaluj dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Zkopíruj kód
COPY . .

# Exponuj port
EXPOSE 8000

# Spusť Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
