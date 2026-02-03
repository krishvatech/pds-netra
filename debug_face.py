
import sys
import os
from pathlib import Path
import traceback

# Setup path
project_root = Path("/Users/krishva/Projects/PDS-Netra-Project/pds-netra")
edge_path = project_root / "pds-netra-edge"
sys.path.append(str(edge_path))

try:
    print("Importing compute_embedding...", flush=True)
    from tools.generate_face_embedding import compute_embedding
    print("Import successful.", flush=True)
    
    image_path = "/home/shruti/.gemini/antigravity/brain/9e1f93e3-7d07-478a-b049-d55be703d998/uploaded_media_1769577881708.png"
    
    print(f"Testing compute_embedding on {image_path}", flush=True)
    embedding = compute_embedding(image_path)
    print(f"Success! Embedding generated. Length: {len(embedding)}", flush=True)
    
except Exception:
    print("Exception occurred:", flush=True)
    traceback.print_exc()
