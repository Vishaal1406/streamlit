pipeline {
    agent any
    environment {
        PATH = "/usr/bin:/usr/local/bin:${env.PATH}"
    }
    stages {
        stage('Git Clone') {
            steps {
                git branch: 'main', url: 'http://gitea-n:3000/admin/streamlit-app.git'
            }
        }

        stage('Setup Python Environment') {
            steps {
                sh '''
                apt update && apt install -y python3 python3-pip python3-venv
                python3 -m venv venv
                '''
            }
        }

        stage('Install System Dependencies') {
            steps {
                sh '''
                apt update && apt install -y libpq-dev
                '''
            }
        }

        stage('Install Python Dependencies') {
            steps {
                sh '''
                . venv/bin/activate
                pip install --upgrade pip
                pip install -r requirements.txt
                '''
            }
        }

        stage('Linting') {
            steps {
                sh '''
                . venv/bin/activate
                pip install pylint
                echo "[MASTER]
                disable=C0303,C0301,C0114,C0116,W0404,W0621,W0718,W1514,I1101,R1705,C0411,C0103,R1733,W0416,C0412,W0612,W0611,C0413" > .pylintrc
                pylint app.py
                '''
            }
        }
        stage('Check Image Files') {
            steps {
                sh '''
                ls -lah images/
                if [ ! -f images/pav_bhaji.jpg ]; then
                    echo "ERROR: images/pav_bhaji.jpg not found!"
                    exit 1
                fi
                '''
            }
        }

        stage('Check Test File') {
            steps {
                sh '''
                if [ ! -f test_app.py ]; then
                    echo "ERROR: test_app.py not found!"
                    exit 1
                fi
                '''
            }
        }

        stage('Run Unit Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    #nohup streamlit run app.py --server.port=8501 --server.headless=true > streamlit.log 2>&1 &
                    #sleep 5 
                    pytest -vv --disable-warnings -q 
                '''

            }
        }




        stage('Code Formatting') {
            steps {
                sh '''
                . venv/bin/activate && pip install black
                black .
                black --check .
                '''
            }
        }


        stage('Security Scan') {
            steps {
                sh '''
                . venv/bin/activate
                pip install safety
                pip install --upgrade setuptools
                safety check 2>/dev/null || true
                '''
            }
        }

        stage('Static Code Analysis') {
            steps {
                sh '''
                . venv/bin/activate
                pip install types-requests types-ujson
                pip install mypy
                mypy app.py
                '''
            }
        }

        stage('Run Streamlit App in Background') {
            steps {
                sh '''
                . venv/bin/activate
                nohup streamlit run app.py --server.port=8501 --server.headless=true > streamlit.log 2>&1 &
                '''
            }
        }

        stage('Monitor Streamlit Application') {
            steps {
                sh '''
                sleep 10
                curl  http://localhost:8501
                '''
            }
        }

        stage('Smoke Testing') {
            steps {
                sh '''
                ps aux | grep streamlit
                '''
            }
        }

        stage('Cleanup') {
            steps {
                sh '''
                rm -rf streamlit-app
                '''
            }
        }
    }
}
