#!/bin/bash
set -e

VM_IP="101.53.137.55"
VM_USER="root"
REPO_URL="https://github.com/namm9an/Vault.git"
APP_DIR="/opt/vault"

echo "==> Deploying Vault to $VM_IP..."

ssh -o StrictHostKeyChecking=no $VM_USER@$VM_IP bash -s << 'REMOTE'
set -e

# Install Docker if not present
if ! command -v docker &>/dev/null; then
  echo "==> Installing Docker..."
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  echo "==> Docker installed."
else
  echo "==> Docker already installed."
fi

# Clone or update repo
if [ -d /opt/vault/.git ]; then
  echo "==> Updating existing repo..."
  cd /opt/vault && git pull origin main
else
  echo "==> Cloning repo..."
  git clone https://github.com/namm9an/Vault.git /opt/vault
fi

cd /opt/vault

# Copy prod env
cp .env.prod .env

echo "==> Building and starting containers..."
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

echo "==> Waiting for services to be healthy..."
sleep 10
docker compose -f docker-compose.prod.yml ps

echo ""
echo "==> Vault is live at http://101.53.140.68"
REMOTE
