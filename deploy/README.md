# EC2 Deployment Guide — GRC RAG Governance Assistant

Deploy the GRC RAG assistant to an AWS EC2 **t2.micro** (free tier) instance with
**Google Gemini** as the LLM and your existing **S3 bucket** for document storage.

**Estimated time:** ~2 hours  
**Cost:** $0 (free tier for 12 months)

---

## Prerequisites

Before starting, make sure you have:

- [ ] AWS account with MFA enabled
- [ ] AWS Budget alert set ($5–$10/month)
- [ ] S3 bucket created with your GRC PDFs uploaded
- [ ] Google Gemini API key (free at https://aistudio.google.com/app/apikey)
- [ ] Your repo pushed to GitHub

---

## Step 1 — Launch EC2 Instance

1. Open **AWS Console → EC2 → Launch Instance**
2. Use these settings:

| Setting | Value |
|---|---|
| **Name** | `grc-rag-assistant` |
| **AMI** | Amazon Linux 2023 (free tier eligible) |
| **Instance type** | `t2.micro` ✅ Free tier |
| **Key pair** | Create new → download `.pem` file → save it safely |
| **Network** | Default VPC, default subnet |
| **Auto-assign public IP** | Enable |
| **Storage** | 8 GB gp3 (default) |

3. Click **Launch Instance**

---

## Step 2 — Configure Security Group (Firewall)

After launching, find your instance → **Security** tab → click the Security Group → **Edit inbound rules**:

| Type | Protocol | Port | Source | Why |
|---|---|---|---|---|
| SSH | TCP | 22 | My IP | SSH access |
| Custom TCP | TCP | 8000 | 0.0.0.0/0 | FastAPI backend |
| Custom TCP | TCP | 8501 | 0.0.0.0/0 | Streamlit UI |

---

## Step 3 — Attach IAM Role for S3 Access

Your EC2 instance needs permission to read/write your S3 bucket.

1. **IAM → Roles → Create role**
2. **Trusted entity:** EC2
3. **Policy:** Create inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::YOUR-BUCKET-NAME",
        "arn:aws:s3:::YOUR-BUCKET-NAME/*"
      ]
    }
  ]
}
```

4. Name the role `grc-rag-ec2-role`
5. **EC2 → Your instance → Actions → Security → Modify IAM role → Select `grc-rag-ec2-role`**

---

## Step 4 — SSH Into the Instance

```powershell
# Windows PowerShell (replace YOUR_KEY.pem and YOUR_EC2_IP)
ssh -i "C:\path\to\YOUR_KEY.pem" ec2-user@YOUR_EC2_PUBLIC_IP

# First time: accept fingerprint with 'yes'
```

> **Tip:** Find your Public IP in EC2 → Instances → your instance → Public IPv4 address

---

## Step 5 — Run the Setup Script

Once logged in via SSH:

```bash
# Clone just the setup script first
curl -o setup_ec2.sh \
  https://raw.githubusercontent.com/YOUR_USERNAME/docuchat-rag/main/deploy/setup_ec2.sh

# Make it executable and run it
chmod +x setup_ec2.sh
./setup_ec2.sh
```

> **Note:** Edit `REPO_URL` in `setup_ec2.sh` first to point to your GitHub repo.

---

## Step 6 — Configure Environment Variables

```bash
nano /home/ec2-user/docuchat-rag/.env
```

Fill in these values (everything else can stay as default):

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-1.5-flash

AWS_REGION=us-east-1
S3_BUCKET=your-s3-bucket-name-here
S3_PREFIX=grc-docs/

DEBUG=false
```

Save and exit (`Ctrl+X → Y → Enter`)

---

## Step 7 — Restart Services

```bash
sudo systemctl restart docuchat-api docuchat-ui

# Verify both are running
sudo systemctl status docuchat-api
sudo systemctl status docuchat-ui
```

Check the API is working:

```bash
curl http://localhost:8000/api/health
# Expected: {"status":"healthy","version":"0.1.0"}
```

---

## Step 8 — Create GRC Project and Sync Documents from S3

```bash
cd /home/ec2-user/docuchat-rag
source .venv/bin/activate

# 1. Create the GRC project
PROJECT_ID=$(curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GRC Knowledge Assistant",
    "description": "RAG assistant for AI governance, risk, compliance and cloud security.",
    "system_prompt": "You are a GRC and cloud security expert. Answer only from the provided documents. Always cite your sources. If the answer is not in the documents, say you do not know.",
    "top_k": 5
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Project ID: $PROJECT_ID"

# 2. Sync all PDFs from S3 into the project
python scripts/sync_from_s3.py --project-id "$PROJECT_ID"
```

---

## Step 9 — Open the App in Your Browser

```
http://YOUR_EC2_PUBLIC_IP:8501
```

Test with a GRC question:
> *"What does the NIST framework say about risk assessment?"*

You should get an answer with citations showing which PDF and chunk it came from.

---

## Optional — Assign a Static IP (Elastic IP)

By default, EC2 public IPs change when you stop/start the instance.

To get a permanent IP:
1. **EC2 → Elastic IPs → Allocate Elastic IP**
2. **Associate** it with your instance

This is **free** as long as it stays attached to a running instance.

---

## Useful Commands

```bash
# View API logs live
sudo journalctl -u docuchat-api -f

# View UI logs live
sudo journalctl -u docuchat-ui -f

# Restart after code changes
cd /home/ec2-user/docuchat-rag
git pull
sudo systemctl restart docuchat-api docuchat-ui

# Stop to save free-tier hours (when not using)
# Do this from AWS Console: EC2 → Instance → Stop
```

---

## Cost Summary

| Service | Usage | Cost |
|---|---|---|
| EC2 t2.micro | 750 hrs/month | **$0** (free tier 12 months) |
| S3 storage | 19 PDFs ~40MB | **$0** (5GB free) |
| Gemini API | ~1,500 req/day | **$0** (free tier) |
| Elastic IP | Attached to instance | **$0** |
| **Total** | | **$0/month** |

> ⚠️ Stop your instance when not using it to conserve free-tier hours.
