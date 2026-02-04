from pathlib import Path
import os

env_path = Path(".env")
print(f"Reading from: {env_path.resolve()}")
print(f"File exists: {env_path.exists()}")
print()

# Read the file
content = env_path.read_text(encoding="utf-8")
print("File content (first 500 chars):")
print(repr(content[:500]))
print()

# Parse it the way worker.py does
for i, line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), 1):
    line_stripped = line.strip()
    if not line_stripped or line_stripped.startswith("#"):
        continue
    if line_stripped.startswith("export "):
        line_stripped = line_stripped[len("export "):].strip()
    if "=" not in line_stripped:
        continue
    key, value = line_stripped.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    print(f"Line {i}: key='{key}' value='{value}'")
    os.environ[key] = value

print()
print(f"After loading, SMTP_HOST = {os.environ.get('SMTP_HOST', 'NOT SET')}")
