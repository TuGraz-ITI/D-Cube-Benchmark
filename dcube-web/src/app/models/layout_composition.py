#
# MIT License
#
# Copyright (c) 2023 Graz University of Technology
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
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
