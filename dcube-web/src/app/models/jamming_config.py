from backend.database import db


class JammingConfig(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    channel = db.Column(db.Integer())
    power = db.Column(db.Integer())
    periode = db.Column(db.Integer())
    length = db.Column(db.Integer())
    name = db.Column(db.String(255))

    def __init__(self, name, channel, power, periode, length):
        self.name = name
        self.channel = channel
        self.power = power
        self.periode = periode
        self.length = length

    @property
    def serialize(self):
        return {
            'id': self.id,
            'channel': self.channel,
            'power': self.power,
            'periode': self.periode,
            'length': self.length
        }
