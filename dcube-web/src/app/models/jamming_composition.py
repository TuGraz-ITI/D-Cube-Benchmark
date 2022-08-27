from backend.database import db


class JammingComposition(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(255))
    short = db.Column(db.String(255))
    public = db.Column(db.Boolean(), default=True)
    #scenarios = db.relationship("JammingScenario", uselist=False)

    def __init__(self, name, short, public=True):
        self.name = name
        self.short = short
        self.public = public

    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
        }
