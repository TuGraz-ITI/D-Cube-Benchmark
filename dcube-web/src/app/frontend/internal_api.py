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
from flask import Blueprint, abort, current_app, send_from_directory

from models.job import Job
from models.firmware import Firmware
from models.config import Config

from models.jamming_pi import JammingPi
from models.jamming_scenario import JammingScenario
from models.jamming_timing import JammingTiming
from models.jamming_config import JammingConfig
from models.jamming_composition import JammingComposition

from models.layout_pi import LayoutPi
from models.layout_composition import LayoutComposition

import json
import calendar
import holidays
import os

from backend.database import db
from datetime import datetime


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


def res_to_dict(r):
    line = {}
    line['begin'] = timestamp = str(calendar.timegm(r.begin.utctimetuple()))
    line['end'] = timestamp = str(calendar.timegm(r.end.utctimetuple()))
    return line


def job_to_dict(j):
    line = {}
    line['id'] = int(j.id)
    line['name'] = str(j.name)
    line['group'] = str(j.group.name)
    line['duration'] = int(j.duration)
    line['node'] = str(j.protocol.benchmark_suite.node.name)
    line['jamming'] = int(j.jamming_composition_id)
    line['jamming_short'] = str(j.jamming_composition.short)
    line['jamming_name'] = str(j.jamming_composition.name)
    line['benchmark_suite'] = str(j.protocol.benchmark_suite.name)
    line['layout'] = int(j.layout_composition_id)
    line['firmware'] = int(j.firmware.id)
    line['periodicity'] = int(j.traffic_load)
    line['message_length'] = int(j.msg_len)
    line['patch'] = bool(j.patch)
    line['cpatch'] = bool(j.cpatch)
    line['logs'] = bool(j.logs)
    line['finished'] = bool(j.finished)
    if(not j.result == None):
        line['result'] = res_to_dict(j.result)
    line['templab'] = True if not j.temp_profile == None else False
    return line


internal_api = Blueprint('internal_api', __name__)


@internal_api.route("/denied")
def get_denied():
    abort(403)


@internal_api.route("/status")
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


@internal_api.route("/job/<int:job_id>")
def get_job(job_id):
    job = Job.query.filter_by(id=job_id).order_by(Job.id.desc()).first()
    if job == None:
        abort(404)
    res = job_to_dict(job)
    return json.dumps(res)


@internal_api.route('/firmware/<int:job_id>')
def download_firmware(job_id):
    firmware = Firmware.query.filter_by(job_id=job_id).first()

    if (firmware == None):
        abort(404)

    new_path = os.path.join(os.path.abspath(
        current_app.config['UPLOAD_FOLDER']), firmware.filename)
    new_dir = os.path.join(os.path.abspath(
        current_app.config['UPLOAD_FOLDER']))

    if os.path.isfile(new_path):
        return send_from_directory(directory=new_dir, path=firmware.filename, as_attachment=True,
                                   download_name='firmware_'+str(job_id)+".ihex")

    if ((firmware.job == None) or (firmware.job.group == None)):
        abort(404)

    abort(404)


@internal_api.route("/layout/<int:job_id>/cmd/rpi<rpi>")
@internal_api.route("/layout/<int:job_id>/cmd/<rpi>")
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

        if (j.protocol):
            cfgs=j.protocol.benchmark_suite.configs
            delay=""
            for cfg in cfgs:
                if cfg.key=="start":
                    delay = " -d" + str(cfg.value)

            try:
                co=json.loads(j.config_overrides)
                if "start" in co:
                    delay = " -d" + str(co["start"])
            except Exception:
                pass

            per += delay

    else:
        per = ""

    return str(lp.command) + " -l" + str(j.msg_len) + per


@internal_api.route("/jamming/<int:job_id>/csv/rpi<rpi>")
@internal_api.route("/jamming/<int:job_id>/csv/<rpi>")
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


@internal_api.route("/jamming/<int:job_id>/options/rpi<rpi>")
@internal_api.route("/jamming/<int:job_id>/options/<rpi>")
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

@internal_api.route("/templab/<int:job_id>/csv")
def get_templab_profile_csv(job_id):

    job = Job.query.filter_by(id=job_id).first()

    if not job == None:
        profile_filename = "templab_%d.csv" % job.id

        profile_upload_dir = os.path.join(
            os.path.abspath(current_app.config['TEMPLAB_FOLDER']))
        profile_filepath = os.path.join(profile_upload_dir, profile_filename)
        print("looking up profile_filepath")

        if os.path.isfile(profile_filepath):
            return send_from_directory(directory=current_app.config['TEMPLAB_FOLDER'], path=profile_filename, as_attachment=True,
                                       download_name="temperature.csv")
    abort(404)



@internal_api.route("/patch/custom/<int:job_id>/xml/rpi<rpi>")
@internal_api.route("/patch/custom/<int:job_id>/xml/<rpi>")
def get_custom_patch_xml(job_id, rpi):

    job = Job.query.filter_by(id=job_id).first()

    if not job == None:
        patch_filename = "patch_%d.xml" % job.id

        patch_upload_dir = os.path.join(
            os.path.abspath(current_app.config['PATCH_FOLDER']))
        patch_filepath = os.path.join(patch_upload_dir, patch_filename)

        if os.path.isfile(patch_filepath):
            return send_from_directory(directory=current_app.config['PATCH_FOLDER'], path=patch_filename, as_attachment=True,
                                       download_name="custom.xml")
    abort(404)


@internal_api.route("/patch/custom/<int:job_id>/json/rpi<rpi>")
@internal_api.route("/patch/custom/<int:job_id>/json/<rpi>")
def get_custom_patch_json(job_id, rpi):
    job = Job.query.filter_by(id=job_id).first()
    if not job == None and job.overrides:
        return job.overrides
    abort(404)


@internal_api.route("/patch/<int:job_id>/xml/rpi<rpi>")
@internal_api.route("/patch/<int:job_id>/xml/<rpi>")
def get_patch_xml(job_id, rpi):
    job = Job.query.filter_by(id=job_id).first()

    if not job == None:
        if job.protocol and "Nordic" in job.protocol.benchmark_suite.node.name:
            filename = "testbed_nordic.xml"
        elif job.protocol and "Sky" in job.protocol.benchmark_suite.node.name:
            filename = "testbed_sky.xml"
        else:
            filename = "testbed.xml"

        if not job.protocol == None:
            directory=os.path.join(current_app.static_folder,"benchmark_suites",str(job.protocol.benchmark_suite.id))
        else:
            directory=os.path.join(current_app.static_folder,"benchmark_suites")

        print("sending file %s from directory %s"%(filename,directory))
        return send_from_directory(directory=directory, path=filename, as_attachment=True,
                               download_name="testbed.xml")
    abort(404)


@internal_api.route("/patch/<int:job_id>/json/rpi<rpi>")
@internal_api.route("/patch/<int:job_id>/json/<rpi>")
def get_patch_json(job_id, rpi):
    job = Job.query.filter_by(id=job_id).first()
    patterns = LayoutPi.query.with_entities(LayoutPi.composition_id, LayoutPi.group).filter_by(
        composition_id=job.layout_composition_id).distinct()

    config = {}
    counter = 0

    config["node_id"] = int(rpi, 10)

    for p in patterns:
        if p.group == "None":
            continue

        tp = 0
        if(p.group.startswith("p2p")):
            tp = 1
        if(p.group.startswith("p2mp")):
            tp = 2
        if(p.group.startswith("mp2p")):
            tp = 3
        if(p.group.startswith("mp2mp")):
            tp = 4
        config["traffic_pattern[{0}]".format(counter)] = tp

        sources = LayoutPi.query.filter_by(
            composition_id=job.layout_composition_id, group=p.group, role="source").all()
        source_counter = 0
        for s in sources:
            config["source_id[{0}][{1}]".format(
                counter, source_counter)] = int(s.rpi)
            source_counter += 1

        destinations = LayoutPi.query.filter_by(
            composition_id=job.layout_composition_id, group=p.group, role="sink").all()
        sink_counter = 0
        for d in destinations:
            config["sink_id[{0}][{1}]".format(
                counter, sink_counter)] = int(d.rpi)
            sink_counter += 1

        config["message_length[{0}]".format(counter)] = int(job.msg_len)
        config["message_offsetH[{0}]".format(counter)] = int(0)
        config["message_offsetL[{0}]".format(counter)] = int(0)
        config["period[{0}]".format(counter)] = int(job.traffic_load)

        #TODO do not hardcode
        if (job.protocol):
            cfgs=job.protocol.benchmark_suite.configs
            for cfg in cfgs:
                if cfg.key=="delta":
                    config["delta[{0}]".format(counter)] = int(cfg.value)

                try:
                    co=json.loads(job.config_overrides)
                    if "delta" in co:
                        config["delta[{0}]".format(counter)] = int(co["delta"])
                except Exception as e:
                    pass

        #if(job.protocol and (job.protocol.benchmark_suite.id == 3 or job.protocol.benchmark_suite.id == 4 or job.protocol.benchmark_suite.id == 5 )):
        #    config["delta[{0}]".format(counter)] = int(3000)

        if(job.traffic_load == 0):
            config["upper_bound[{0}]".format(counter)] = int(30000)
            config["lower_bound[{0}]".format(counter)] = int(5000)
        else:
            config["upper_bound[{0}]".format(counter)] = int(0)
            config["lower_bound[{0}]".format(counter)] = int(0)
        counter += 1

    return json.dumps(config)
