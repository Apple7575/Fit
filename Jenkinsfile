pipeline {
    agent none

    options {
        timestamps()
        disableConcurrentBuilds(abortPrevious: true)
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
    }

    stages {
        stage('Verify') {
            parallel {
                stage('backend') {
                    agent {
                        docker { image 'gradle:9.7.1-jdk21' }
                    }
                    environment {
                        GRADLE_USER_HOME = "${WORKSPACE}/.gradle"
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
                    agent {
                        docker { image 'node:24-alpine' }
                    }
                    environment {
                        npm_config_cache = "${WORKSPACE}/.npm"
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
