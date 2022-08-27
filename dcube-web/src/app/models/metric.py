from backend.database import db


class Metric(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    energy = db.Column(db.Float())
    reliability = db.Column(db.Float())
    latency = db.Column(db.Float())
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    job = db.relationship("Job",back_populates="metric",uselist=False, foreign_keys = 'Metric.job_id')

    def __init__(self, energy, reliability, latency, job_id):
        self.energy = energy
        self.reliability = reliability
        self.latency = latency
        self.job_id = job_id
