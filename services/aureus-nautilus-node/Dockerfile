FROM ghcr.io/nautechsystems/nautilus_trader:latest

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "nautilus_runner.py"]
