import subprocess

logs = subprocess.run(
    ["docker", "logs", "aureus-signal"],
    capture_output=True, text=True
)

log_text = logs.stdout + logs.stderr

print("Checking for raw or parsed debug messages:")
lines = [l for l in log_text.split('\n') if "raw message:" in l or "parsed command" in l or "command worker" in l.lower() or "received recovery" in l.lower()]
print(f"Found {len(lines)} lines:")
for l in lines[:20]:
    print("  " + l)
