FROM python:3.10-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY database /app/database

WORKDIR /app/backend
EXPOSE 5000

CMD ["python", "app.py"]
