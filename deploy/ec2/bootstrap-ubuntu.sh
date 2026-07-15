#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script with sudo: sudo ./bootstrap-ubuntu.sh" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "Unsupported system: /etc/os-release is missing." >&2
  exit 1
fi

. /etc/os-release
if [[ ${ID:-} != "ubuntu" ]]; then
  echo "This bootstrap script currently supports Ubuntu only." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl gnupg git jq unzip

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

ARCH=$(dpkg --print-architecture)
CODENAME=${VERSION_CODENAME}
echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

case "$(uname -m)" in
  x86_64) aws_arch=x86_64 ;;
  aarch64|arm64) aws_arch=aarch64 ;;
  *) echo "Skipping AWS CLI installation on unsupported architecture $(uname -m)."; aws_arch= ;;
esac

if [[ -n ${aws_arch} ]] && ! command -v aws >/dev/null 2>&1; then
  tmp_dir=$(mktemp -d)
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${aws_arch}.zip" \
    -o "${tmp_dir}/awscliv2.zip"
  unzip -q "${tmp_dir}/awscliv2.zip" -d "${tmp_dir}"
  "${tmp_dir}/aws/install"
  rm -rf "${tmp_dir}"
fi

systemctl enable --now docker

TARGET_USER=${SUDO_USER:-ubuntu}
if id "${TARGET_USER}" >/dev/null 2>&1; then
  usermod -aG docker "${TARGET_USER}"
fi

install -d -o "${TARGET_USER}" -g "${TARGET_USER}" /opt/insightguide

echo
echo "EC2 bootstrap completed."
echo "1. Sign out and back in so Docker group membership takes effect."
echo "2. Copy or clone the repository into /opt/insightguide."
echo "3. Configure deploy/ec2/.env, then run deploy/ec2/deploy.sh."
