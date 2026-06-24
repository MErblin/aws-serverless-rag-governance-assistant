#!/bin/bash
# =============================================================================
# setup_ec2.sh — Bootstrap script for EC2 t2.micro (Amazon Linux 2023)
#
# Run this ONCE after launching your EC2 instance:
#   chmod +x setup_ec2.sh
#   ./setup_ec2.sh
#
# What it does:
#   1. Installs Python 3.11, git, pip
#   2. Clones your repo
#   3. Creates a virtual environment and installs dependencies
#   4. Copies systemd service files for auto-start
#   5. Opens firewall ports 8000 (API) and 8501 (Streamlit)
# =============================================================================

set -e  # stop on any error

REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/docuchat-rag.git"
APP_DIR="/home/ec2-user/docuchat-rag"
VENV_DIR="$APP_DIR/.venv"

echo "======================================================"
echo "  GRC RAG Governance Assistant — EC2 Setup"
echo "======================================================"

# ── 1. System packages ────────────────────────────────────────────────────────
echo ""
echo "[1/6] Installing system packages..."
sudo dnf update -y
sudo dnf install -y git python3.11 python3.11-pip python3.11-devel gcc

# ── 2. Clone repo ─────────────────────────────────────────────────────────────
echo ""
echo "[2/6] Cloning repository..."
if [ -d "$APP_DIR" ]; then
    echo "  Directory exists — pulling latest changes..."
    cd "$APP_DIR" && git pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi

# ── 3. Virtual environment + dependencies ────────────────────────────────────
echo ""
echo "[3/6] Setting up Python environment..."
cd "$APP_DIR"
python3.11 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

# ── 4. Create .env from template (only if not already present) ───────────────
echo ""
echo "[4/6] Setting up environment file..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo ""
    echo "  ⚠️  IMPORTANT: Edit $APP_DIR/.env and fill in:"
    echo "      GEMINI_API_KEY=your-key-here"
    echo "      S3_BUCKET=your-bucket-name"
    echo ""
else
    echo "  .env already exists — skipping."
fi

# ── 5. Install systemd services ───────────────────────────────────────────────
echo ""
echo "[5/6] Installing systemd services..."
sudo cp "$APP_DIR/deploy/docuchat-api.service" /etc/systemd/system/
sudo cp "$APP_DIR/deploy/docuchat-ui.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable docuchat-api docuchat-ui
sudo systemctl start docuchat-api docuchat-ui

# ── 6. Data directories ───────────────────────────────────────────────────────
echo ""
echo "[6/6] Creating data directories..."
mkdir -p "$APP_DIR/data/projects"
mkdir -p "$APP_DIR/data/chroma"

echo ""
echo "======================================================"
echo "  Setup complete!"
echo ""
echo "  Check service status:"
echo "    sudo systemctl status docuchat-api"
echo "    sudo systemctl status docuchat-ui"
echo ""
echo "  View logs:"
echo "    sudo journalctl -u docuchat-api -f"
echo "    sudo journalctl -u docuchat-ui -f"
echo ""
echo "  Next: Edit /home/ec2-user/docuchat-rag/.env"
echo "        then: sudo systemctl restart docuchat-api docuchat-ui"
echo "======================================================"
