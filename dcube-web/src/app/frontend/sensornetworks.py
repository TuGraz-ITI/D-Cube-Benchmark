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
from flask import Blueprint, redirect, request, render_template, current_app, url_for, flash
from flask_security import login_required, roles_required, current_user
from werkzeug.utils import secure_filename

from .helpers import *

from models.user import User
from models.group import Group

from models.job import Job
from models.firmware import Firmware
from models.log import Log

from backend.database import db
from backend.security import user_datastore

from .frontend import maintenance_mode

import calendar
import os

sensornetworks = Blueprint('sensornetworks', __name__)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower(
           ) in current_app.config['ALLOWED_EXTENSIONS']


@sensornetworks.route('/permission')
@roles_required("admins")
def users():
    users = User.query.all()
    groups = Group.query.all()
    return render_template('sensornetworks/users.html', users=users, groups=groups)


@sensornetworks.route('/permission/<int:id>/<int:permission>')
@roles_required("admins")
def promote_user(id=None, permission=None):
    if(id == None):
        flash('Missing Data!', 'error')
    else:
        user = User.query.filter_by(id=id).first()
        if(user == None):
            flash('User does not exist!', 'error')
        else:
            sn = user_datastore.find_or_create_role(name="sensornetworks")
            if sn == None:
                flash('Group not found!!', 'error')
            else:
                if(permission == 1):
                    user_datastore.add_role_to_user(user, "sensornetworks")
                    flash('User ' + user.username +
                          ' is now in sensornetworks!', 'success')
                    db.session.commit()
                elif(permission == 0):
                    user_datastore.remove_role_from_user(
                        user, "sensornetworks")
                    flash('User ' + user.username +
                          ' is no longer in sensornetworks!', 'success')
                    db.session.commit()
                else:
                    flash('Invalid permission parameter!', 'error')
    return redirect(url_for('sensornetworks.users'))


@sensornetworks.route('/queue/')
@roles_required("sensornetworks")
def show_queue():
    page = (request.args.get('page'))
    if page == None:
        page = -1
    else:
        page = int(page, 10)
    return show_queue_page(page)


@sensornetworks.route('/queue/log/')
@sensornetworks.route('/queue/log/<int:id>')
@roles_required("sensornetworks")
def show_log(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))
    log = Log.query.filter_by(job_id=id).order_by(Log.id.desc()).first()
    if log == None:
        abort(404)
    if (current_user.is_authenticated and (current_user.has_role("admins") or log.job.group_id == current_user.group_id)):
        return render_template('sensornetworks/view_log.html', log=log)
    else:
        abort(401)


@sensornetworks.route('/queue/<int:page>')
@roles_required("sensornetworks")
def show_queue_page(page=-1):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    if(page == -1):
        jobs = Job.query.filter_by(group=current_user.group).filter_by(
            node="Anchor-North").order_by(Job.id.desc()).paginate(1, 50)
    else:
        jobs = Job.query.filter_by(group=current_user.group).filter_by(
            node="Anchor-North").order_by(Job.id.desc()).paginate(page, 50)

    scheduler_running = check_scheduler_time()
    scheduler_start = Config.get_string("scheduler_time_start", "?")
    scheduler_stop = Config.get_string("scheduler_time_stop", "?")

    return render_template('sensornetworks/queue.html', jobs=jobs)


@sensornetworks.route('/queue/create_job', methods=['POST'])
@roles_required("sensornetworks")
def create_job():
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    name = (request.form['name'])
    description = (request.form['description'])
    node = "Anchor-North"

    # check if the post request has the file part
    if (('file' not in request.files) or name == None):
        flash('Missing Data!', 'error')
        return redirect(url_for('sensornetworks.show_queue'))

    file = request.files['file']
    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        flash('No file!', 'error')
        return redirect(url_for('sensornetworks.show_queue'))

    if file and allowed_file(file.filename):
        upload_name = secure_filename(file.filename)
        upload_dir = os.path.join(os.path.abspath(
            current_app.config['UPLOAD_FOLDER']))
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        dt = datetime.utcnow()
        timestamp = calendar.timegm(dt.utctimetuple())

        logstring = "0"

        filename = "%s_%s_%s_%s_%s_%s_%s.ihex" % (
            timestamp, current_user.group.name, 0, 0, 115200, 0, 0)

        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        job = Job(name, description, dt, None, False, True, 0,
                  current_user.group.id, node, None, None, None, None, False)
        db.session.add(job)
        db.session.commit()

        firmware = Firmware(upload_name, filename, job.id)
        db.session.add(firmware)
        db.session.commit()

        flash('Job ' + name + " created!", 'success')
        return redirect(url_for('sensornetworks.show_queue'))
    else:
        flash('Illegal filetype!', 'error')
        return redirect(url_for('sensornetworks.show_queue'))
