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


class Config(db.Model):
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column(db.Integer(), primary_key=True)
    key = db.Column(db.String(255), unique=True)
    value = db.Column(db.String(255))

    def __init__(self, key, value):
        self.key = key
        self.value = value

    @staticmethod
    def get_bool(key, default=False):
        config = Config.query.filter_by(key=key).first()
        if config == None:
            return default
        elif config.value == "True":
            return True
        else:
            return False

    @staticmethod
    def get_int(key, default=0):
        config = Config.query.filter_by(key=key).first()
        if config == None:
            return default
        try:
            num = int(config.value, 10)
            return num
        except ValueError:
            return default

    @staticmethod
    def get_string(key, default=""):
        config = Config.query.filter_by(key=key).first()
        if config == None:
            return default
        return config.value
