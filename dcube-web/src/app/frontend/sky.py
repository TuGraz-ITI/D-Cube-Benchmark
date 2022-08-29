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
from flask import Blueprint, redirect, request, render_template, current_app, url_for, flash, send_from_directory, abort
from flask_security import login_required, roles_required, current_user
from werkzeug.utils import secure_filename

from .helpers import *

from models.user import User
from models.role import Role
from models.group import Group

from models.job import Job
from models.firmware import Firmware
from models.scenario import Scenario
from models.metric import Metric
from models.log import Log
from models.patch import Patch
from models.result import Result

from models.jamming_pi import JammingPi
from models.jamming_scenario import JammingScenario
from models.jamming_timing import JammingTiming
from models.jamming_config import JammingConfig
from models.jamming_composition import JammingComposition

from models.layout_pi import LayoutPi
from models.layout_composition import LayoutComposition

from models.benchmark_suite import BenchmarkSuite
from models.protocol import Protocol
from models.node import Node

from backend.database import db
from backend.security import user_datastore

from .frontend import maintenance_mode, frontend

import calendar
import os

MODULE_NAME = "sky"
sky = Blueprint(MODULE_NAME, __name__)

JOB_OVERHEAD = 120


@sky.before_app_first_request
def setup_defaults():
    db.create_all()
    role = user_datastore.find_role(MODULE_NAME)
    if(role is None):
        role = user_datastore.find_or_create_role(name=MODULE_NAME)
        db.session.add(role)
        db.session.commit()


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower(
           ) in current_app.config['ALLOWED_EXTENSIONS']


@sky.route('/permission')
@roles_required("admins")
def users():
    users = User.query.all()
    groups = Group.query.all()
    return render_template(
        'base/users.html', module=MODULE_NAME, users=users, groups=groups)


@sky.route('/permission/<int:id>/<int:permission>')
@roles_required("admins")
def promote_user(id=None, permission=None):
    if(id is None):
        flash('Missing Data!', 'error')
    else:
        user = User.query.filter_by(id=id).first()
        if(user is None):
            flash('User does not exist!', 'error')
        else:
            sn = user_datastore.find_or_create_role(name="sky")
            if sn is None:
                flash('Group not found!!', 'error')
            else:
                if(permission == 1):
                    user_datastore.add_role_to_user(user, "sky")
                    flash('User ' + user.username +
                          ' is now in sky!', 'success')
                    db.session.commit()
                elif(permission == 0):
                    user_datastore.remove_role_from_user(user, "sky")
                    flash('User ' + user.username +
                          ' is no longer in sky!', 'success')
                    db.session.commit()
                else:
                    flash('Invalid permission parameter!', 'error')
    return redirect(url_for('sky.users'))


@sky.route('/queue/')
@login_required
def show_queue():
    page = (request.args.get('page'))
    if page is None:
        page = -1
    else:
        page = int(page, 10)
    return show_queue_page(page)


@sky.route('/queue/<int:page>')
@login_required
def show_queue_page(page=-1):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    jobs = Job.query.filter_by(group=current_user.group).filter(Job.protocol.has(Protocol.benchmark_suite.has(BenchmarkSuite.node.has(Node.name.contains("Sky-")))))
    protocol=None

    if("protocol" in request.args):
        pid = (request.args.get('protocol'))
        pid = int(pid) 
        protocol = Protocol.query.filter_by(id=pid).first()
        if(protocol):
            jobs=jobs.filter(Job.protocol.has(Protocol.id==pid))

    if(page == -1):
        jobs = jobs.order_by(Job.id.desc()).paginate(1, 50)
    else:
        jobs = jobs.order_by(Job.id.desc()).paginate(page, 50)

    jammings = JammingComposition.query
    if not (current_user.has_role("admins")):
        jammings = jammings.filter_by(public=True)
    jammings = jammings.all()

    jamming_option = Config.get_bool("jamming_available")
    #TODO: put into autgenerated roles
    jamming_option_user=not current_user.has_role("nojamming")
    jamming_option = jamming_option and jamming_option_user

    # jamming_max=Config.get_int("jamming_max",1)
    max_duration = Config.get_int("max_duration", 36000)
    if current_user.has_role("admins"):
        max_duration = 36000

    j = Job.query.filter_by(finished=False)
    est = 0.0
    for job in j:
        est += ((job.duration + JOB_OVERHEAD) / 60.0)

    layout_categories = BenchmarkSuite.query.all()
    layout_compositions = LayoutComposition.query.all()

    durations_string = Config.get_string("durations", "30 60 120 180 300")
    durations = map(int, durations_string.split())

    default_duration = Config.get_int("def_duration", 300)

    protocols = Protocol.query.filter_by(group_id=current_user.group_id).filter(
            Protocol.benchmark_suite.has(BenchmarkSuite.node.has(Node.name.contains("Sky-")))).all()

    return render_template('base/queue.html', 
                           module=MODULE_NAME,
                           jobs=jobs,
                           jamming_option=jamming_option,
                           max_duration=max_duration,
                           jammings=jammings,
                           est=est,
                           durations=durations,
                           default_duration=default_duration,
                           layout_compositions=layout_compositions,
                           layout_categories=layout_categories,
                           protocols=protocols,
                           protocol=protocol
                           )


@sky.route('/queue/log/')
@sky.route('/queue/log/<int:id>')
@login_required
def show_log(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))
    log = Log.query.filter_by(job_id=id).order_by(Log.id.desc()).first()
    if log is None:
        abort(404)
    if (current_user.is_authenticated and (current_user.has_role(
            "admins") or log.job.group_id == current_user.group_id)):
        return render_template('base/view_log.html',
                               module=MODULE_NAME, log=log)
    else:
        abort(401)


@sky.route('/queue/download_evaluation/<int:id>')
@login_required
def download_job_evaluation(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))
    job = Job.query.filter_by(id=id).first()
    if job is None:
        abort(404)
    dl_dir = current_app.config['EVALUATION_FOLDER']
    if dl_dir is None:
        abort(404)
    if (current_user.is_authenticated and (current_user.has_role(
            "admins") or (job.group_id == current_user.group_id))):
        return send_from_directory(directory=dl_dir, path='report_' + str(
            id) + '.pdf', as_attachment=True, download_name='report_' + str(id) + ".pdf")
    else:
        abort(401)


@sky.route('/queue/download_logs/<int:id>')
@login_required
def download_job_logs(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))
    job = Job.query.filter_by(id=id).first()
    if job is None:
        abort(404)
    dl_dir = current_app.config['LOGFILE_FOLDER'] + "/" + str(id)
    if dl_dir is None:
        abort(404)
    if (current_user.is_authenticated and (current_user.has_role(
            "admins") or job.group_id == current_user.group_id)):
        return send_from_directory(directory=dl_dir, path='logs.zip',
                                   as_attachment=True, download_name='logs_' + str(id) + ".zip")
    else:
        abort(401)


@sky.route('/queue/details/<int:id>')
@login_required
def show_details(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))
    job = Job.query.filter_by(id=id).first()
    if job is None:
        abort(404)

    if not (current_user.group.id==job.group.id or current_user.has_role("admins")):
        abort(401)

    scenarios = Scenario.query.filter_by(job_id=id).all()

    report = False
    dl_dir = current_app.config['EVALUATION_FOLDER']
    if not dl_dir is None:
        rep = os.path.abspath(
            os.path.join(
                dl_dir,
                'report_' +
                str(id) +
                '.pdf'))
        if(os.path.isfile(rep)):
            report = True

    metrics = None
    metrics = Metric.query.filter_by(job_id=id).first()
    leaderboard = Config.get_bool("leaderboard", False)
    return render_template('base/details.html', module=MODULE_NAME, job=job,
                           scenarios=scenarios, metrics=metrics, leaderboard=leaderboard, report=report)


@sky.route('/queue/create_job', methods=['POST'])
@roles_required("sky")
def create_job():
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    name = (request.form['name'])
    duration = (request.form['duration'])
    logs = ("logs" in (request.form))
    if("baudrate" in (request.form)):
        baudrate_str = (request.form['baudrate'])
    else:
        baudrate_str = None
    priority = ("priority" in (request.form))
    patch = ("patch" in (request.form))
    description = (request.form['description'])
    node = "Sky-All"

    node_placement_str = (request.form['node_placement'])
    traffic_load_str = (request.form['traffic_load_time'])
    msg_len_str = (request.form['traffic_load_len'])

    if(not (node_placement_str is None)):
        node_placement = LayoutComposition.query.filter_by(
            id=int(node_placement_str)).first()
        if node_placement is None:
            flash(
                'Unknown node placement ' +
                node_placement_str +
                '!',
                'error')
            return redirect(url_for('sky.show_queue'))
    else:
        flash('No node placement selected!', 'error')
        return redirect(url_for('sky.show_queue'))

    if(not (traffic_load_str is None)):
        traffic_load = int(traffic_load_str)
        if not (traffic_load == 0 or traffic_load ==
                5000 or traffic_load == 30000):
            flash('Invalid traffic load ' + traffic_load_str + '!', 'error')
            return redirect(url_for('sky.show_queue'))
    else:
        flash('No traffic load selected!', 'error')
        return redirect(url_for('sky.show_queue'))

    if(not (msg_len_str is None)):
        msg_len = int(msg_len_str)
        if not (msg_len == 8 or msg_len == 32 or msg_len == 64):
            flash('Invalid message length  ' + msg_len_str + '!', 'error')
            return redirect(url_for('sky.show_queue'))
    else:
        flash('No message length selected!', 'error')
        return redirect(url_for('sky.show_queue'))

    jamming_option = Config.get_bool("jamming_available")
    max_duration = Config.get_int("max_duration", 36000)
    if current_user.has_role("admins"):
        max_duration = 36000

    jamming_option_user=not current_user.has_role("nojamming")
    jamming_option = jamming_option and jamming_option_user

    jamming_str = (request.form['jamming'])

    if(jamming_option == False and not jamming_str == "None" and not current_user.has_role("admins")):
        flash('Jamming has been disabled!', 'error')
        return redirect(url_for('sky.show_queue'))

    jammings = JammingComposition.query
    if not (current_user.has_role("admins")):
        jammings = jammings.filter_by(public=True)

    jamming_composition = jammings.filter_by(name=jamming_str).first()
    if(jamming_composition is None):
        flash('Unknown jamming configuration ' + jamming_str + '!', 'error')
        return redirect(url_for('sky.show_queue'))

    if(not (baudrate_str is None)):
        baudrate = int(baudrate_str, 10)

        if(not (baudrate == 9600 or baudrate == 115200)):
            flash('Invalid baudrate configuration!', 'error')
            return redirect(url_for('sky.show_queue'))
    else:
        baudrate = 115200

    if(priority == True and not (current_user.has_role("admins") or current_user.have("privileged")) ):
        flash('You do not have permissions to create priority jobs!', 'error')
        return redirect(url_for('sky.show_queue'))

    if(not node == "Sky-All" and not current_user.has_role("admins")):
        flash('You do not have permission to run jobs on other nodes!', 'error')
        return redirect(url_for('sky.show_queue'))

    try:
        durationint = int(duration, 10)
    except ValueError:
        flash('Invalid duration!', 'error')
        return redirect(url_for('sky.show_queue'))

    if(durationint < 20 or durationint > max_duration):
        flash('Invalid duration value!', 'error')
        return redirect(url_for('sky.show_queue'))

    if (('file' not in request.files) or name is None or duration is None):
        flash('Missing Data!', 'error')
        return redirect(url_for('sky.show_queue'))

    cpatch = ("cpatch" in (request.form))
    if cpatch and ("cfile" not in request.files):
        flash('XML file required with custom patching!', 'error')
        return redirect(url_for('sky.show_queue'))
    if cpatch:
        cfile = request.files['cfile']
        if cfile.filename == '':
            flash('XML file required with custom patching!', 'error')
            return redirect(url_for('sky.show_queue'))
        cjson = (request.form['cjson'])
        if (cjson is None):
            flash('Missing JSON Data!', 'error')
            return redirect(url_for('sky.show_queue'))

    if 'protocol' in request.form:
        protocol_id = (request.form['protocol'])
        protocol_id=int(protocol_id)
        protocol = Protocol.query.filter(Protocol.id==protocol_id).first()

        if protocol == None:
            flash('Invalid Protocol!', 'error')
            return redirect(url_for('sky.show_queue'))
    else:
        flash("Missing Protocol data!","error")
        return redirect(url_for('sky.show_queue'))

    file = request.files['file']
    if file.filename == '':
        flash('No file!', 'error')
        return redirect(url_for('sky.show_queue',protocol=protocol.id))

    if file and allowed_file(file.filename):
        upload_name = secure_filename(file.filename)
        upload_dir = os.path.join(os.path.abspath(
            current_app.config['UPLOAD_FOLDER']))
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        dt = datetime.utcnow()

        firmware = Firmware(upload_name, None, None)
        db.session.add(firmware)
        db.session.flush()

        filename = "firmware_%s.hex" % firmware.id
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        firmware.filename = filename

        job = Job(name, description, dt, logs, priority, durationint, current_user.group.id,
                  traffic_load, msg_len, jamming_composition.id, node_placement.id, protocol.id, patch)
        db.session.add(job)
        db.session.flush()

        firmware.job_id = job.id
        db.session.commit()

        if(cpatch):
            patch_upload_name = secure_filename(cfile.filename)
            patch_filename = "patch_{0}.xml".format(job.id)
            patch_upload_dir = os.path.join(
                os.path.abspath(current_app.config['PATCH_FOLDER']))

            if not os.path.exists(patch_upload_dir):
                os.makedirs(patch_upload_dir)

            patch_filepath = os.path.join(patch_upload_dir, patch_filename)
            cfile.save(patch_filepath)
            patch_db = Patch(patch_upload_name, patch_filename, job.id)
            db.session.add(patch_db)
            job.overrides = cjson
            db.session.commit()

        db.session.commit()

        flash('Job ' + name + " created!", 'success')
        return redirect(url_for('sky.show_queue',protocol=protocol.id))
    else:
        flash('Illegal filetype!', 'error')
        return redirect(url_for('sky.show_queue',protocol=protocol.id))


@sky.route('/queue/delete_job/<int:id>')
@login_required
def delete_job(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    if((id is None)):
        flash('Missing Data!', 'error')
    else:
        group = current_user.group
        if(group is None):
            flash('You are not a member of any group!', 'error')
        else:
            job = Job.query.filter_by(id=id).first()
            if(job is None):
                flash('Job does not exist!', 'error')
            elif(job.group == group):
                if(job.running):
                    flash('Cannot delete a running job!', 'error')
                elif(job.finished):
                    flash('Cannot delete a finished job!', 'error')
                else:
                    patches = Patch.query.filter_by(job_id=id).delete()
                    metrics = Metric.query.filter_by(job_id=id).delete()
                    results = Result.query.filter_by(job_id=id).delete()
                    scenarios = Metric.query.filter_by(job_id=id)
                    for s in scenarios:
                        evaluations = Evaluation.queue.filter_by(
                            scenario_id=s.id).delete
                    scenarios.delete()
                    logs = Log.query.filter_by(job_id=id).delete()

                    flash('Job ' + job.name + ' deleted!', 'success')
                    db.session.delete(job)
                    db.session.commit()
            else:
                flash('The specified job does not belong to your group!', 'error')
    return redirect(url_for('sky.show_queue'))
