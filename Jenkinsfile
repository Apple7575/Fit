pipeline {
    agent none

    // 캐시를 ${WORKSPACE} 에 두면 브랜치마다, 병렬 스테이지마다(@2/@3) 따로 쌓인다.
    // jenkins_home 은 --volumes-from 으로 모든 에이전트에 이미 붙으므로 고정 경로를 쓴다.
    environment {
        CI_CACHE = '/var/jenkins_home/ci-cache'
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
                        ALL="backend frontend infra"
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

                        b=""; f=""; i=""
                        while IFS= read -r path; do
                            case "$path" in
                                backend/*)             b="backend" ;;
                                frontend/*)            f="frontend" ;;
                                infra/*)               i="infra" ;;
                                docs/*|.gitlab/*|*.md) ;;
                                *)                     run_all ;;
                            esac
                        done < .ci-changed

                        [ -z "$b$f$i" ] && i="infra"
                        echo "$b $f $i" > $OUT
                        exit 0
                    ''')

                    def areas = (ok == 0 && fileExists('.ci-areas')) ? readFile('.ci-areas').trim() : ''
                    if (!areas) { areas = 'backend frontend infra' }

                    env.RUN_BACKEND  = areas.contains('backend')  ? 'true' : 'false'
                    env.RUN_FRONTEND = areas.contains('frontend') ? 'true' : 'false'
                    env.RUN_INFRA    = areas.contains('infra')    ? 'true' : 'false'
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
            options {
                skipDefaultCheckout()
            }
            environment {
                DEPLOY_ENV = "${env.BRANCH_NAME == 'main' ? 'prod' : 'dev'}"
            }
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'deploy-ssh',
                                                   keyFileVariable: 'SSH_KEY',
                                                   usernameVariable: 'SSH_USER')]) {
                    // git clean 을 쓰지 않는다. .env.prod / .env.dev 는 추적 대상이 아니라 같이 지워진다.
                    // flock : main 과 develop 이 동시에 빌드돼도 호스트 작업 디렉토리를 한 번에 하나만 건드리게 한다.
                    sh '''
                        ssh -i "$SSH_KEY" \
                            -o StrictHostKeyChecking=accept-new \
                            -o ConnectTimeout=10 \
                            "$SSH_USER@host.docker.internal" \
                            "flock -w 900 /tmp/ca-deploy.lock -c '
                                set -e
                                cd /home/ubuntu/app
                                git fetch --prune origin
                                git reset --hard origin/$BRANCH_NAME
                                ./infra/deploy.sh $DEPLOY_ENV
                            '"
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
