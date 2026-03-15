FROM python:3.11-slim

WORKDIR /app

# No heavy build dependencies needed for pure Python/Pandas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
