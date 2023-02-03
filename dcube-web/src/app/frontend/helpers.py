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
from models.config import Config
from datetime import datetime
from flask_security import current_user

from models.jamming_pi import JammingPi
from models.jamming_scenario import JammingScenario
from models.jamming_timing import JammingTiming
from models.jamming_config import JammingConfig
from models.jamming_composition import JammingComposition

from models.layout_pi import LayoutPi

import holidays
import string
import random
import pytz

KEY_LEN = 64
JOB_OVERHEAD = 120


def maintenance_mode():
    if current_user.has_role("admins"):
        return False

    if current_user.is_authenticated and current_user.group.id == 1:
        return False

    return Config.get_bool("maintenance", True)


def base_str():
    return (string.ascii_letters+string.digits)


def key_gen():
    keylist = [random.choice(base_str()) for i in range(KEY_LEN)]
    return ("".join(keylist))


def check_weekend():
    wd = datetime.today().weekday()
    if (wd == 5 or wd == 6):
        return True
    else:
        return False


def check_holiday():
    h = holidays.Austria(prov='ST')
    h.append(["2020-12-24","2020-12-31"])
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
        tz=pytz.timezone("Europe/Vienna") #TODO: Take string from config!
        now=datetime.now(tz)

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


def check_jamming_time():
    if (check_holiday() == True):
        return True

    if (check_weekend() == True):
        return True

    db.session.commit()
    start = Config.query.filter_by(key="jamming_time_start").first()
    stop = Config.query.filter_by(key="jamming_time_stop").first()
    if not start == None and not stop == None:
        tz=pytz.timezone("Europe/Vienna") #TODO: Take string from config!
        now = datetime.now(tz)
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


def build_node_dict(composition):
    patterns = LayoutPi.query.with_entities(LayoutPi.composition_id, LayoutPi.group).filter_by(
        composition_id=composition.id).distinct()
    nodes = []
    edges = []
    for p in patterns:

        s_nodes = []
        sources = LayoutPi.query.filter_by(
            composition_id=composition.id, group=p.group, role="source").all()
        for s in sources:
            node = {"label": s.rpi}
            s_nodes.append(node)

        d_nodes = []
        destinations = LayoutPi.query.filter_by(
            composition_id=composition.id, group=p.group, role="sink").all()
        for d in destinations:
            node = {"label": d.rpi}
            d_nodes.append(node)

        nodes += s_nodes+d_nodes
    return nodes


def build_layout_dict(composition, rpi=None, show_unused=True):
    patterns = LayoutPi.query.with_entities(LayoutPi.composition_id, LayoutPi.group).filter_by(
        composition_id=composition.id).distinct()
    nodes = []
    edges = []
    for p in patterns:
        s_nodes = []
        sources = LayoutPi.query.filter_by(
            composition_id=composition.id, group=p.group, role="source").all()
        for s in sources:
            node = {"id": s.id, "label": s.rpi,
                    "color": "rgb(235,43,76)", "value": 10}
            if(s.rpi == rpi):
                node['font'] = {"size": 20}
                node['value'] = 20
            s_nodes.append(node)

        d_nodes = []
        destinations = LayoutPi.query.filter_by(
            composition_id=composition.id, group=p.group, role="sink").all()
        for d in destinations:
            node = {"id": d.id, "label": d.rpi,
                    "color": "rgb(153,204,255)", "value": 10}
            if(d.rpi == rpi):
                node['font'] = {"size": 20}
                node['value'] = 20
            d_nodes.append(node)

        u_nodes = []
        if(show_unused == True):
            unused = LayoutPi.query.filter_by(composition_id=composition.id, group=p.group).filter(
                LayoutPi.role != "sink").filter(LayoutPi.role != "source").all()
            for u in unused:
                node = {"id": u.id, "label": u.rpi,
                        "color": "rgb(236,236,236)", "value": 10}
                if(u.rpi == rpi):
                    node['font'] = {"size": 20}
                    node['value'] = 20
                u_nodes.append(node)

        for s in s_nodes:
            for d in d_nodes:
                edge = {"from": s['id'], "to": d['id']}
                edges.append(edge)

        nodes += s_nodes+d_nodes+u_nodes
    return {"nodes": nodes, "edges": edges}


def build_jamming_composition_dict(composition):

    pis = JammingPi.query.filter_by(composition_id=composition.id).all()

    groups = []
    items = []

    for pi in pis:
        groups.append({"id": pi.rpi, "content": pi.rpi})

        timings = JammingTiming.query.filter_by(scenario_id=pi.scenario.id)
        for t in timings:
            i = {"id": "{0}-{1}".format(pi.id, t.id), "cid": str(
                t.config.id), "content": t.config.name, "start": int(t.timestamp), "group": pi.rpi}
            items.append(i)

    return {"items": items, "groups": groups}


def build_jamming_scenario_dict(scenario):
    timings = JammingTiming.query.filter_by(scenario_id=scenario.id)

    items = []
    for t in timings:
        i = {"id": int(t.id), "cid": str(t.config.id), "content": t.config.name, "start": int(t.timestamp), "jam_power": int(
            t.config.power), "jam_channel": int(t.config.channel), "jam_period": int(t.config.periode), "jam_length": int(t.config.length)}
        items.append(i)

    return items


def build_jamming_config_dict(configs):
    items = []
    for c in configs:
        i = {"id": int(c.id), "cid": str(c.id), "content": c.name, "jam_power": int(
            c.power), "jam_channel": int(c.channel), "jam_period": int(c.periode), "jam_length": int(c.length)}
        items.append(i)

    return items


def build_jamming_dict(composition, scenario_id=None, node_id=None):
    pis = JammingPi.query.filter_by(composition_id=composition.id)

    nodes = []
    edges = []
    known = []

    for pi in pis:
        if not (pi.scenario_id*1000 in known):
            d = {"id": pi.scenario.id*1000, "label": pi.scenario.name,
                 "color": "rgb(235,43,76)", "value": 10}
            if(pi.scenario.id == scenario_id):
                d['font'] = {"size": 20}
                d['value'] = 20
            nodes.append(d)
            known.append(pi.scenario.id*1000)

        d = {"id": pi.id, "label": pi.rpi,
             "color": "rgb(153,204,255)", "value": 10}
        if(pi.id == node_id):
            d['font'] = {"size": 20}
            d['value'] = 20
        nodes.append(d)
        edges.append({"from": pi.id, "to": pi.scenario_id*1000})

    return {"nodes": nodes, "edges": edges}
