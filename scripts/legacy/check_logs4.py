import subprocess

logs = subprocess.run(
    ["docker", "logs", "aureus-signal"],
    capture_output=True, text=True
)

log_text = logs.stdout + logs.stderr

lines = [l for l in log_text.split('\n') if "API sync request flag" in l or "FULL recalculation" in l.lower()]
print(f"Found {len(lines)} explicit debug lines:")
for l in lines[-10:]:
    print("  " + l)
