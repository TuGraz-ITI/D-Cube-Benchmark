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

