import subprocess

logs = subprocess.run(
    ["docker", "logs", "aureus-signal"],
    capture_output=True, text=True
)

log_text = logs.stdout + logs.stderr

print("Checking for Recalc progress...")
recalc_lines = [l for l in log_text.split('\n') if "Recalc" in l]
print(f"Found {len(recalc_lines)} recalc lines. Last 5:")
for l in recalc_lines[-5:]:
    print("  " + l)

print("Checking for REQUESTS...")
req_lines = [l for l in log_text.split('\n') if "Received recovery request" in l]
print(f"Found {len(req_lines)} request lines. Last 5:")
for l in req_lines[-5:]:
    print("  " + l)
