# This contains our rest api; since it is a bit messy to use the @app.route
# decorator style when using application factories, all of our routes are
# inside blueprints. This is the api-facing blueprint.
#
# You can find out more about blueprints at
# http://flask.pocoo.org/docs/blueprints/

from flask import Blueprint, render_template, flash, redirect, request, Response, url_for, current_app, abort, send_from_directory
from flask_security import login_required, roles_required, current_user

from werkzeug.utils import secure_filename

from functools import wraps

from datetime import datetime

from models.user import User
from models.role import Role
from models.group import Group
from models.job import Job
from models.firmware import Firmware
from models.patch import Patch
from models.temp_profile import TempProfile
from models.result import Result
from models.log import Log
from models.config import Config
from models.evaluation import Evaluation
from models.metric import Metric
from models.scenario import Scenario
from models.protocol import Protocol

from backend.security import user_datastore
from backend.database import db

from models.jamming_pi import JammingPi
from models.jamming_scenario import JammingScenario
from models.jamming_timing import JammingTiming
from models.jamming_config import JammingConfig
from models.jamming_composition import JammingComposition

from models.layout_pi import LayoutPi
from models.layout_composition import LayoutComposition
from models.benchmark_suite import BenchmarkSuite

import json
import calendar
import holidays
import os
import base64

FIRST_JOB = 2180

rest_api = Blueprint('rest_api', __name__)


def validate_key(key):
    if (key == None):
        return False
    user = User.query.filter_by(api_key=key).first()
    if (user == None):
        return False
    if key == user.api_key:
        return True
    else:
        return False


def get_apiuser():
    key = request.args.get('key')
    return User.query.filter_by(api_key=key).first()


def check_weekend():
    wd = datetime.today().weekday()
    if (wd == 5 or wd == 6):
        return True
    else:
        return False


def check_holiday():
    h = holidays.Austria(prov='ST')
    if (datetime.today() in h):
        return True
    else:
        return False


def check_scheduler_time():
    if (check_holiday() == True):
        return True
    if (check_weekend() == True):
        return True

    db.session.commit()
    start = Config.query.filter_by(key="scheduler_time_start").first()
    stop = Config.query.filter_by(key="scheduler_time_stop").first()
    if not start == None and not stop == None:
        now = datetime.now()
        seconds_since_midnight = (
            now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()

        start_tokens = start.value.split(":")
        stop_tokens = stop.value.split(":")
        seconds_start = (
            int(start_tokens[2]))+(int(start_tokens[1])*60)+(int(start_tokens[0])*3600)
        seconds_stop = (
            int(stop_tokens[2]))+(int(stop_tokens[1])*60)+(int(stop_tokens[0])*3600)
        if(seconds_stop > seconds_start):
            if(seconds_since_midnight > seconds_start and seconds_since_midnight < seconds_stop):
                return True
            else:
                return False

        if(seconds_stop < seconds_start):
            if(seconds_since_midnight < seconds_start and seconds_since_midnight > seconds_stop):
                return False
            else:
                return True

        if(seconds_stop == seconds_start):
            return False

    return True  # assuming we can run if no timelimit is set


def maintenance_mode(user):
    if user.has_role("admins"):
        return False
    return Config.get_bool("maintenance", True)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower(
           ) in current_app.config['ALLOWED_EXTENSIONS']

# The actual decorator function


def require_appkey(view_function):
    @wraps(view_function)
    # the new, post-decoration function. Note *args and **kwargs here.
    def decorated_function(*args, **kwargs):
        if request.args.get('key') and validate_key(request.args.get('key')):
            return view_function(*args, **kwargs)
        else:
            abort(401)
    return decorated_function


@rest_api.route("/")
def api_landing():
    return "this is the api root"


def res_to_dict(r):
    line = {}
    line['begin'] = timestamp = str(calendar.timegm(r.begin.utctimetuple()))
    line['end'] = timestamp = str(calendar.timegm(r.end.utctimetuple()))
    return line


def job_to_dict(j):
    line = {}
    line['id'] = j.id
    line['name'] = j.name
    line['description'] = j.description
    line['schduled'] = str(calendar.timegm(j.scheduled.utctimetuple()))
    if (j.jamming_composition):
        #line['jamming'] = int(j.jamming_composition.short)
        line['jamming'] = j.jamming_composition.short
    if j.protocol:
        line['protocol'] = int(j.protocol.id)
    if j.layout:
        line['layout'] = int(j.layout.short)
    if j.traffic_load:
        line['periodicity'] = int(j.traffic_load)
    if j.msg_len:
        line['message_length'] = int(j.msg_len)
    line['failed'] = bool(j.failed)
    line['running'] = bool(j.running)
    line['finished'] = bool(j.finished)
    line['patching'] = bool(j.patch)
    line['evaluated'] = bool(j.evaluated)
    if(not j.result == None):
        line['result'] = res_to_dict(j.result)
    return line


def metric_to_dict(m):
    line = {}
    line['reliability'] = m.reliability
    line['latency'] = m.latency
    line['energy'] = m.energy
    return line


def scenario_to_dict(s, u):
    line = {}
    line['Source node(s)'] = s.source
    line['Destination node(s)'] = s.destination
    line['GPIO pin'] = s.gpio
    for e in s.evaluation:
        if(e.public == True) or u.has_role('admins'):
            line[e.key] = e.value
    return line


def jamming_config_to_dict(c):
    line = {}
    line['id'] = str(c.id)
    line['channel'] = str(c.channel)
    line['power'] = str(c.power)
    line['periode'] = str(c.periode)
    line['length'] = str(c.length)
    return line


def jamming_timing_to_dict(t):
    line = {}
    line['id'] = str(t.id)
    line['timestamp'] = str(t.timestamp)
    line['config'] = jamming_config_to_dict(t.config)
    return line


def jamming_scenario_to_dict(s):
    line = {}
    line['id'] = str(s.id)
    tmp = []
    for t in s.timings:
        tmp.append(jamming_timing_to_dict(t))
    line["timestamps"] = tmp
    return line


def jamming_scenario_to_csv(s):
    line = ""
    for i, t in enumerate(s.timings):
        line += "{0},{1},{2},{3},{4}\n".format(
            t.timestamp*1000000, t.config.channel, t.config.power, t.config.periode, t.config.length)
    line = line.rstrip()
    return line


@rest_api.route("/queue/adv")
@rest_api.route("/queue/adv/<int:limit>")
@require_appkey
def list_adv_queue(limit=None):
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)
    filters=request.args.to_dict()
    jobs = Job.query.filter_by(group=user.group).order_by(Job.id.desc())
    del filters["key"]
    for f in filters:
        jobs = jobs.filter(getattr(Job, f).contains(filters[f]))
    #jobs = jobs.filter_by(**filters)
    if not limit==None:
        jobs = jobs.limit(limit).all()
    else:
        jobs = jobs.all()
    res = []
    for j in jobs:
        res.append(job_to_dict(j))
    return json.dumps(res)

@rest_api.route("/queue")
@require_appkey
def list_queue():
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    jobs = Job.query.filter_by(group=user.group).order_by(Job.id.desc()).all()
    res = []
    for j in jobs:
        res.append(job_to_dict(j))
    return json.dumps(res)


@rest_api.route("/queue/<int:job_id>",methods=['GET'])
@require_appkey
def list_job(job_id):
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    if(user.has_role('admins')):
        job = Job.query.filter_by(id=job_id).order_by(Job.id.desc()).first()
    else:
        job = Job.query.filter_by(group=user.group).filter_by(
            id=job_id).order_by(Job.id.desc()).first()
    if job == None:
        abort(404)

    res = job_to_dict(job)
    return json.dumps(res)


@rest_api.route("/queue/<int:job_id>",methods=['DELETE'])
@require_appkey
def delete_job(job_id):
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    if(user.has_role('admins')):
        job = Job.query.filter_by(id=job_id).order_by(Job.id.desc()).first()
    else:
        job = Job.query.filter_by(group=user.group).filter_by(
            id=job_id).order_by(Job.id.desc()).first()
    if job == None:
        abort(404)
    res = job_to_dict(job)

    if (job.finished == True):
        abort(400)

    if (job.running == True):
        abort(400)

    res = job_to_dict(job)

    patches = Patch.query.filter_by(job_id=job.id).delete()
    metrics = Metric.query.filter_by(job_id=job.id).delete()
    results = Result.query.filter_by(job_id=job.id).delete()
    scenarios = Metric.query.filter_by(job_id=job.id)
    for s in scenarios:
        evaluations = Evaluation.queue.filter_by(
            scenario_id=s.id).delete
    scenarios.delete()
    logs = Log.query.filter_by(job_id=job.id).delete()

    db.session.delete(job)
    db.session.commit()

    return json.dumps(res)


@rest_api.route("/queue/logs/<int:job_id>")
@require_appkey
def download_logs(job_id):
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    job = Job.query.filter_by(id=job_id).first()
    if job == None:
        abort(404)
    dl_dir = current_app.config['LOGFILE_FOLDER']+"/"+str(job_id)
    if dl_dir == None:
        abort(404)
    if (user.has_role("admins") or job.group_id == user.group_id):
        return send_from_directory(directory=dl_dir, filename='logs.zip', as_attachment=True, attachment_filename='logs_'+str(job_id)+".zip")
    else:
        abort(401)


@rest_api.route("/metric/adv")
@rest_api.route("/metric/adv/<int:limit>")
@require_appkey
def list_adv_metrics(limit=None):
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    start = request.args.get('start')
    stop = request.args.get('stop')

    filters=request.args.to_dict()
    del filters["key"]
 
    metrics = Metric.query.filter(Metric.job.has(Job.group_id==user.group_id)).order_by(Metric.id.desc())
    if not start == None:
        start = datetime.fromtimestamp(int(start))
        metrics = metrics.filter(Metric.job.has(Job.result.has(Result.begin>=start)))
        del filters["start"]

    if not stop == None:
        stop = datetime.fromtimestamp(int(stop))
        metrics = metrics.filter(Metric.job.has(Job.result.has(Result.begin<=stop)))
        del filters["stop"]

    for f in filters:
        metrics = metrics.filter(Metric.job.has(getattr(Job, f).contains(filters[f])))

    if not limit==None:
        metrics = metrics.limit(limit)
    else:
        metrics = metrics

    res=[]
    for metric in metrics.all():
        res.append({"job":job_to_dict(metric.job),"metric":metric_to_dict(metric)})
    return json.dumps(res)


@rest_api.route("/metric")
@require_appkey
def list_metrics():
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    start = request.args.get('start')
    stop = request.args.get('stop')

    name = request.args.get('name')
 
    metrics = Metric.query.filter(Metric.job.has(Job.group_id==user.group_id)).order_by(Metric.id.desc())
    if not name == None:
        metrics = metrics.filter(Metric.job.has(Job.name.like(name)))
    if not start == None:
        start = datetime.fromtimestamp(int(start))
        metrics = metrics.filter(Metric.job.has(Job.result.has(Result.begin>=start)))
    if not stop == None:
        stop = datetime.fromtimestamp(int(stop))
        metrics = metrics.filter(Metric.job.has(Job.result.has(Result.begin<=stop)))

    res=[]
    for metric in metrics.all():
        res.append({"job":job_to_dict(metric.job),"metric":metric_to_dict(metric)})
    return json.dumps(res)


@rest_api.route("/metric/<int:job_id>")
@require_appkey
def list_metric(job_id):
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    if (not user.has_role('admins')) and job_id < FIRST_JOB:
        abort(403)
 
    metric = Metric.query.filter_by(job_id=job_id).order_by(Metric.id.desc()).first()

    if metric == None:
        abort(404)
    res = metric_to_dict(metric)
    return json.dumps(res)


@rest_api.route("/scenario/<int:job_id>")
@require_appkey
def list_scenarios(job_id):
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    if (not user.has_role('admins')) and job_id < FIRST_JOB:
        abort(403)

    scenarios = Scenario.query.filter_by(job_id=job_id).all()

    if scenarios == None:
        abort(404)
    res = []

    job = Job.query.filter_by(id=job_id).first()
    if job.group.id==user.group.id:
        jd=job_to_dict(job)
    else:
        jd="hidden"

    for scenario in scenarios:
        res.append(scenario_to_dict(scenario, user))
    #return json.dumps({"job":jd,"results":res})
    return json.dumps(res)


@rest_api.route('/queue/create_job', methods=['POST'])
@require_appkey
def create_job():
    user = get_apiuser()
    if maintenance_mode(user):
        abort(503)

    data = request.json
    if (data == None):
        abort(400)

    if 'file' in data:
        ihex_file = base64.b64decode(data['file'])
    else:
        abort(400)

    if 'name' in data:
        name = data['name']
    else:
        abort(400)

    if 'description' in data:
        description = data['description']
    else:
        description = ""

    if 'priority' in data:
        priority = data['priority']
    else:
        priority = False

    if 'duration' in data:
        duration = data['duration']
    else:
        duration = 180

    if 'protocol' in data:
        protocol = data['protocol']
    else:
        abort(400)

    if 'layout' in data:
        layout = data['layout']
    else:
        abort(400)

    if 'periodicity' in data:
        periodicity = data['periodicity']
    else:
        abort(400)

    if 'message_length' in data:
        message_length = data['message_length']
    else:
        abort(400)

    if 'patching' in data:
        patch = data['patching']
    else:
        patch = True

    cpatch = False
    cfile = None
    if "xml" in data:
        cfile = base64.b64decode(data['xml'])
        cpatch = True

    temp_profile = False
    if "temp_profile" in data:
        temp_profile_file = base64.b64decode(data['temp_profile'])
        temp_profile = True

    cjson = None
    if "overrides" in data:
        cjson = data['overrides']
        cpatch = True

    if "config_overrides" in data:
        cojson = data['config_overrides']
    else:
        cojson = None

    if 'jamming' in data:
        jamming = data['jamming']
    else:
        jamming = 0

    if 'logs' in data:
        logs = data['logs']
    else:
        logs = False

    jamming_option = Config.get_bool("jamming_available")
    jamming_option_user=not user.has_role("nojamming")
    jamming_option = jamming_option and jamming_option_user

    max_duration = Config.get_int("max_duration", 36000)
    if user.has_role("admins") or user.has_role("privileged"):
        max_duration = 86400

    if(jamming_option == False and not jamming == 0 and not user.has_role("admins")):
        print("bad jamming")
        abort(400)

    jammings = JammingComposition.query
    if not (user.has_role("admins")):
        jammings = jammings.filter_by(public=True)

    jam = jammings.filter_by(short=str(jamming)).first()
    if(jam == None):
        print("jamming not found")
        abort(400)

    if(priority == True and not (user.has_role("admins") or user.has_role("privileged"))):
        print("not allowed")
        abort(400)

    prot = Protocol.query.filter_by(id=int(protocol)).first()
    if prot==None:
        print("protocol not found")
        abort(400)

    if not (prot.group.id==user.group.id or user.has_role("admins")):
        print("not your protocol")
        abort(401)

    bs = prot.benchmark_suite
    if (bs == None):
        print("not a valid benchmark suite on your protocol")
        abort(400)

    comp = LayoutComposition.query.filter_by(
        short=layout).filter_by(benchmark_suite_id=bs.id).first()
    if(comp == None):
        print("bad layout")
        abort(400)

    if(not (message_length == 8 or message_length == 32 or message_length == 64 or user.has_role("admins") or user.has_role("privileged"))):
        print("bad message thing")
        abort(400)

    #MALLI
    #if(not (periodicity == 0 or periodicity == 5000 or periodicity == 30000)):
    #    abort(400)

    if(not (patch == True or patch == False)):
        print("patch bad")
        abort(400)

    if(duration < 120 or duration > max_duration):
        print("duration bad")
        abort(400)

    if cpatch and (cfile == None or cjson == None):
        print("custom patch bad")
        abort(400)

    elif cpatch and len(cfile) <= 0:
        print("custom very bad")
        abort(400)

    if temp_profile and not (user.has_role("admins") or user.has_role("templab")):
        print("templab access is limited")
        abort(400)

    if temp_profile and not "Nordic" in bs.node.name:
        print("templab can only be used with nrf nodes")
        abort(400)

    if len(ihex_file) > 0:
        upload_name = "via API"

###########
# TODO
# function int upload(string uploadname,bool logs,bool reboot,int baudrate, int duration, user and or group)
###########
        upload_dir = os.path.join(os.path.abspath(
            current_app.config['UPLOAD_FOLDER']))
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        dt = datetime.utcnow()
        timestamp = calendar.timegm(dt.utctimetuple())

        if(logs):
            logstring = "1"
        else:
            logstring = "0"

        baudrate = 115200
        rebootstring = 0

        filename = "%s_%s_%d_%s_%d_%s_%d.ihex" % (
            timestamp, user.group.name, duration, logstring, baudrate, rebootstring, jamming)

        filepath = os.path.join(upload_dir, filename)
        with open(filepath, 'w') as f:
            f.write(ihex_file.decode())

        fw = Firmware.query.filter_by(filename=filename).first()
        if(not fw == None):
            print("invalid firmware")
            abort(400)

        job = Job(name, description, dt, logs, priority, duration, prot.group.id, 
                periodicity, message_length, jam.id, comp.id, prot.id, patch)

        db.session.add(job)
        db.session.commit()

        firmware = Firmware(upload_name, filename, job.id)
        db.session.add(firmware)
        db.session.commit()

        if(cpatch):
            patch_upload_name = "via API"
            patch_filename = "patch_{0}.xml".format(job.id)
            patch_upload_dir = os.path.join(
                os.path.abspath(current_app.config['PATCH_FOLDER']))

            if not os.path.exists(patch_upload_dir):
                os.makedirs(patch_upload_dir)

            patch_filepath = os.path.join(patch_upload_dir, patch_filename)
            with open(patch_filepath, 'w') as f:
                f.write(cfile.decode())

            patch_db = Patch(patch_upload_name, patch_filename, job.id)
            db.session.add(patch_db)
            job.overrides = json.dumps(cjson)
            db.session.commit()

        if(not cojson == None):
            job.config_overrides = json.dumps(cojson)
            db.session.commit()

        if(temp_profile):
            profile_upload_name = "via API"
            profile_filename = "templab_{0}.csv".format(job.id)
            profile_upload_dir = os.path.join(
                os.path.abspath(current_app.config['TEMPLAB_FOLDER']))

            if not os.path.exists(profile_upload_dir):
                os.makedirs(profile_upload_dir)
   
            profile_filepath = os.path.join(profile_upload_dir, profile_filename)
            with open(profile_filepath, 'w') as f:
                f.write(temp_profile_file.decode())

            profile_db = TempProfile(profile_upload_name, profile_filename, job.id)
            db.session.add(profile_db)
            db.session.commit()

        return json.dumps(job_to_dict(job))
    else:
        abort(400)


@rest_api.route("/status")
def get_status():
    j = Job.query.filter_by(running=True).first()
    d = {}
    if not (j is None):
        d["status"] = "running"
        if j.jamming_composition == None:
            d["jamming"] = "unavailable"
        else:
            d["jamming"] = j.jamming_composition.short

    else:
        t = check_scheduler_time()
        if(t == True):
            d["status"] = "ready"
        else:
            d["status"] = "offline"
    return json.dumps(d)


@rest_api.route("/layout/<int:job_id>/cmd/<rpi>")
def get_layout_cmd(job_id, rpi):
    cmd = ""
    j = Job.query.filter_by(id=job_id).first()
    if(j == None):
        return "/bin/false"

    lc = LayoutComposition.query.filter_by(id=j.layout_composition_id).first()
    if lc == None:
        return "/bin/false"

    lp = LayoutPi.query.filter_by(
        composition_id=lc.id).filter_by(rpi=rpi).first()
    if lp == None:
        lp = LayoutPi.query.filter_by(
            composition_id=lc.id).filter_by(rpi="default").first()
        if lp == None:
            return "/bin/true"

    if lp.role == "source":
        per = " -i" + str(j.traffic_load)
    else:
        per = ""

    return str(lp.command) + " -l" + str(j.msg_len) + per


@rest_api.route("/jamming/<int:job_id>/csv/<rpi>")
def get_jamming_csv(job_id, rpi):
    csv = ""
    j = Job.query.filter_by(id=job_id).first()
    jc = JammingComposition.query.filter_by(
        id=j.jamming_composition_id).first()
    jp = JammingPi.query.filter_by(
        composition_id=jc.id).filter_by(rpi=rpi).first()
    if jp == None:
        jp = JammingPi.query.filter_by(
            composition_id=jc.id).filter_by(rpi="default").first()
        if jp == None:
            return ""
    csv = jamming_scenario_to_csv(jp.scenario)
    return csv


@rest_api.route("/jamming/<int:job_id>/options/<rpi>")
def get_jamming_options(job_id, rpi):
    opt = ""
    j = Job.query.filter_by(id=job_id).first()
    jc = JammingComposition.query.filter_by(
        id=j.jamming_composition_id).first()
    jp = JammingPi.query.filter_by(
        composition_id=jc.id).filter_by(rpi=rpi).first()
    if jp == None:
        jp = JammingPi.query.filter_by(
            composition_id=jc.id).filter_by(rpi="default").first()
        if jp == None:
            return ""
    if(jp.sync):
        opt += "-s "
    if(jp.relative):
        opt += "-r "

    return opt
