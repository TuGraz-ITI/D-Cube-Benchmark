from backend.database import db
from datetime import datetime


class Result(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    begin = db.Column(db.DateTime())
    end = db.Column(db.DateTime())
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    job = db.relationship("Job", back_populates="result")

    def __init__(self, begin, end, job_id):
        self.begin = begin
        self.end = end
        self.job_id = job_id
