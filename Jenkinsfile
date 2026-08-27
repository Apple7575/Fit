pipeline {
    agent none

    options {
        timestamps()
        disableConcurrentBuilds(abortPrevious: true)
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 30, unit: 'MINUTES')
    }

    stages {
        stage('Verify') {
            parallel {
                stage('backend') {
                    agent {
                        docker {
                            image 'eclipse-temurin:21-jdk'
                            // Gradle 캐시를 빌드 간 재사용해 매번 배포판을 내려받지 않게 한다.
                            args '-v $HOME/.gradle-cache:/root/.gradle'
                        }
                    }
                    steps {
                        dir('backend') {
                            sh 'chmod +x gradlew'
                            sh './gradlew build --no-daemon'
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
                        docker {
                            image 'node:24-alpine'
                            args '-v $HOME/.npm-cache:/root/.npm'
                        }
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
                            // POSTGRES_PASSWORD 는 필수값이므로 문법 검증용 더미를 채운다.
                            sh '''
                                cp .env.example .env
                                sed -i 's/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=ci-dummy/' .env
                                docker compose config --quiet
                                rm -f .env
                            '''
                        }
                    }
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
