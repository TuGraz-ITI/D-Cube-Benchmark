from backend.database import db


class Scenario(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    source = db.Column(db.String(255))
    destination = db.Column(db.String(255))
    gpio = db.Column(db.String(255))
    evaluation = db.relationship(
        'Evaluation', backref='scenario', lazy='dynamic')
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))

    def __init__(self, source, destination, gpio, job_id):
        self.source = source
        self.destination = destination
        self.gpio = gpio
        self.job_id = job_id
