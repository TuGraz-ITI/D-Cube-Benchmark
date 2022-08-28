#
# MIT License
#
# Copyright (c) 2022 Graz University of Technology
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
from .storage.storage import LocalStorage


class FlaskFileUpload(object):

    def __init__(self, app=None, storage=None):
        self.app = None
        self.storage = storage
        self.prefix = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):

        self.app = app
        self.storage = self.storage or LocalStorage(app)
        self.prefix = app.config.get("FILEUPLOAD_PREFIX", "/upload")

        from .views import create_blueprint

        fu_static = app.config.get("FILEUPLOAD_LOCALSTORAGE_STATIC","static")
        bp = create_blueprint(__name__, app=app, storage=self.storage,static_folder=fu_static)

        self.app.register_blueprint(
            bp,
            url_prefix=self.prefix
        )
