pipeline {
    agent none

    // 캐시를 ${WORKSPACE} 에 두면 브랜치마다, 병렬 스테이지마다(@2/@3) 따로 쌓인다.
    // jenkins_home 은 --volumes-from 으로 모든 에이전트에 이미 붙으므로 고정 경로를 쓴다.
    environment {
        CI_CACHE = '/var/jenkins_home/ci-cache'
    }

    // 운영 DB 에 쓰는 것은 사람이 켜야 한다. develop(dev DB)은 시드가 바뀌면 알아서 돈다.
    parameters {
        booleanParam(
            name: 'LOAD_SEED_PROD', defaultValue: false,
            description: 'main 빌드에서 운영 DB(prod)에 시드를 적재한다. 켜지 않으면 건너뛴다.')
        booleanParam(
            name: 'FORCE_SEED_LOAD', defaultValue: false,
            description: '시드 파일이 안 바뀌었어도 적재한다.')
    }

    options {
        timestamps()
        disableConcurrentBuilds(abortPrevious: true)
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
    }

    stages {
        stage('Changes') {
            agent any
            steps {
                script {
                    def ok = sh(returnStatus: true, script: '''
                        set -u
                        OUT=.ci-areas
                        ALL="backend frontend infra ai"
                        run_all() { echo "$ALL" > $OUT; exit 0; }

                        # main/develop 은 deploy.sh 가 두 이미지를 모두 다시 빌드하므로 예외 없이 전부 검증한다.
                        case "$BRANCH_NAME" in
                            main|develop) run_all ;;
                        esac

                        # 기준을 못 구하면 전부 돌린다. 검증을 건너뛰고 초록불이 뜨는 쪽이 훨씬 위험하다.
                        TARGET="${CHANGE_TARGET:-develop}"
                        git fetch --no-tags --quiet origin "$TARGET" 2>/dev/null || run_all
                        BASE=$(git merge-base FETCH_HEAD HEAD 2>/dev/null)      || run_all
                        git diff --name-only "$BASE" HEAD > .ci-changed         || run_all
                        [ -s .ci-changed ]                                      || run_all

                        b=""; f=""; i=""; a=""
                        while IFS= read -r path; do
                            case "$path" in
                                backend/*)             b="backend" ;;
                                frontend/*)            f="frontend" ;;
                                infra/*)               i="infra" ;;
                                ai/*)                  a="ai" ;;
                                docs/*|.gitlab/*|*.md) ;;
                                *)                     run_all ;;
                            esac
                        done < .ci-changed

                        [ -z "$b$f$i$a" ] && i="infra"
                        echo "$b $f $i $a" > $OUT
                        exit 0
                    ''')

                    def areas = (ok == 0 && fileExists('.ci-areas')) ? readFile('.ci-areas').trim() : ''
                    if (!areas) { areas = 'backend frontend infra ai' }

                    env.RUN_BACKEND  = areas.contains('backend')  ? 'true' : 'false'
                    env.RUN_FRONTEND = areas.contains('frontend') ? 'true' : 'false'
                    env.RUN_INFRA    = areas.contains('infra')    ? 'true' : 'false'
                    env.RUN_AI       = areas.contains('ai')       ? 'true' : 'false'
                    echo "검증 대상: ${areas}"
                }
            }
        }

        stage('Verify') {
            parallel {
                stage('backend') {
                    when {
                        beforeAgent true
                        expression { env.RUN_BACKEND == 'true' }
                    }
                    agent {
                        docker { image 'gradle:9.7.1-jdk21' }
                    }
                    environment {
                        GRADLE_USER_HOME = "${CI_CACHE}/gradle"
                    }
                    steps {
                        dir('backend') {
                            sh 'gradle build --no-daemon'
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true,
                                  testResults: 'backend/build/test-results/test/TEST-*.xml'
                        }
                    }
                }

                stage('frontend') {
                    when {
                        beforeAgent true
                        expression { env.RUN_FRONTEND == 'true' }
                    }
                    agent {
                        docker { image 'node:24-alpine' }
                    }
                    environment {
                        npm_config_cache = "${CI_CACHE}/npm"
                    }
                    steps {
                        dir('frontend') {
                            sh 'npm ci --prefer-offline'
                            sh 'npm run lint'
                            sh 'npm run build'
                        }
                    }
                }

                stage('ai') {
                    when {
                        beforeAgent true
                        expression { env.RUN_AI == 'true' }
                    }
                    agent {
                        docker { image 'python:3.12-slim' }
                    }
                    environment {
                        PIP_CACHE_DIR = "${CI_CACHE}/pip"
                    }
                    steps {
                        // 테스트가 ai.jd_coaching 처럼 저장소 루트 기준으로 import 하므로 루트에서 돈다.
                        // 컨테이너 uid 에 홈이 없어 --user 설치가 안 된다. 워크스페이스에 venv 를 만든다.
                        sh '''
                            python -m venv .venv
                            .venv/bin/pip install --quiet -r ai/requirements-dev.txt
                            .venv/bin/python -m unittest discover -s ai/tests -t .
                        '''
                    }
                }

                stage('infra') {
                    when {
                        beforeAgent true
                        expression { env.RUN_INFRA == 'true' }
                    }
                    agent {
                        docker {
                            image 'docker:27-cli'
                            args '-v /var/run/docker.sock:/var/run/docker.sock'
                        }
                    }
                    steps {
                        dir('infra') {
                            sh '''
                                for e in prod dev; do
                                    sed 's/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=ci-dummy/' ".env.$e.example" > .env.ci
                                    docker compose --env-file .env.ci config --quiet
                                    rm -f .env.ci
                                done
                                docker compose -f proxy/docker-compose.yml config --quiet

                                # 로컬 조합. 예제에 비밀번호가 들어 있어 sed 가 필요 없다.
                                docker compose --env-file .env.local.example \
                                    -f docker-compose.yml -f docker-compose.local.yml config --quiet
                            '''
                        }
                    }
                }
            }
        }

        stage('Deploy') {
            when {
                beforeAgent true
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            agent any
            environment {
                DEPLOY_ENV = "${env.BRANCH_NAME == 'main' ? 'prod' : 'dev'}"
            }
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'deploy-ssh',
                                                   keyFileVariable: 'SSH_KEY',
                                                   usernameVariable: 'SSH_USER'),
                                 file(credentialsId: "env-secrets-${env.DEPLOY_ENV}",
                                      variable: 'SECRETS')]) {
                    // .env 는 예제(비밀 아닌 값) + 크리덴셜 파일(비밀값) 로 여기서 만들어
                    // 표준입력으로만 넘긴다. 명령줄에 실으면 ps 로 다른 사용자에게 보인다.
                    // flock : main 과 develop 이 동시에 빌드돼도 호스트 작업 디렉토리를 한 번에 하나만 건드리게 한다.
                    sh '''
                        set +x
                        EXAMPLE="infra/.env.$DEPLOY_ENV.example"
                        [ -f "$EXAMPLE" ] || { echo "$EXAMPLE 가 없습니다."; exit 1; }

                        # 크리덴셜 파일이 가진 키는 예제에서 빼고 그쪽 값으로 덮는다.
                        # tr -d : 파일을 Windows 에서 만들면 값 끝에 CR 이 붙어 조용히 틀린다.
                        KEYS=$(tr -d '\r' < "$SECRETS" | grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' | tr -d '=' | paste -sd '|' -)
                        [ -n "$KEYS" ] || { echo "크리덴셜 파일에 KEY=VALUE 가 없습니다."; exit 1; }

                        {
                            grep -vE "^($KEYS)=" "$EXAMPLE"
                            cat "$SECRETS"
                            # 손으로 만든 파일이라 끝 개행이 없을 수 있다. 없으면 다음 줄이 값에 붙는다.
                            echo ""
                            echo '#transfer-ok'
                        } | tr -d '\r' | ssh -i "$SSH_KEY" \
                            -o StrictHostKeyChecking=accept-new \
                            -o ConnectTimeout=10 \
                            "$SSH_USER@host.docker.internal" \
                            "flock -w 900 /tmp/ca-deploy.lock -c '
                                set -e
                                cd /home/ubuntu/app
                                git fetch --prune origin
                                git reset --hard origin/$BRANCH_NAME
                                cat > infra/.env.$DEPLOY_ENV.new
                                grep -q ^#transfer-ok infra/.env.$DEPLOY_ENV.new
                                chmod 600 infra/.env.$DEPLOY_ENV.new
                                mv infra/.env.$DEPLOY_ENV.new infra/.env.$DEPLOY_ENV
                                ./infra/deploy.sh $DEPLOY_ENV
                            '"
                    '''
                }
            }
        }

        stage('Deploy-Data') {
            when {
                beforeAgent true
                branch 'develop'
            }
            agent any
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'deploy-ssh',
                                                   keyFileVariable: 'SSH_KEY',
                                                   usernameVariable: 'SSH_USER')]) {
                    // data/ 를 2호기(하둡 노드)로 직접 전송한다.
                    sh '''
                        tar czf - data | ssh -i "$SSH_KEY" \
                            -o StrictHostKeyChecking=accept-new \
                            -o ConnectTimeout=10 \
                            "$SSH_USER@172.26.6.113" '
                                set -e
                                D=/home/ubuntu/pipeline
                                rm -rf "$D/.data.new" && mkdir -p "$D/.data.new"
                                tar xzf - -C "$D/.data.new"
                                rm -rf "$D/data" && mv "$D/.data.new/data" "$D/data"
                                rmdir "$D/.data.new"
                                echo "data 동기화: $(find "$D/data" -type f | wc -l) 파일"
                            '
                    '''
                }
            }
        }

        // 시드 CSV → DB. 배포는 Flyway 로 **테이블까지만** 만들고 값은 아무도 안 넣어서,
        // 지금까지 사람이 1호기에 들어가 스크립트를 쳤다. 그 자리를 없앤다.
        //
        // 1호기에는 파이썬이 없고 `/data/` 는 sparse checkout 에서 빠져 있다(앱 서버는
        // 파이프라인을 받지 않는다). 그래서 Deploy-Data 와 같은 방식으로 필요한 것만
        // tar 로 흘려보내고 **일회용 컨테이너**로 돌린다. 호스트에 파이썬을 깔지 않는다.
        //
        // 로더가 Flyway 마이그레이션을 읽어 자연키를 대조하므로 backend 의 migration 도
        // 함께 보낸다 — **저장소 구조 그대로**여야 경로가 맞는다 (실측으로 확인).
        //
        // postgres 는 127.0.0.1 에만 열려 있어 호스트 밖에서 못 붙는다. 컨테이너를
        // 그 스택의 appnet 에 붙여 서비스 이름 `postgres` 로 간다.
        //
        // **보내기와 실행을 나눈다.** 한 ssh 에 tar 를 파이프로 물리면서 원격 스크립트를
        // heredoc 으로 주면 stdin 을 서로 뺏어 tar 가 사라진다.
        stage('Load-Seed') {
            when {
                beforeAgent true
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            agent any
            environment {
                DEPLOY_ENV = "${env.BRANCH_NAME == 'main' ? 'prod' : 'dev'}"
            }
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'deploy-ssh',
                                                   keyFileVariable: 'SSH_KEY',
                                                   usernameVariable: 'SSH_USER')]) {
                    sh '''
                        set -eu
                        SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
                        HOST=$SSH_USER@host.docker.internal

                        # 운영 DB 에 쓰는 것은 사람이 켤 때만 한다.
                        if [ "$DEPLOY_ENV" = "prod" ] && [ "${LOAD_SEED_PROD:-false}" != "true" ]; then
                            echo "prod 적재는 LOAD_SEED_PROD 를 켠 빌드에서만 합니다. 건너뜁니다."
                            exit 0
                        fi

                        # 시드가 안 바뀌었으면 4분을 쓸 이유가 없다. 머지 커밋이면 HEAD~1 이
                        # 직전 develop 이라 병합된 브랜치의 변경이 그대로 잡힌다.
                        if [ "${FORCE_SEED_LOAD:-false}" != "true" ]; then
                            if ! git diff --name-only HEAD~1 HEAD 2>/dev/null \
                                 | grep -qE '^data/(curated/seed|config)/'; then
                                echo "시드·설정 변경이 없습니다. 건너뜁니다. (FORCE_SEED_LOAD 로 강제 가능)"
                                exit 0
                            fi
                        fi

                        # ── 1. 보낸다 (stdin 은 tar 전용)
                        tar czf - data/curated/seed data/manifests/seed data/scripts \
                                  data/pipeline data/config data/requirements.txt \
                                  backend/src/main/resources/db/migration \
                        | $SSH "$HOST" '
                            set -e
                            D=/home/ubuntu/dataload
                            rm -rf "$D.new" && mkdir -p "$D.new"
                            tar xzf - -C "$D.new"
                            rm -rf "$D" && mv "$D.new" "$D"
                            echo "받음: $(find "$D" -type f | wc -l) 파일"
                        '

                        # ── 2. 돌린다 (stdin 이 비어 heredoc 을 쓸 수 있다)
                        $SSH "$HOST" "CA_ENV=$DEPLOY_ENV bash -s" <<'REMOTE'
flock -w 900 /tmp/ca-seedload.lock -c '
  set -e
  D=/home/ubuntu/dataload
  cfg=/home/ubuntu/app/infra/.env.$CA_ENV
  # 값에 특수문자가 있어 source 하면 깨진다 — 줄에서 뽑는다 (실측: line 44 오류).
  PW=$(grep -E "^POSTGRES_PASSWORD=" "$cfg" | cut -d= -f2- | tr -d "\r")
  DB=$(grep -E "^POSTGRES_DB=" "$cfg" | cut -d= -f2- | tr -d "\r")
  US=$(grep -E "^POSTGRES_USER=" "$cfg" | cut -d= -f2- | tr -d "\r")

  run() {
    docker run --rm --network "ca-${CA_ENV}_appnet" \
      -v "$D":/repo -w /repo/data \
      -e DATABASE_URL="postgresql://${US}:${PW}@postgres:5432/${DB}" \
      -e PYTHONIOENCODING=utf-8 -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
      python:3.12-slim sh -c "pip install -q \"psycopg[binary]>=3.1\" \"python-dotenv>=1.0\" \"PyYAML>=6.0\" && $1"
  }

  echo "── company 먼저 (나머지가 FK 를 건다)"
  run "python scripts/load_company.py"
  echo "── 무엇이 들어가는지 먼저 본다"
  run "python scripts/load_seed_csv.py --dry-run"
  echo "── 적재"
  run "python scripts/load_seed_csv.py"

  rm -rf "$D"
'
REMOTE
                    '''
                }
            }
        }
    }

    post {
        failure {
            echo "빌드 실패: ${env.BUILD_URL}"
        }
    }
}
