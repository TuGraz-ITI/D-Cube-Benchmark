from backend.database import db


class JammingTiming(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    timestamp = db.Column(db.BigInteger())
    config_id = db.Column(db.Integer, db.ForeignKey('jamming_config.id'))
    scenario_id = db.Column(db.Integer, db.ForeignKey('jamming_scenario.id'))
    config = db.relationship("JammingConfig", uselist=False)

    def __init__(self, timestamp, config_id, scenario_id):
        self.timestamp = timestamp
        self.config_id = config_id
        self.scenario_id = scenario_id

    @property
    def serialize(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'config_id': self.config_id,
            'scenario_id': self.scenario_id
        }
