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
from datetime import datetime


class Job(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(255))
    scheduled = db.Column(db.DateTime())
    logs = db.Column(db.Boolean())
    duration = db.Column(db.Integer())
    #jamming = db.Column(db.Integer())
    failed = db.Column(db.Boolean(), default=False)
    running = db.Column(db.Boolean(), default=False)
    finished = db.Column(db.Boolean(), default=False)
    evaluated = db.Column(db.Boolean(), default=False)
    description = db.Column(db.String(255))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    firmware = db.relationship("Firmware", uselist=False, back_populates="job")
    result = db.relationship("Result", uselist=False, back_populates="job")
    scenario = db.relationship(
        'Scenario', backref='job', lazy='dynamic')
    #metric = db.relationship('Metric', backref='job', lazy='dynamic')
    metric = db.relationship('Metric',uselist=False)
    log = db.relationship("Log", uselist=False, back_populates="job")
    priority = db.Column(db.Boolean(), default=False)
    jamming_composition_id = db.Column(
        db.Integer, db.ForeignKey('jamming_composition.id'))
    jamming_composition = db.relationship('JammingComposition', uselist=False)
    # ewsn2019
    traffic_load = db.Column(db.Integer())
    msg_len = db.Column(db.Integer())
    layout_composition_id = db.Column(
        db.Integer, db.ForeignKey('layout_composition.id'))
    patch = db.Column(db.Boolean(), default=False)
    cpatch = db.relationship("Patch", uselist=False, back_populates="job")
    temp_profile = db.relationship("TempProfile", uselist=False, back_populates="job")
    overrides = db.Column(db.String(4096))
    config_overrides = db.Column(db.String(4096))
    # ewsn2020
    protocol_id = db.Column(db.Integer, db.ForeignKey('protocol.id'))


    # def __init__(self, name, description, scheduled, logs, jamming, reboot, priority, duration, group_id, node, category, node_placement, traffic_pattern, msg_len):
    def __init__(self, name, description, scheduled, logs, priority, duration, group_id, traffic_load, msg_len, jamming_composition_id, layout_composition_id, protocol_id ,patch=False):
        self.name = name
        self.description = description
        self.scheduled = scheduled
        self.logs = logs
        #self.jamming = jamming
        self.priority = priority
        self.duration = duration
        self.group_id = group_id
        self.traffic_load = traffic_load
        self.msg_len = msg_len
        self.jamming_composition_id = jamming_composition_id
        self.layout_composition_id = layout_composition_id
        self.protocol_id = protocol_id
        self.patch = patch
