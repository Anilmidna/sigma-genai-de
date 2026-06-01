#!/bin/bash
# =============================================================================
# SIGMA DATATECH — DEPLOY SCRIPT
# =============================================================================
# Run from YOUR LAPTOP to push code to EC2 and restart services.
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh <ec2-public-ip> <path-to-key.pem>
#
# Example:
#   ./deploy.sh 54.123.45.67 ~/Downloads/sigma-key.pem
# =============================================================================

set -e

EC2_IP=$1
KEY_FILE=$2

if [ -z "$EC2_IP" ] || [ -z "$KEY_FILE" ]; then
    echo "Usage: ./deploy.sh <ec2-ip> <key.pem>"
    echo "Example: ./deploy.sh 54.123.45.67 ~/sigma-key.pem"
    exit 1
fi

# Auto-detect EC2 user
EC2_USER="ec2-user"
PLATFORM_DIR="/home/$EC2_USER/sigma-platform"
SSH="ssh -i $KEY_FILE -o StrictHostKeyChecking=no $EC2_USER@$EC2_IP"
SCP="scp -i $KEY_FILE -o StrictHostKeyChecking=no"

echo "============================================================"
echo "DEPLOYING TO EC2: $EC2_IP"
echo "============================================================"

# Test connection
echo "[1/4] Testing SSH connection..."
$SSH "echo 'SSH OK'" || {
    echo "[ERROR] Cannot SSH. Check IP, key file, and security group."
    exit 1
}

# Sync code
echo "[2/4] Syncing code to EC2..."
rsync -avz --quiet \
    -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
    --exclude "agent_outputs/" \
    --exclude "agent_memory/" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude ".env" \
    $(dirname $0)/../lab/ \
    $EC2_USER@$EC2_IP:$PLATFORM_DIR/lab/

# Copy systemd service files
echo "[3/4] Installing systemd services..."
rsync -avz --quiet \
    -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
    $(dirname $0)/systemd/ \
    $EC2_USER@$EC2_IP:$PLATFORM_DIR/deploy/systemd/

$SSH "sudo cp $PLATFORM_DIR/deploy/systemd/*.service /etc/systemd/system/ && sudo systemctl daemon-reload"

# Restart services
echo "[4/4] Restarting services..."
$SSH "
    sudo systemctl restart sigma-mcp-server   2>/dev/null || sudo systemctl start sigma-mcp-server
    sleep 2
    sudo systemctl restart sigma-schema-agent  2>/dev/null || sudo systemctl start sigma-schema-agent
    sudo systemctl restart sigma-pii-agent     2>/dev/null || sudo systemctl start sigma-pii-agent
    sudo systemctl restart sigma-quality-agent 2>/dev/null || sudo systemctl start sigma-quality-agent
    sleep 2
    sudo systemctl restart sigma-supervisor    2>/dev/null || sudo systemctl start sigma-supervisor
    sleep 2
    echo '--- Service Status ---'
    sudo systemctl is-active sigma-supervisor sigma-schema-agent sigma-pii-agent sigma-quality-agent sigma-mcp-server
"

echo ""
echo "============================================================"
echo "DEPLOY COMPLETE"
echo "============================================================"
echo ""
echo "  Supervisor  : http://$EC2_IP:8001"
echo "  Schema Agent: http://$EC2_IP:8002"
echo "  PII Agent   : http://$EC2_IP:8003"
echo "  Quality Agent: http://$EC2_IP:8004"
echo "  MCP Server  : http://$EC2_IP:8005"
echo ""
echo "  Watch logs: ssh -i $KEY_FILE $EC2_USER@$EC2_IP"
echo "              journalctl -u sigma-supervisor -f"
echo ""
echo "  Trigger pipeline from laptop:"
echo "              python lab/trigger.py --ec2-ip $EC2_IP --bucket YOUR_BUCKET"
echo "============================================================"
