#!/usr/bin/env python3
"""Run on EC2: creates the GRC project and syncs all PDFs from S3."""
import json, subprocess, sys
import urllib.request

API = "http://localhost:8000/api"

# Create project
body = json.dumps({
    "name": "GRC Knowledge Assistant",
    "description": "RAG assistant for AI governance, risk, compliance and cloud security.",
    "system_prompt": "You are a GRC and cloud security expert. Answer only from the provided documents. Always cite your sources. If the answer is not in the documents, say you do not know.",
    "top_k": 5,
}).encode()

req = urllib.request.Request(
    f"{API}/projects",
    data=body,
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
project = json.loads(resp.read())
project_id = project["id"]
print(f"Project created: {project_id}")

# Run sync script
result = subprocess.run(
    [sys.executable, "scripts/sync_from_s3.py", "--project-id", project_id],
    cwd="/home/ec2-user/docuchat-rag",
)
sys.exit(result.returncode)
