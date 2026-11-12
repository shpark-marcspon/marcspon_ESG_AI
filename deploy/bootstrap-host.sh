#!/usr/bin/env bash
# 새 서버(Ubuntu 24.04 arm64)를 한 번 준비한다(밴드 DP1). 도는 자리: 서버, root 로(sudo). 두 번 돌려도 같다.
#   사용: sudo bash bootstrap-host.sh [ROOT]  (ship.sh 전이라 운영 기계에서 scp 로 올리거나 ssh … 'sudo bash -s' < deploy/bootstrap-host.sh)
#   ROOT 는 /srv/esg-demo(기본, 첫 벌) 또는 /srv/esg-demo2(둘째 벌 — 데모 고정판, 밴드 DM1). 둘째 벌은 그 뿌리의 폴더와
#     그 뿌리의 백업 cron 한 줄(15분 늦게 — 두 덤프가 겹치지 않게)만 더 단다. 도커·사용자·스왑·로그 상한은 이미 있으면 그대로.
# 하는 것: Docker 공식 apt 저장소로 Engine + compose 플러그인 · 배포 사용자 deploy(docker 그룹, ubuntu 의 SSH 키를 받음)
#   · /srv/esg-demo/{releases,shared,backup}(deploy 소유, shared·backup 700) · 스왑 2 GiB(서버에서 이미지 빌드 여유 — 어림)
#   · unattended-upgrades · /etc/docker/daemon.json 로그 상한(json-file 20m × 5 — 30 GiB 디스크) · deploy 의 cron(백업).
# 지우는 것 0. 찍는 것: 설치한 판.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "root 로 돈다(sudo)" >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
ROOT="${1:-/srv/esg-demo}"
case "$ROOT" in
  /srv/esg-demo) cron_min=30 ;;
  /srv/esg-demo2) cron_min=45 ;;
  *) echo "ROOT 는 /srv/esg-demo · /srv/esg-demo2 뿐이다: $ROOT" >&2; exit 2 ;;
esac

# ── Docker(공식 저장소 — https://docs.docker.com/engine/install/ubuntu/) ──
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  apt-get update -q
  apt-get install -y -q ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
apt-get install -y -q unattended-upgrades cron dnsutils >/dev/null

# ── 도커 로그 상한(바꾸면 도커를 다시 띄운다 — 처음 한 번만 바뀐다) ──
want='{ "log-driver": "json-file", "log-opts": { "max-size": "20m", "max-file": "5" } }'
if [ "$(cat /etc/docker/daemon.json 2>/dev/null || true)" != "$want" ]; then
  echo "$want" > /etc/docker/daemon.json
  systemctl restart docker
fi
systemctl enable --now docker >/dev/null

# ── 배포 사용자 ──
id deploy >/dev/null 2>&1 || useradd -m -s /bin/bash deploy
usermod -aG docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
if [ -f /home/ubuntu/.ssh/authorized_keys ] && [ ! -f /home/deploy/.ssh/authorized_keys ]; then
  install -m 600 -o deploy -g deploy /home/ubuntu/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
fi

# ── 폴더 ──
install -d -m 755 -o deploy -g deploy "$ROOT" "$ROOT/releases"
install -d -m 700 -o deploy -g deploy "$ROOT/shared" "$ROOT/backup"

# ── 스왑 2 GiB ──
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  [ -f /swapfile ] || { fallocate -l 2G /swapfile; chmod 600 /swapfile; mkswap /swapfile >/dev/null; }
  swapon /swapfile
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab

# ── 자동 보안 갱신 ──
systemctl enable --now unattended-upgrades >/dev/null

# ── 백업 cron(deploy 사용자). 서버 시계는 UTC — 18:30 UTC = 03:30 KST(첫 벌) · 18:45 UTC = 03:45 KST(둘째 벌) ──
# 둘째 벌 줄은 DEPLOY_ROOT 를 겹쳐 밝힌다(backup-db.sh 도 자기 자리에서 유도하지만 cron 줄만 봐도 벌이 보이게). 찾기는 「<ROOT>/current/deploy/backup-db.sh 」(끝 빈칸)로 —
#   /srv/esg-demo/… 가 /srv/esg-demo2/… 의 앞머리라 빈칸 없이 찾으면 둘째 벌 줄을 첫 벌 줄로 읽는다.
line="$cron_min 18 * * * DEPLOY_ROOT=$ROOT $ROOT/current/deploy/backup-db.sh >> $ROOT/backup/backup.log 2>&1"
[ "$ROOT" != /srv/esg-demo ] || line="30 18 * * * $ROOT/current/deploy/backup-db.sh >> $ROOT/backup/backup.log 2>&1"
if ! crontab -u deploy -l 2>/dev/null | grep -qF "$ROOT/current/deploy/backup-db.sh "; then
  { crontab -u deploy -l 2>/dev/null || true; echo "$line"; } | crontab -u deploy -
fi

echo "docker: $(docker --version)"
echo "compose: $(docker compose version --short)"
echo "swap: $(swapon --show=SIZE --noheadings | head -n 1)"
echo "폴더: $(ls -ld "$ROOT/shared" | awk '{print $1, $3}')"
echo "cron(deploy): $(crontab -u deploy -l | grep -c backup-db.sh) 줄(벌마다 하나)"
