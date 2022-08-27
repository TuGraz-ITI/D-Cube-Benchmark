from backend.database import db


class BenchmarkSuite(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    short = db.Column(db.String(255))
    name = db.Column(db.String(255))
    composition = db.relationship('LayoutComposition', lazy='dynamic')#, back_populates="benchmark_suite")
    node_id = db.Column(db.Integer, db.ForeignKey('node.id'))
    node = db.relationship('Node', uselist=False)
    #config = db.relationship(
    #    'BenchmarkConfig', lazy='dynamic', back_populates="benchmark_suite")
    energy = db.Column(db.Boolean(), default=True)
    latency = db.Column(db.Boolean(), default=True)
    reliability = db.Column(db.Boolean(), default=True)

    def __init__(self, name, short):
        self.name = name
        self.short = short

    @property
    def serialize(self):
        return {
            'id': self.id,
            'short': self.short,
            'node': self.node
        }
