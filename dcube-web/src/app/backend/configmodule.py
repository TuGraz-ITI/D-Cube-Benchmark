#
# MIT License
#
# Copyright (c) 2023 Graz University of Technology
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
import bleach

class Config(object):
    def uia_username_mapper(identity):
        # we allow pretty much anything - but we bleach it.
        return bleach.clean(identity, strip=True)

    TEMPLATES_AUTO_RELOAD = True
    SECRET_KEY = 'dcube'.encode('utf8')
    
    DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Because we're security-conscious developers, we also hard-code disabling
    # the CDN support (this might become a default in later versions):
    BOOTSTRAP_SERVE_LOCAL = True
    
    UPLOAD_FOLDER = '/storage/firmwares'
    ALLOWED_EXTENSIONS = set(['ihex','hex'])
    
    GRAFANA_URL = "/grafana"
    GRAFANA_DASHBOARD_FOLDER = "?folderIds=1"
    
    LOGFILE_FOLDER = '/storage/logfiles/'
    EVALUATION_FOLDER = '/storage/evaluations/'
    PATCH_FOLDER = '/storage/patches/'
    TEMPLAB_FOLDER = '/storage/temperature_profiles/'
    
    # Flask-Security setup
    SECURITY_EMAIL_SENDER = 'Testbed < noreply@testbed.local>'
    SECURITY_LOGIN_WITHOUT_CONFIRMATION = True
    SECURITY_REGISTERABLE = False
    SECURITY_RECOVERABLE = False
    SECURITY_CHANGEABLE = True
    SECURITY_USERNAME_ENABLE = True
    SECURITY_SEND_PASSWORD_CHANGE_EMAIL	= False
    SECURITY_URL_PREFIX = '/auth'
    SECURITY_POST_LOGIN_VIEW = 'frontend.index'
    SECURITY_POST_LOGOUT_VIEW = 'frontend.index'
    SECURITY_UNAUTHORIZED_VIEW = 'frontend.index'
    SECURITY_PASSWORD_HASH = 'pbkdf2_sha512'
    # import uuid; salt = uuid.uuid4().hex
    SECURITY_PASSWORD_SALT = '5d99d5d942024a86bf15427a3a1685e9'
    SECURITY_USER_IDENTITY_ATTRIBUTES = [{'username':{"mapper":uia_username_mapper}}]

    # Enforce 2FA
    SECURITY_TWO_FACTOR_ENABLED_METHODS = ['authenticator','email']  # 'sms' also valid but requires an sms provider
    SECURITY_TWO_FACTOR = True
    SECURITY_TWO_FACTOR_REQUIRED = True
    SECURITY_TWO_FACTOR_RESCUE_EMAIL = False
    SECURITY_TWO_FACTOR_ALWAYS_VALIDATE = True
    SECURITY_TWO_FACTOR_LOGIN_VALIDITY = "1 week"

    # Generate a good totp secret using: passlib.totp.generate_secret()
    SECURITY_TOTP_SECRETS = {"1": "TjQ9Qa31VOrfEzuPy4VHQWPCTmRzCnFzMKLxXYiZu9B"}
    SECURITY_TOTP_ISSUER = "D-Cube"


    PYTHON_PATH = "/usr/bin/python3" 
    DCM_PATH = "/testbed/pydcube"
    DCM_BINARY = "/testbed/pydcube/rpc_testbed.py"
    DCM_BROKER="rabbitmq"
    SWITCH_CONFIG = "switch.json"

    INFLUX_USER = "root"
    INFLUX_PASSWORD = "root"
    INFLUX_HOST = "influx"
    INFLUX_DBNAME = "dcube"
    INFLUX_PORT = 8086

    LANDING_PAGE = "/overview"

class DockerConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://dcube:YzqmVQt9@mysql/dcube'
