#!/usr/bin/env bash
# 하둡 노드 세팅. 두 서버에서 같은 스크립트를 돌린다. 여러 번 실행해도 안전하다.
# 포맷·기동은 하지 않는다 (README 참고).
#   sudo bash infra/hadoop/setup-node.sh
set -euo pipefail

HADOOP_VERSION=3.3.6
MASTER_IP=172.26.6.113
WORKER1_IP=172.26.13.212

HADOOP_HOME=/opt/hadoop
DATA_DIR=/opt/hadoop-data
CONF_SRC="$(cd "$(dirname "$0")" && pwd)/conf"

log() { echo -e "\n\033[1;36m[hadoop] $*\033[0m"; }

[ "$(id -u)" = "0" ] || { echo "sudo 로 실행하세요."; exit 1; }

log "Java 11"
if ! [ -d /usr/lib/jvm/java-11-openjdk-amd64 ]; then
    apt-get update -qq
    apt-get install -y --no-install-recommends openjdk-11-jdk-headless curl
fi
echo "  $(/usr/lib/jvm/java-11-openjdk-amd64/bin/java -version 2>&1 | head -1)"

log "/etc/hosts 별칭"
for entry in "$MASTER_IP ha-master" "$WORKER1_IP ha-worker1"; do
    name=${entry##* }
    sed -i "/[[:space:]]$name\$/d" /etc/hosts
    echo "$entry" >> /etc/hosts
    echo "  $entry"
done

log "Hadoop $HADOOP_VERSION"
if [ -d "/opt/hadoop-$HADOOP_VERSION" ]; then
    echo "  이미 설치됨"
else
    TARBALL="hadoop-$HADOOP_VERSION.tar.gz"
    BASE="https://dlcdn.apache.org/hadoop/common/hadoop-$HADOOP_VERSION"
    ARCHIVE="https://archive.apache.org/dist/hadoop/common/hadoop-$HADOOP_VERSION"

    cd /tmp
    curl -fsSLO "$BASE/$TARBALL" || curl -fsSLO "$ARCHIVE/$TARBALL"
    curl -fsSLO "$BASE/$TARBALL.sha512" || curl -fsSLO "$ARCHIVE/$TARBALL.sha512"

    expected=$(grep -oE '[0-9a-fA-F]{128}' "$TARBALL.sha512" | head -1 | tr 'A-F' 'a-f')
    actual=$(sha512sum "$TARBALL" | cut -d' ' -f1)
    [ "$expected" = "$actual" ] || { echo "체크섬 불일치. 설치를 중단합니다."; exit 1; }
    echo "  체크섬 OK"

    tar -xzf "$TARBALL" -C /opt
    rm -f "$TARBALL" "$TARBALL.sha512"
fi
ln -sfn "/opt/hadoop-$HADOOP_VERSION" "$HADOOP_HOME"

log "설정 배치"
install -m 644 "$CONF_SRC"/core-site.xml "$CONF_SRC"/hdfs-site.xml \
               "$CONF_SRC"/yarn-site.xml "$CONF_SRC"/mapred-site.xml \
               "$CONF_SRC"/workers "$HADOOP_HOME/etc/hadoop/"
install -m 644 "$CONF_SRC"/hadoop-env.sh "$HADOOP_HOME/etc/hadoop/hadoop-env.sh"
echo "  $HADOOP_HOME/etc/hadoop/ 에 복사"

mkdir -p "$DATA_DIR"/{nn,dn,tmp,logs}
chown -R ubuntu:ubuntu "$DATA_DIR" "/opt/hadoop-$HADOOP_VERSION"

cat > /etc/profile.d/hadoop.sh <<'EOF'
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/opt/hadoop
export HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
EOF
chmod 644 /etc/profile.d/hadoop.sh

log "완료"
echo "  Hadoop   $HADOOP_HOME -> /opt/hadoop-$HADOOP_VERSION"
echo "  데이터   $DATA_DIR"
echo "  환경변수 /etc/profile.d/hadoop.sh (재로그인 후 적용)"
