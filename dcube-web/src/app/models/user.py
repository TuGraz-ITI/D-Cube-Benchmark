from flask_security import UserMixin

from backend.database import db, roles_users


class User(db.Model, UserMixin):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    api_key = db.Column(db.String(255), unique=True)
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    fs_uniquifier = db.Column(db.String(255), unique=True, nullable=False)

    def get_name(self):
        return self.username
