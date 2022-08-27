from backend.database import db


class JammingScenario(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(255))
    timings = db.relationship('JammingTiming', backref='group', lazy='dynamic', order_by="asc(JammingTiming.timestamp)")

    def __init__(self, name):
        self.name = name

    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
        }
