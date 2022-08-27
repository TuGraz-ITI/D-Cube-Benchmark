from backend.database import db


class BenchmarkConfig(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    benchmark_suite_id = db.Column(db.Integer, db.ForeignKey('benchmark_suite.id'))
    benchmark_suite = db.relationship('BenchmarkSuite', backref='configs', uselist=False) #, lazy='dynamic')
    key = db.Column(db.String(255))
    value = db.Column(db.String(255))

    def __init__(self, key, value, benchmark_suite_id):
        self.key = key
        self.value = value
        self.benchmark_suite_id = benchmark_suite_id
