from backend.database import db


class Node(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.Text())

    def __init__(self, name):
        self.name = name
