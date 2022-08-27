from backend.database import db


class LayoutPi(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    rpi = db.Column(db.String(255))
    command = db.Column(db.String(255))
    role = db.Column(db.String(255))
    group = db.Column(db.String(255))
    composition_id = db.Column(
        db.Integer, db.ForeignKey('layout_composition.id'))

    def __init__(self, rpi, command, role, group, composition_id):
        self.rpi = rpi
        self.command = command
        self.role = role
        self.group = group
        self.composition_id = composition_id

    @property
    def serialize(self):
        return {
            'id': self.id,
            'rpi': self.rpi,
            'command': self.command,
            'role': self.role,
            'group': self.group,
            'composition_id': self.composition_id
        }
