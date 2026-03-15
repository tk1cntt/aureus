import urllib.request
import json
try:
    with urllib.request.urlopen("http://host.docker.internal:8000/v1/models") as response:
        text = response.read().decode()
        data = json.loads(text)
        models = [m['id'] for m in data.get('data', [])]
        print(f"✅ Available Models: {models}")
except Exception as e:
    print(f"❌ Error during model discovery: {e}")
