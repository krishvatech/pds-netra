
import sys
import os
from pathlib import Path

# Simulate the path structure in authorized_users.py
# The file is at pds-netra-backend/app/api/v1/authorized_users.py
# So parents[4] from there would be root pds-netra

# Let's say we are running this script from project root /home/shruti/pds-netra/pds-netra
project_root = Path.cwd()
edge_path = project_root / "pds-netra-edge"

print(f"Edge path: {edge_path}")
if not edge_path.exists():
    print("Edge path does not exist!")
    sys.exit(1)

if str(edge_path) not in sys.path:
    sys.path.append(str(edge_path))

try:
    from tools.generate_face_embedding import compute_embedding
    print("Successfully imported compute_embedding from tools.generate_face_embedding")
except ImportError as e:
    print(f"Failed to import: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Other error: {e}")
    sys.exit(1)
