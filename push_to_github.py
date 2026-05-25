#!/usr/bin/env python3
"""Push github_actions code to GitHub repo via API"""
import os, base64, requests

TOKEN = "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"
BASE_DIR = r"E:\WorkBuddy\touzi\github_actions"
REPO = "yyh200/ajin-push"
API_BASE = f"https://api.github.com/repos/{REPO}/contents"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

SKIP_DIRS = {"__pycache__"}

files = []
for root, dirs, fnames in os.walk(BASE_DIR):
    # Skip __pycache__
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in fnames:
        full = os.path.join(root, fname)
        rel = os.path.relpath(full, BASE_DIR).replace("\\", "/")
        with open(full, "rb") as fh:
            content = fh.read()
        files.append((rel, content))

print(f"Total files: {len(files)}")

for path, content in files:
    url = f"{API_BASE}/{path}"
    payload = {
        "message": f"Add {path}",
        "content": base64.b64encode(content).decode("utf-8"),
    }
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        print(f"  [{resp.status_code}] {path}")
    elif resp.status_code == 422:
        print(f"  [⚠️ 422] {path} (may already exist)")
    else:
        print(f"  [❌ {resp.status_code}] {path}: {resp.text[:120]}")

print("Done!")
