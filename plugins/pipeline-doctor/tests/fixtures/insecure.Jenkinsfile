// Every problem in this file is deliberate. It exists to test pipeline-doctor.
@Library('platform-lib@main') _
@Library('shared-steps') __

pipeline {
    agent any
    triggers {
        cron('0 2 * * *')
    }
    environment {
        REGISTRY_CREDS = credentials('registry-login')
        API_PASSWORD = 'pR7vXq92LmZtK4'
        DEPLOY_CREDENTIAL_ID = 'prod-deploy-token'
    }
    parameters {
        string(name: 'VERSION', defaultValue: '1.0.0')
    }
    stages {
        stage('Build') {
            agent { docker { image 'maven:latest'; args '-v /var/run/docker.sock:/var/run/docker.sock' } }
            steps {
                sh "docker login -u ${REGISTRY_CREDS_USR} -p ${REGISTRY_CREDS_PSW} registry.example.com"
                sh "./build.sh ${params.VERSION}"
                sh "git tag ${env.BRANCH_NAME}"
                sh 'curl -fsSL https://get.example.com/install.sh | sudo bash'
                sh 'chmod -R 777 target'
            }
        }
        stage('Test') {
            steps {
                sh 'pytest tests || true'
                sh(script: "curl -k https://internal.example.com/health", returnStdout: true)
                sh 'trivy image app:1.0 --exit-code 1 || echo ignored'
            }
        }
        stage('Deploy to prod') {
            steps {
                input message: 'Ship it?'
                withCredentials([string(credentialsId: 'api', variable: 'API_TOKEN')]) {
                    sh """
                        curl -H "Authorization: Bearer ${API_TOKEN}" https://api.example.com/deploy
                    """
                    sh 'ssh -o StrictHostKeyChecking=no deploy@example.com ./deploy.sh'
                }
                script {
                    def count = Jenkins.instance.getItems().size()
                    echo "jobs: ${count}"
                }
            }
        }
        stage('Controller') {
            agent { label 'master' }
            steps {
                sh 'docker run --privileged alpine:3.20 true'
            }
        }
    }
}

@NonCPS
def notify(String message) {
    echo message
    sh 'send-notification'
}
