from backend.database import db


class JammingPi(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    rpi = db.Column(db.String(255))
    sync = db.Column(db.Boolean(), default=True)
    relative = db.Column(db.Boolean(), default=False)
    composition_id = db.Column(
        db.Integer, db.ForeignKey('jamming_composition.id'))
    scenario_id = db.Column(db.Integer, db.ForeignKey('jamming_scenario.id'))
    scenario = db.relationship("JammingScenario", uselist=False)

    def __init__(self, rpi, composition_id, scenario_id):
        self.rpi = rpi
        self.composition_id = composition_id
        self.scenario_id = scenario_id

    @property
    def serialize(self):
        return {
            'id': self.id,
            'rpi': self.rpi,
            'sync': self.sync,
            'relative': self.relative,
            'composition_id': self.composition_id,
            'scenario_id': self.scenario_id
        }
