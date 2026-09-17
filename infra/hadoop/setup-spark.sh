#!/usr/bin/env bash
# Spark + PySpark 실행 환경. NodeManager 가 있는 노드에서만 돌린다 (현재 ha-master).
# data/requirements.txt 가 바뀌면 다시 실행한다.
#   sudo bash infra/hadoop/setup-spark.sh [requirements.txt 경로]
set -euo pipefail

SPARK_VERSION=3.5.9
SPARK_HOME=/opt/spark
VENV=/opt/venv-data
REQ="${1:-/home/ubuntu/hadoop-setup/requirements.txt}"

log() { echo -e "\n\033[1;36m[spark] $*\033[0m"; }
[ "$(id -u)" = "0" ] || { echo "sudo 로 실행하세요."; exit 1; }

log "Spark $SPARK_VERSION"
if [ -d "/opt/spark-$SPARK_VERSION-bin-hadoop3" ]; then
    echo "  이미 설치됨"
else
    TARBALL="spark-$SPARK_VERSION-bin-hadoop3.tgz"
    BASE="https://dlcdn.apache.org/spark/spark-$SPARK_VERSION"
    ARCHIVE="https://archive.apache.org/dist/spark/spark-$SPARK_VERSION"

    cd /tmp
    curl -fsSLO "$BASE/$TARBALL" || curl -fsSLO "$ARCHIVE/$TARBALL"
    curl -fsSLO "$BASE/$TARBALL.sha512" || curl -fsSLO "$ARCHIVE/$TARBALL.sha512"

    expected=$(grep -oE '[0-9a-fA-F]{128}' "$TARBALL.sha512" | head -1 | tr 'A-F' 'a-f')
    if [ -z "$expected" ]; then
        # 일부 릴리스는 128자를 공백으로 끊어 적는다
        expected=$(tr -d ' \n' < "$TARBALL.sha512" | grep -oiE '[0-9a-f]{128}' | head -1 | tr 'A-F' 'a-f')
    fi
    actual=$(sha512sum "$TARBALL" | cut -d' ' -f1)
    [ "$expected" = "$actual" ] || { echo "체크섬 불일치. 설치를 중단합니다."; exit 1; }
    echo "  체크섬 OK"

    tar -xzf "$TARBALL" -C /opt
    rm -f "$TARBALL" "$TARBALL.sha512"
fi
ln -sfn "/opt/spark-$SPARK_VERSION-bin-hadoop3" "$SPARK_HOME"

log "파이썬 의존성"
[ -f "$REQ" ] || { echo "$REQ 가 없습니다."; exit 1; }
apt-get install -y --no-install-recommends python3-venv >/dev/null 2>&1 || true
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$REQ"
echo "  $VENV ($("$VENV/bin/python" --version))"
"$VENV/bin/pip" list 2>/dev/null | grep -iE "lxml|PyYAML|psycopg|requests|dotenv" | sed 's/^/    /'

log "spark-defaults.conf"
cat > "$SPARK_HOME/conf/spark-defaults.conf" <<EOF
spark.master                     yarn
spark.submit.deployMode          client

# executor.memory + memoryOverhead 가 YARN 상한(6144MB) 을 넘으면 컨테이너 요청이 거부된다.
spark.executor.memory            4g
spark.executor.memoryOverhead    1g
spark.executor.cores             1
spark.executor.instances         3
spark.driver.memory              1g

# 드라이버와 executor 의 python 이 같아야 한다.
spark.pyspark.python             $VENV/bin/python
spark.pyspark.driver.python      $VENV/bin/python

spark.eventLog.enabled           true
spark.eventLog.dir               hdfs://ha-master:9000/spark-logs
EOF
echo "  작성 완료"

cat > "$SPARK_HOME/conf/spark-env.sh" <<'EOF'
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop
export YARN_CONF_DIR=/opt/hadoop/etc/hadoop
EOF
chmod 755 "$SPARK_HOME/conf/spark-env.sh"

chown -R ubuntu:ubuntu "/opt/spark-$SPARK_VERSION-bin-hadoop3" "$VENV"

cat > /etc/profile.d/spark.sh <<'EOF'
export SPARK_HOME=/opt/spark
export PATH=$PATH:$SPARK_HOME/bin
EOF
chmod 644 /etc/profile.d/spark.sh

log "완료"
echo "  Spark  $SPARK_HOME -> /opt/spark-$SPARK_VERSION-bin-hadoop3"
echo "  venv   $VENV  (executor 가 이 python 을 쓴다)"
echo ""
echo "  다음: hdfs dfs -mkdir -p /spark-logs 후 검증 스크립트 실행"
