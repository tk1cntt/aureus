import subprocess
import json

# Dump docker logs
cmd = ["wsl", "-d", "Aureus", "-e", "bash", "-lc", "docker logs --tail 200 aureus-gateway-dev"]
res = subprocess.run(cmd, capture_output=True, text=True)

for line in res.stderr.split('\n'):
    if "published to aureus:mt5:events" in line:
        try:
            # find the opening brace
            idx = line.find('{')
            if idx != -1:
                event_str = line[idx:].strip()
                # Some logs have color codes or garbage at the end, so let's try to parse
                # Just print it for now
                print(event_str.replace("'", '"'))
        except Exception as e:
            print("Err:", e)
