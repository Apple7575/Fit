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
                                sed 's/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=ci-dummy/' .env.example > .env.ci
                                docker compose --env-file .env.ci config --quiet
                                rm -f .env.ci
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
