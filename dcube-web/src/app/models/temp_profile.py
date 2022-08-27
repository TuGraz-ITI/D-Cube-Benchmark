from backend.database import db


class TempProfile(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(255))
    filename = db.Column(db.String(255), unique=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    job = db.relationship("Job", back_populates="temp_profile")

    def __init__(self, name, filename, job_id):
        self.name = name
        self.filename = filename
        self.job_id = job_id
