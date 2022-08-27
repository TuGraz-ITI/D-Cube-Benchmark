from backend.database import db


class Config(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    key = db.Column(db.String(255), unique=True)
    value = db.Column(db.String(255))

    def __init__(self, key, value):
        self.key = key
        self.value = value

    @staticmethod
    def get_bool(key, default=False):
        config = Config.query.filter_by(key=key).first()
        if config == None:
            return default
        elif config.value == "True":
            return True
        else:
            return False

    @staticmethod
    def get_int(key, default=0):
        config = Config.query.filter_by(key=key).first()
        if config == None:
            return default
        try:
            num = int(config.value, 10)
            return num
        except ValueError:
            return default

    @staticmethod
    def get_string(key, default=""):
        config = Config.query.filter_by(key=key).first()
        if config == None:
            return default
        return config.value
