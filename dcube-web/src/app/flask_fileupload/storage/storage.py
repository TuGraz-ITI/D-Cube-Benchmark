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
import os

from werkzeug.utils import secure_filename
from flask import url_for
from .utils import convert_to_snake_case
from . import AbstractStorage, StorageExists, StorageNotExists, StorageNotAllowed


class LocalStorage(AbstractStorage):

    def __init__(self, app):
        super(LocalStorage, self).__init__(app)
        self.img_folder = app.config.get("FILEUPLOAD_LOCALSTORAGE_IMG_FOLDER", "upload")
        self.img_folder = self.img_folder if self.img_folder.endswith("/") else self.img_folder + "/"
        self.static_folder = app.config.get("FILEUPLOAD_LOCALSTORAGE_STATIC","static")
        self.abs_img_folder = os.path.join(self.static_folder, self.img_folder)
        if not os.path.exists(self.abs_img_folder):
            os.makedirs(self.abs_img_folder)

    def get_existing_files(self):
        return [f for f in os.listdir(self.abs_img_folder)]

    def get_base_path(self):
        return url_for("flask_fileupload.static", filename=self.img_folder)

    def store(self, filename, file_data):
        filename = secure_filename(filename)
        if self.snake_case:
            filename = convert_to_snake_case(filename)

        if filename in self.get_existing_files():
            raise StorageExists()

        if self.all_allowed or any(filename.endswith('.' + x) for x in self.allowed):
            file_data.save(os.path.join(self.abs_img_folder, filename))
        else:
            raise StorageNotAllowed()

        return filename

    def delete(self, filename):
        existing_files = self.get_existing_files()
        if filename not in existing_files:
            raise StorageNotExists()
        else:
            os.remove(os.path.join(self.abs_img_folder, filename))
