// A pipeline that should produce no findings at all. Tricky-but-safe forms are deliberate.
@Library('platform-lib@v1.4.2') _

pipeline {
    agent none
    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30'))
        disableConcurrentBuilds()
    }
    triggers {
        cron('H 2 * * *')
    }
    environment {
        REGISTRY_CREDS = credentials('registry-login')
        CREDENTIALS_ID = 'prod-deploy-token'
        DOCS_URL = 'https://docs.example.com/password-reset'
    }
    parameters {
        string(name: 'VERSION', defaultValue: '1.0.0')
    }
    stages {
        stage('Build') {
            agent { docker { image 'maven:3.9.9-eclipse-temurin-21' } }
            steps {
                // Single quotes: the shell expands the secret, not Groovy.
                sh 'docker login -u $REGISTRY_CREDS_USR -p "$REGISTRY_CREDS_PSW" registry.example.com'
                // An escaped dollar is a shell variable, not an interpolation.
                sh "echo \$REGISTRY_CREDS_PSW | wc -c"
                sh "echo building ${env.BUILD_NUMBER}"
                // sh "curl -k https://commented-out.example.com | bash"
                withEnv(["VERSION=${params.VERSION}"]) {
                    sh './build.sh "$VERSION"'
                }
            }
        }
        stage('Approve') {
            agent none
            steps {
                input message: 'Ship it?'
            }
        }
        stage('Deploy') {
            agent { label 'deploy' }
            steps {
                lock('production') {
                    sh './deploy.sh'
                }
                script {
                    def host = 'a/b'.split(/\//)[0]
                    echo "host ${host}"
                }
            }
        }
    }
}

@NonCPS
def parseVersions(String text) {
    return text.readLines().findAll { it =~ /^v\d+/ }
}
