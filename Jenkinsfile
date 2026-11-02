// Tests Pipeline Doctor and runs it against this file.
pipeline {
    agent { label 'docker' }
    options {
        timeout(time: 10, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30'))
        disableConcurrentBuilds()
    }
    stages {
        stage('Unit tests') {
            steps {
                dir('plugins/pipeline-doctor') {
                    sh 'python3 -m unittest discover -s tests'
                }
            }
        }
        stage('Audit this pipeline') {
            steps {
                sh 'python3 plugins/pipeline-doctor/skills/audit/scripts/pipeline_doctor.py Jenkinsfile --fail-on low'
            }
        }
    }
}
