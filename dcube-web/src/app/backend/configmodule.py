import bleach

class Config(object):
    def uia_username_mapper(identity):
        # we allow pretty much anything - but we bleach it.
        return bleach.clean(identity, strip=True)

    TEMPLATES_AUTO_RELOAD = True
    SECRET_KEY = 'dcube'.encode('utf8')
    
    DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    BLOGGING_URL_PREFIX = "/blog"
    BLOGGING_SITEURL = "http://localhost"
    BLOGGING_SITENAME = "D-Cube Testbed"
    BLOGGING_PERMISSIONS = True
    BLOGGING_PERMISSIONNAME = "admins"
    BLOGGING_ALLOW_FILEUPLOAD = True
    FILEUPLOAD_PREFIX = "/fileupload"
    FILEUPLOAD_LOCALSTORAGE_STATIC = "/storage"
    FILEUPLOAD_LOCALSTORAGE_IMG_FOLDER = "fileupload"
    FILEUPLOAD_ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "pdf", "ppt", "pptx", "txt", "zip"]
    
    # Because we're security-conscious developers, we also hard-code disabling
    # the CDN support (this might become a default in later versions):
    BOOTSTRAP_SERVE_LOCAL = True
    
    UPLOAD_FOLDER = '/storage/firmwares'
    ALLOWED_EXTENSIONS = set(['ihex','hex'])
    
    GRAFANA_URL="/grafana"
    GRAFANA_DASHBOARD_FOLDER = "?folderIds=3"
    
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
    SECURITY_SEND_PASSWORD_CHANGE_EMAIL	= False
    SECURITY_URL_PREFIX = '/auth'
    SECURITY_POST_LOGIN_VIEW = 'frontend.index'
    SECURITY_POST_LOGOUT_VIEW = 'frontend.index'
    SECURITY_UNAUTHORIZED_VIEW = 'frontend.index'
    SECURITY_PASSWORD_HASH = 'pbkdf2_sha512'
    # import uuid; salt = uuid.uuid4().hex
    SECURITY_PASSWORD_SALT = '5d99d5d942024a86bf15427a3a1685e9'
    SECURITY_USER_IDENTITY_ATTRIBUTES = [{'username':{"mapper":uia_username_mapper}}]
    GRAFANA_DASHBOARD_FOLDER = "?folderIds=3"

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
