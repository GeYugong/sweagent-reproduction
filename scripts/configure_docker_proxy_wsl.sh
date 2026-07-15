#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must run as root." >&2
  exit 1
fi

proxy_url="${1:-http://127.0.0.1:10808}"
no_proxy="localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

install -m 0755 -d /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/http-proxy.conf <<EOF
[Service]
Environment="HTTP_PROXY=${proxy_url}"
Environment="HTTPS_PROXY=${proxy_url}"
Environment="NO_PROXY=${no_proxy}"
EOF

systemctl daemon-reload
systemctl restart docker
systemctl show docker --property=Environment
docker pull hello-world:latest
docker run --rm hello-world
