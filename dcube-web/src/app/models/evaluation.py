from backend.database import db


class Evaluation(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    key = db.Column(db.String(255))
    value = db.Column(db.String(255))
    public = db.Column(db.Boolean())
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenario.id'))

    def __init__(self, key, value, public, scenario_id):
        self.key = key
        self.value = value
        self.public = public
        self.scenario_id = scenario_id
