from flask_security import RoleMixin

from backend.database import db


class Role(db.Model, RoleMixin):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
