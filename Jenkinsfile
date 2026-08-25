pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                echo 'TODO: 빌드 명령'
            }
        }

        stage('Test') {
            steps {
                echo 'TODO: 테스트 명령'
            }
        }

        stage('Deploy') {
            steps {
                echo 'TODO: EC2 배포'
            }
        }
    }

    post {
        failure {
            echo '파이프라인 실패'
        }
    }
}
