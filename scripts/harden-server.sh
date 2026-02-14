#!/bin/bash
# =============================================================================
# POS System — Server Hardening Script
# Run once on the DigitalOcean droplet: bash scripts/harden-server.sh
# =============================================================================
set -euo pipefail

echo "=========================================="
echo "POS Server Hardening — $(date)"
echo "=========================================="

# 1. System updates
echo "[1/8] Updating system packages..."
apt update && apt upgrade -y

# 2. Automatic security updates
echo "[2/8] Configuring automatic security updates..."
apt install -y unattended-upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades << 'AUTOEOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
AUTOEOF

cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'UUEOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
UUEOF

# 3. SSH hardening
echo "[3/8] Hardening SSH..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/' /etc/ssh/sshd_config
sed -i 's/^#\?LoginGraceTime.*/LoginGraceTime 30/' /etc/ssh/sshd_config
sed -i 's/^#\?X11Forwarding.*/X11Forwarding no/' /etc/ssh/sshd_config
sed -i 's/^#\?AllowTcpForwarding.*/AllowTcpForwarding no/' /etc/ssh/sshd_config
sed -i 's/^#\?AllowAgentForwarding.*/AllowAgentForwarding no/' /etc/ssh/sshd_config
systemctl restart sshd

# 4. UFW Firewall
echo "[4/8] Configuring UFW firewall..."
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw limit 22/tcp comment 'SSH rate limit'
ufw allow 80/tcp comment 'HTTP (redirect + ACME)'
ufw allow 443/tcp comment 'HTTPS'
echo "y" | ufw enable

# 5. fail2ban
echo "[5/8] Installing and configuring fail2ban..."
apt install -y fail2ban
cat > /etc/fail2ban/jail.local << 'F2BEOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
backend = systemd

[sshd]
enabled = true
port = ssh
maxretry = 3
bantime = 3600

[nginx-limit-req]
enabled = true
port = http,https
filter = nginx-limit-req
logpath = /var/lib/docker/containers/*/*.log
maxretry = 10
findtime = 120
bantime = 600

[nginx-scanner]
enabled = true
port = http,https
filter = nginx-scanner
logpath = /var/lib/docker/containers/*/*.log
maxretry = 3
findtime = 60
bantime = 86400

[recidive]
enabled = true
bantime = 604800
findtime = 86400
maxretry = 3
F2BEOF

# Create nginx scanner filter
cat > /etc/fail2ban/filter.d/nginx-scanner.conf << 'SCANEOF'
[Definition]
failregex = ^.*"(GET|POST|HEAD) .*(\.php|\.asp|\.env|wp-login|wp-admin|phpmyadmin|xmlrpc|/shell|/cmd|/eval|/setup|/config).*" (404|444|403).*$
ignoreregex =
SCANEOF

systemctl enable fail2ban
systemctl restart fail2ban

# 6. Sysctl hardening
echo "[6/8] Applying sysctl hardening..."
cat > /etc/sysctl.d/99-hardening.conf << 'SYSEOF'
# SYN flood protection
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2

# Anti-spoofing
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# No ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0

# No source routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0

# Ignore ping broadcasts
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Disable IPv6 (not needed)
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
SYSEOF
sysctl --system > /dev/null 2>&1

# 7. Core dump restriction
echo "[7/8] Restricting core dumps..."
echo "* hard core 0" >> /etc/security/limits.conf
echo "fs.suid_dumpable = 0" >> /etc/sysctl.d/99-hardening.conf
sysctl -p /etc/sysctl.d/99-hardening.conf > /dev/null 2>&1

# 8. Docker log limits (global default)
echo "[8/8] Setting Docker log limits..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'DKEOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
DKEOF
systemctl restart docker

echo ""
echo "=========================================="
echo "Hardening complete!"
echo "=========================================="
echo "UFW status:"
ufw status numbered
echo ""
echo "fail2ban status:"
fail2ban-client status
echo ""
echo "IMPORTANT: Test SSH in a NEW terminal before closing this session!"
echo "  ssh root@$(curl -s ifconfig.me)"
echo "=========================================="
