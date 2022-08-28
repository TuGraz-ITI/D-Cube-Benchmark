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
from flask import Blueprint, render_template, flash, redirect, request, url_for
from .forms import UploadForm
from .storage import StorageNotAllowed, StorageExists, StorageNotExists
from flask_security import login_required, roles_required, current_user


def create_blueprint(import_name, app, storage, static_folder):

    bp = Blueprint("flask_fileupload", import_name,
                   template_folder="templates",
                   static_folder=static_folder,
                   static_url_path="/static",
                   )

    @bp.route("/", methods=["GET", "POST"])
    @roles_required("admins")
    def upload():
        form = UploadForm()
        if form.validate_on_submit():
            try:
                filename = storage.store(form.upload_name.data, form.upload_img.data)
            except (StorageNotAllowed, StorageExists) as e:
                flash(str(e), category="danger")
                return redirect(request.url)
            else:
                flash("Image saved: " + filename, category="info")

            return redirect(request.url)

        return render_template("fileupload/upload.html", form=form)

    @bp.route("/delete/<filename>", methods=["GET"])
    @roles_required("admins")
    def upload_delete(filename):
        try:
            storage.delete(filename)
            flash("File removed: " + filename, category="info")
        except StorageNotExists as e:
            flash(str(e))

        return redirect(url_for("flask_fileupload.upload"))

    return bp

