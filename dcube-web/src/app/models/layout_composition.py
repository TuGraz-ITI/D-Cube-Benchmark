from backend.database import db


class LayoutComposition(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(255))
    short = db.Column(db.String(255))
    benchmark_suite_id = db.Column(db.Integer, db.ForeignKey('benchmark_suite.id'))
    job = db.relationship('Job', backref='layout', lazy='dynamic')
    benchmark_suite = db.relationship('BenchmarkSuite', backref='layouts', uselist=False) #, lazy='dynamic')
    #benchmark_suite = db.relationship('BenchmarkSuite') #, lazy='dynamic')

    def __init__(self, name, short, benchmark_suite_id):
        self.name = name
        self.short = short
        self.benchmark_suite_id = benchmark_suite_id

    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'benchmark_suite_id': self.benchmark_suite_id
        }
