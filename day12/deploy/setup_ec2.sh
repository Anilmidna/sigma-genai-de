#!/bin/bash
# =============================================================================
# SIGMA DATATECH — EC2 SETUP SCRIPT
# =============================================================================
# Run this ONCE on a fresh EC2 instance (Amazon Linux 2023 or Ubuntu 22.04)
# Either paste as EC2 User Data OR run manually after SSH-ing in:
#   chmod +x setup_ec2.sh && sudo ./setup_ec2.sh
#
# What this does:
#   1. Installs Python 3.11, pip, git
#   2. Installs all Python packages (FastAPI, uvicorn, boto3, chromadb, mcp...)
#   3. Creates the platform directory structure
#   4. Installs systemd services for all 5 agents
#   5. Opens required ports in the OS firewall
# =============================================================================

set -e  # Exit on any error

echo "============================================================"
echo "SIGMA INTELLIGENCE PLATFORM — EC2 SETUP"
echo "============================================================"

# ── Detect OS ─────────────────────────────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    OS="unknown"
fi

echo "[1/6] Installing system packages..."
if [ "$OS" = "amzn" ] || [ "$OS" = "rhel" ]; then
    dnf update -y -q
    dnf install -y python3.11 python3.11-pip git htop -q
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
    alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1
    USER_HOME="/home/ec2-user"
    PLATFORM_USER="ec2-user"
elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    apt-get update -q
    apt-get install -y python3.11 python3-pip python3.11-venv git htop -q
    USER_HOME="/home/ubuntu"
    PLATFORM_USER="ubuntu"
else
    echo "[WARN] Unknown OS. Assuming Amazon Linux."
    USER_HOME="/home/ec2-user"
    PLATFORM_USER="ec2-user"
fi

echo "[2/6] Installing Python packages..."
pip3 install --quiet \
    fastapi \
    uvicorn[standard] \
    httpx \
    boto3 \
    pandas \
    great_expectations \
    chromadb \
    sentence-transformers \
    mcp[cli] \
    faker \
    python-dotenv \
    pydantic

echo "[3/6] Creating platform directory..."
PLATFORM_DIR="$USER_HOME/sigma-platform"
mkdir -p $PLATFORM_DIR/lab/agents
mkdir -p $PLATFORM_DIR/lab/agent_outputs
mkdir -p $PLATFORM_DIR/lab/agent_memory
mkdir -p $PLATFORM_DIR/lab/ge_suites
mkdir -p $PLATFORM_DIR/deploy/systemd
mkdir -p $PLATFORM_DIR/logs
chown -R $PLATFORM_USER:$PLATFORM_USER $PLATFORM_DIR

echo "[4/6] Creating environment file..."
cat > $PLATFORM_DIR/.env << 'ENVEOF'
# Edit these values before starting services
AWS_DEFAULT_REGION=us-east-1
SIGMA_S3_BUCKET=sigma-datatech-YOURTEAM
SIGMA_STREAM=sigma-transactions
SNOWFLAKE_ACCOUNT=your-account
SNOWFLAKE_USER=your-user
SNOWFLAKE_PASSWORD=your-password
SNOWFLAKE_DATABASE=SIGMA
SNOWFLAKE_WAREHOUSE=SIGMA_WH
PLATFORM_DIR=/home/ec2-user/sigma-platform
ENVEOF

chown $PLATFORM_USER:$PLATFORM_USER $PLATFORM_DIR/.env
echo "[INFO] Edit $PLATFORM_DIR/.env with your credentials before starting services"

echo "[5/6] Installing systemd services..."
# Copy service files if they exist
for svc in sigma-supervisor sigma-schema-agent sigma-pii-agent sigma-quality-agent sigma-mcp-server; do
    if [ -f "$PLATFORM_DIR/deploy/systemd/${svc}.service" ]; then
        cp "$PLATFORM_DIR/deploy/systemd/${svc}.service" /etc/systemd/system/
    fi
done
systemctl daemon-reload

echo "[6/6] Configuring firewall..."
# Allow ports 8001-8005 (agent ports) — restrict to team IP in production
if command -v firewall-cmd &> /dev/null; then
    for port in 8001 8002 8003 8004 8005; do
        firewall-cmd --permanent --add-port=${port}/tcp 2>/dev/null || true
    done
    firewall-cmd --reload 2>/dev/null || true
fi

echo ""
echo "============================================================"
echo "SETUP COMPLETE"
echo "============================================================"
echo ""
echo "NEXT STEPS:"
echo "  1. Edit credentials:  nano $PLATFORM_DIR/.env"
echo "  2. Deploy code:       ./deploy.sh <ec2-ip> <key.pem>"
echo "  3. Start services:    sudo systemctl start sigma-supervisor"
echo "  4. Watch logs:        journalctl -u sigma-supervisor -f"
echo ""
echo "  EC2 Security Group must allow inbound TCP 8001-8005 from your IP"
echo "============================================================"
