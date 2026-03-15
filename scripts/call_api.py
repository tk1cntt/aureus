import urllib.request
import json
import time

url = 'http://localhost:8001/api/v1/backtest/XAUUSD/sync'
data = json.dumps({'start': '2026-02-25', 'end': '2026-03-01'}).encode('utf-8')
headers = {'Content-Type': 'application/json'}

print(f"Calling {url}...")
req = urllib.request.Request(url, data=data, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        print("Response Code:", response.getcode())
        print("Response Body:", response.read().decode('utf-8'))
except Exception as e:
    print("Error:", e)
