from backend.database import db


class Log(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    text = db.Column(db.Text())
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    job = db.relationship("Job", back_populates="log")

    def __init__(self, job_id):
        self.job_id = job_id
        self.text = ""
