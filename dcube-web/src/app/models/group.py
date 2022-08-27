from backend.database import db


class Group(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    users = db.relationship('User', backref='group', lazy='dynamic')
    jobs = db.relationship('Job', backref='group', lazy='dynamic')

    def __init__(self, name):
        self.name = name
