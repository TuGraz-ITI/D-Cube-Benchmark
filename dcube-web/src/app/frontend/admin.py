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
from flask import Blueprint, redirect, request, render_template, current_app, url_for, flash, send_from_directory, abort
from flask_security import login_required, roles_required, current_user, hash_password

from werkzeug.utils import secure_filename

from .helpers import *

from models.user import User
from models.group import Group
from models.role import Role

from models.job import Job
from models.firmware import Firmware
from models.metric import Metric
from models.result import Result
from models.scenario import Scenario
from models.evaluation import Evaluation
from models.patch import Patch
from models.log import Log

from models.jamming_pi import JammingPi
from models.jamming_scenario import JammingScenario
from models.jamming_timing import JammingTiming
from models.jamming_config import JammingConfig
from models.jamming_composition import JammingComposition

from models.layout_pi import LayoutPi
from models.layout_composition import LayoutComposition

from models.node import Node
from models.protocol import Protocol
from models.benchmark_suite import BenchmarkSuite
from models.benchmark_config import BenchmarkConfig

from backend.database import db
from backend.security import user_datastore

from .frontend import maintenance_mode

import calendar
import os
import json

intervals = (
    ('weeks', 604800),  # 60 * 60 * 24 * 7
    ('days', 86400),    # 60 * 60 * 24
    ('hours', 3600),    # 60 * 60
    ('minutes', 60),
    ('seconds', 1),
)


def display_time(seconds, granularity=2):
    result = []

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(value, name))
    return ', '.join(result[:granularity])


admin = Blueprint('admin', __name__)


@admin.before_app_first_request
def setup_defaults():
    db.create_all()

    # We best ensure that nobody deleted the builtin roles
    admins = user_datastore.find_or_create_role(name="admins")
    users = user_datastore.find_or_create_role(name="users")
    db.session.commit()

    # If there are no more users create one admin user just in case
    anyone = User.query.first()
    if anyone is None:
        admin = user_datastore.create_user(
            username="admin", email='admin@admin.net', password=hash_password('admin'))
        user_datastore.add_role_to_user(admin, admins)
        user_datastore.add_role_to_user(admin, users)
        group = Group("builtin")
        db.session.add(group)
        db.session.commit()
        admin.group = group

    db.session.commit()

    configs = Config.query
    defaults = [
        Config("maintenance", "True"),
        Config("maintenance_msg", "Testbed is being set up, stay tuned!"),
        Config("pagetitle", "D-Cube Testbed"),
        Config("pagesubtitle", "Docker Edition"),
        Config("leaderboard", "False"),
        Config("durations", "120 480"),
        Config("max_duration", "480"),
        Config("def_duration", "480"),
        Config("jamming_available", "False"),
        Config("scheduler_time_start", "18:00:00"),
        Config("scheduler_time_stop", "8:00:00"),
        Config("jamming_time_start", "20:00:00"),
        Config("jamming_time_stop", "6:00:00"),
        Config("scheduler_stop", "off")
    ]

    for default in defaults:
        if configs.filter_by(key=default.key).first() == None:
            db.session.add(default)
    db.session.commit()

    if JammingComposition.query.first() == None:
        jamming_lvl0=JammingComposition("None",0,True)
        jamming_none=JammingScenario.query.filter_by(name="None").first()
        if jamming_none == None:
            jamming_none=JammingScenario("None")
            db.session.add(jamming_none)
        jamming_config_none=JammingConfig.query.filter_by(name="Off").first() 
        if jamming_config_none == None:
            jamming_config_none=JammingConfig("Off",7,0,13,1000)
            db.session.add(jamming_config_none)
        db.session.add(jamming_lvl0)
        db.session.flush()

        jamming_timing_none=JammingTiming(0,jamming_config_none.id,jamming_none.id)
        db.session.add(jamming_timing_none)
        db.session.add(jamming_lvl0)
        db.session.flush()

        jamming_pi_default=JammingPi("default",jamming_lvl0.id,jamming_none.id)
        db.session.add(jamming_pi_default)
        db.session.commit()

    if Node.query.first() == None:
        sky=Node("Sky-All")
        nordic=Node("Nordic-All")
        linux_node=Node("Linux-All")
        db.session.add(sky)
        db.session.add(nordic)
        db.session.add(linux_node)
        db.session.commit()

    if BenchmarkSuite.query.first() == None:

        sky=Node.query.filter_by(name="Sky-All").first()
        nordic=Node.query.filter_by(name="Nordic-All").first()
        linux_node=Node.query.filter_by(name="Linux-All").first()

        suites=[]
        if not sky==None:
            skydc=BenchmarkSuite("Tmote Sky Data Collection v1","SkyDC_1")
            skydd=BenchmarkSuite("Tmote Sky Dissemination v1","SkyDD_1")
            skydc.node_id=sky.id
            skydd.node_id=sky.id
            suites.append(skydc)
            suites.append(skydd)
            db.session.add(skydc)
            db.session.add(skydd)
        if not nordic==None:
            nrfdc=BenchmarkSuite("nRF52840 Timely Data Collection v1","nRFDC_1")
            nrfdc.latency=False
            nrfdd=BenchmarkSuite("nRF52840 Timely Dissemination v1","nRFDD_1")
            nrfdd.latency=False
            nrfdc.node_id=nordic.id
            nrfdd.node_id=nordic.id
            suites.append(nrfdc)
            suites.append(nrfdd)
            db.session.add(nrfdc)
            db.session.add(nrfdd)
        if not linux_node==None:
            linux=BenchmarkSuite("Linux iperf3 v1","iperf_1")
            linux.node_id=linux_node.id
            suites.append(linux)
            db.session.add(linux)

        db.session.flush()

        for suite in suites:
            empty=LayoutComposition("Empty Configuration",0,suite.id)
            db.session.add(empty)
            db.session.flush()
            cmd="/home/pi/testbed/i2c/measurement -1 -2 -p24"
            if "Linux" in suite.name:
                cmd="/bin/true"

            default_pi=LayoutPi("default",cmd,"None","None",empty.id)
            db.session.add(default_pi)
            db.session.flush()

        for suite in suites:
            if "Linux" in suite.name:
                continue
            simple=LayoutComposition("Node Layout 1",1,suite.id)
            db.session.add(simple)
            db.session.flush()
            group="None"
            if "Dissemination" in suite.name:
                group="p2mp1"
            elif "Collection" in suite.name:
                group="mp2p1"
            default_pi=LayoutPi("default","/home/pi/testbed/i2c/measurement -1 -2 -p24","None","None",simple.id)
            pi100=LayoutPi("100","/home/pi/testbed/i2c/blinker -2 -r -p24 -s 100","source",group,simple.id)
            pi101=LayoutPi("101","/home/pi/testbed/i2c/measurement -1 -2 -p24","sink",group,simple.id)
            db.session.add(default_pi)
            db.session.add(pi100)
            db.session.add(pi101)
            db.session.flush()

        for suite in suites:
            start=BenchmarkConfig("start","60",suite.id)
            db.session.add(start)
            if "Timely" in suite.name:
                delta=BenchmarkConfig("delta","3000",suite.id)
                db.session.add(delta)

    db.session.commit()

    admins=Group.query.filter_by(name="builtin").first()
    if (not admins==None) and Protocol.query.first() == None:

        skydc=BenchmarkSuite.query.filter_by(name="Tmote Sky Data Collection v1").first()
        skydd=BenchmarkSuite.query.filter_by(name="Tmote Sky Dissemination v1").first()
        nrfdc=BenchmarkSuite.query.filter_by(name="nRF52840 Timely Data Collection v1").first()
        nrfdd=BenchmarkSuite.query.filter_by(name="nRF52840 Timely Dissemination v1").first()
        linux=BenchmarkSuite.query.filter_by(name="Linux iperf3 v1").first()

        if(not skydc==None):
            pskydc=Protocol("Administrative Experiment TelosB Sky DC", "https://iti-testbed.tugraz.at/", "Maintenance Jobs", admins.id, skydc.id)
            db.session.add(pskydc)
        if(not skydd==None):
            pskydd=Protocol("Administrative Experiment TelosB Sky DD", "https://iti-testbed.tugraz.at/", "Maintenance Jobs", admins.id, skydd.id)
            db.session.add(pskydd)
        if(not nrfdc==None):
            pnrfdc=Protocol("Administrative Experiment nRF DC", "https://iti-testbed.tugraz.at/", "Maintenance Jobs", admins.id, nrfdc.id)
            db.session.add(pnrfdc)
        if(not nrfdd==None):
            pnrfdd=Protocol("Administrative Experiment nRF DD", "https://iti-testbed.tugraz.at/", "Maintenance Jobs", admins.id, nrfdd.id)
            db.session.add(pnrfdd)
        if(not linux==None):
            plinux=Protocol("Administrative Experiment Linux iperf3", "https://iti-testbed.tugraz.at/", "Maintenance Jobs", admins.id, linux.id)
            db.session.add(plinux)

    db.session.commit()


@admin.route('/statistics')
@roles_required("admins")
def admin_statistics():
    groups = Group.query.all()
    filtered_groups = []
    total_usage = 0
    msg_cnt = 0
    benchmark_suite = (request.args.get('benchmark_suite'))
    benchmark_suite = BenchmarkSuite.query.filter_by(short=benchmark_suite).first()
    for group in groups:
        g = {}
        g['name'] = group.name
        if benchmark_suite == None:
            jobs = Job.query.filter_by(group=group)
        else:
            jobs = Job.query.filter_by(group=group).filter(
                Job.layout.has(LayoutComposition.benchmark_suite_id == benchmark_suite.id))
        g['count'] = len(jobs.all())
        t = 0
        msg_cnt = 0
        for j in jobs:
            if j.finished and not j.failed:
                t = t+j.duration
        g['total_seconds'] = t
        if(not g['name'] == "00"):
            total_usage += t
        g['total_time'] = display_time(t)
        filtered_groups = filtered_groups+[g, ]
    filtered_groups = sorted(
        filtered_groups, key=lambda group: group['total_seconds'], reverse=True)
    return render_template('admin/statistics.html', groups=filtered_groups, total_usage=display_time(total_usage).strip(), msg_cnt=msg_cnt)


@admin.route('/users')
@roles_required("admins")
def users():
    users = User.query.all()
    groups = Group.query.all()
    return render_template('admin/users.html', users=users, groups=groups)


@admin.route('/create_user', methods=['POST'])
@roles_required("admins")
def create_user_post():
    username = (request.form['username'])
    email = (request.form['email'])
    password = (request.form['password'])
    groupname = (request.form['group'])

    if((username == None) or (email == None) or (password == None) or (groupname == None)):
        flash('Missing Data!', 'error')
    else:
        if(not ((user_datastore.find_user(username=username) == None) and (user_datastore.find_user(email=email) == None))):
            flash('User or Email already exist!', 'error')
        else:
            group = Group.query.filter_by(name=groupname).first()
            if (group == None):
                flash('Group ' + groupname + ' does not exist!', 'error')
            else:
                user = user_datastore.create_user(
                    username=username, email=email, password=hash_password(password), group_id=group.id)
                users = user_datastore.find_role("users")
                user_datastore.add_role_to_user(user, users)
                db.session.commit()
                flash('User ' + username + ' created!', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/delete_user/<int:id>')
@roles_required("admins")
def delete_user(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        user = user_datastore.find_user(id=id)
        if(user == None):
            flash('User ' + str(id) + ' does not exist!', 'error')
        else:
            user_datastore.delete_user(user)
            db.session.commit()
            flash('User ' + str(id) + ' deleted!', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/generate_apikey/<int:id>')
@roles_required("admins")
def generate_api_key(id):
    user = User.query.filter_by(id=id).first()
    if(user == None):
        flash('User not found!', 'error')
        return redirect(url_for('admin.users'))

    user.api_key = key_gen()
    db.session.commit()
    flash('API key for User ' + user.username + ' generated!', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/delete_apikey/<int:id>')
@roles_required("admins")
def delete_api_key(id):
    user = User.query.filter_by(id=id).first()
    if(user == None):
        flash('User not found!', 'error')
        return redirect(url_for('admin.users'))

    user.api_key = None
    db.session.commit()
    flash('API key for User ' + user.username + ' deleted!', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/users/<int:id>/admin<int:admin>')
@roles_required("admins")
def promote_user(id=None, admin=None):
    if(id == None):
        flash('Missing Data!', 'error')
    else:
        user = User.query.filter_by(id=id).first()
        if(user == current_user):
            flash('Not possible on currently logged in user!', 'error')
        else:
            if(user == None):
                flash('User does not exist!', 'error')
            else:
                if(admin == 1):
                    user_datastore.add_role_to_user(user, "admins")
                    flash('User ' + user.username +
                          ' is now and administrator!', 'success')
                    db.session.commit()
                elif(admin == 0):
                    user_datastore.remove_role_from_user(user, "admins")
                    flash('User ' + user.username +
                          ' is no longer an administrator!', 'success')
                    db.session.commit()
                else:
                    flash('Invalid admin parameter!', 'error')
    return redirect(url_for('admin.users'))


@admin.route('/roles')
@roles_required("admins")
def roles():
    users = User.query.all()
    roles = Role.query.all()
    return render_template('admin/roles.html', users=users, roles=roles)


@admin.route('/roles/create', methods=['POST'])
@roles_required("admins")
def create_role_post():
    name = (request.form['name'])

    if(name == None):
        flash('Missing Data!', 'error')
    else:
        role = user_datastore.find_role(name)
        if(not role == None):
            flash('Role %s already exists!' % name, 'error')
        else:
            role = user_datastore.find_or_create_role(name=name)
            db.session.add(role)
            db.session.commit()
            flash('Role ' + name + ' created!', 'success')
    return redirect(url_for('admin.roles'))


@admin.route('/roles/assign', methods=['POST'])
@roles_required("admins")
def assign_role_post():
    rolename = (request.form['rolename'])
    username = (request.form['username'])
    if(rolename == None or username == None):
        flash('Missing Data!', 'error')
    else:
        role = user_datastore.find_role(rolename)
        user = user_datastore.find_user(username=username)
        if(role == None):
            flash('Role %s does not exist!' % rolename, 'error')
        elif(user == None):
            flash('User %s does not exist!' % username, 'error')
        else:
            user_datastore.add_role_to_user(user, role)
            db.session.commit()
            flash('User %s is now a member of Role %s!' %
                  (username, rolename), 'success')
    return redirect(url_for('admin.roles'))


@admin.route('/roles/unassign', methods=['POST'])
@roles_required("admins")
def unassign_role_post():
    rolename = (request.form['rolename'])
    username = (request.form['username'])
    if(rolename == None or username == None):
        flash('Missing Data!', 'error')
    else:
        role = user_datastore.find_role(rolename)
        user = user_datastore.find_user(username=username)
        if(role == None):
            flash('Role %s does not exist!' % rolename, 'error')
        elif(user == None):
            flash('User %s does not exist!' % username, 'error')
        else:
            user_datastore.remove_role_from_user(user, role)
            db.session.commit()
            flash('User %s is no longer a member of Role %s!' %
                  (username, rolename), 'success')
    return redirect(url_for('admin.roles'))


@admin.route('/roles/delete/<name>')
@roles_required("admins")
def delete_role(name=None):
    if((name == None)):
        flash('Missing Data!', 'error')
    elif(name == "users" or name == "admins"):
        flash('Cannot delete builtin role %s!' % name, 'error')
    else:
        role = user_datastore.find_role(name)
        if(role == None):
            flash('Role ' + name + ' does not exist!', 'error')
        else:
            users = User.query.all()
            for user in users:
                user_datastore.remove_role_from_user(user, role)
            db.session.delete(role)
            db.session.commit()
            flash('Role ' + name + ' deleted!', 'success')
    return redirect(url_for('admin.roles'))


@admin.route('/groups')
@roles_required("admins")
def groups():
    groups = Group.query.all()
    return render_template('admin/groups.html', groups=groups)


@admin.route('/create_group', methods=['POST'])
@roles_required("admins")
def create_group_post():
    name = (request.form['name'])

    if(name == None):
        flash('Missing Data!', 'error')
    else:
        if(not (Group.query.filter_by(name=name).first() == None)):
            flash('Group already exist!', 'error')
        else:
            group = Group(name)
            db.session.add(group)
            db.session.commit()
            flash('Group ' + name + ' created!', 'success')
    return redirect(url_for('admin.groups'))


@admin.route('/delete_group/<name>')
@roles_required("admins")
def delete_group(name=None):
    if((name == None)):
        flash('Missing Data!', 'error')
    else:
        group = Group.query.filter_by(name=name).first()
        if(group == None):
            flash('Group ' + name + ' does not exist!', 'error')
        else:
            db.session.delete(group)
            db.session.commit()
            flash('Group ' + name + ' deleted!', 'success')
    return redirect(url_for('admin.groups'))


@admin.route('/configs/')
@roles_required("admins")
def configs():
    configs = Config.query.all()
    scheduler_stop = Config.query.filter_by(key="scheduler_stop").first()
    return render_template('admin/configs.html', configs=configs, scheduler_stop=scheduler_stop)


@admin.route('/configs/delete_config/<int:id>')
@roles_required("admins")
def admin_delete_config(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        config = Config.query.filter_by(id=id).first()
        if(config == None):
            flash('Config does not exist!', 'error')
        else:
            flash('Config ' + config.key + ' deleted!', 'success')
            db.session.delete(config)
            db.session.commit()
    return redirect(url_for('admin.configs'))


@admin.route('/configs/jamming', methods=['POST'])
@roles_required("admins")
def admin_change_jmamming():
    jam = ("jamming" in (request.form))
    # jam_max=(request.form['jamming_max'])
    jamming = Config.query.filter_by(key="jamming_available").first()
    jamming_max = Config.query.filter_by(key="jamming_max").first()
    if(jamming == None):
        flash('Jamming option is now ' + str(jam) + '!', 'success')
        jamming = Config("jamming_available", str(jam))
        db.session.add(jamming)
    else:
        flash('Jamming option is now ' + str(jam) + '!', 'success')
        jamming.value = str(jam)

    db.session.commit()
    return redirect(url_for('admin.configs'))


@admin.route('/configs/pagetitle', methods=['POST'])
@roles_required("admins")
def admin_pagetitle():
    pagetitle = (request.form['pagetitle'])
    pagesubtitle = (request.form['pagesubtitle'])

    if(pagetitle == None or pagesubtitle == None):
        flash('Missing Data!', 'error')
    else:
        pagetitle_db = Config.query.filter_by(key="pagetitle").first()
        pagesubtitle_db = Config.query.filter_by(key="pagesubtitle").first()
        if(pagetitle_db == None):
            flash('Pagetitle is now now ' + pagetitle + '!', 'success')
            pagetitle_db = Config("pagetitle", pagetitle)
            db.session.add(pagetitle_db)
        else:
            flash('Pagetitle is now now ' + pagetitle + '!', 'success')
            pagetitle_db.value = pagetitle
        if(pagesubtitle_db == None):
            flash('Pagesubtitle is now now ' + pagesubtitle + '!', 'success')
            pagesubtitle_db = Config("pagesubtitle", pagesubtitle)
            db.session.add(pagesubtitle_db)
        else:
            flash('Pagesubtitle is now now ' + pagesubtitle + '!', 'success')
            pagesubtitle_db.value = pagesubtitle
        db.session.commit()
    return redirect(url_for('admin.configs'))


@admin.route('/configs/scheduler_time', methods=['POST'])
@roles_required("admins")
def admin_scheduler_time():
    start = (request.form['scheduler_start'])
    stop = (request.form['scheduler_stop'])
    jstart = (request.form['jamming_start'])
    jstop = (request.form['jamming_stop'])

    if(start == None or stop == None):
        flash('Missing Data!', 'error')
    else:
        start_db = Config.query.filter_by(key="scheduler_time_start").first()
        stop_db = Config.query.filter_by(key="scheduler_time_stop").first()
        jstart_db = Config.query.filter_by(key="jamming_time_start").first()
        jstop_db = Config.query.filter_by(key="jamming_time_stop").first()

        if(start_db == None):
            flash('Scheduler start time is now now ' + start + '!', 'success')
            start_db = Config("scheduler_time_start", start)
            db.session.add(start_db)
        else:
            flash('Scheduler start time is now now ' + start + '!', 'success')
            start_db.value = start
        if(stop_db == None):
            flash('Scheduler stop time is now now ' + stop + '!', 'success')
            stop_db = Config("scheduler_time_stop", stop)
            db.session.add(stop_db)
        else:
            flash('Jamming stop time is now now ' + stop + '!', 'success')
            stop_db.value = stop

        if(jstart_db == None):
            flash('Scheduler start time is now now ' + jstart + '!', 'success')
            jstart_db = Config("jamming_time_start", jstart)
            db.session.add(jstart_db)
        else:
            flash('Jamming start time is now now ' + jstart + '!', 'success')
            jstart_db.value = jstart
        if(jstop_db == None):
            flash('Jamming stop time is now now ' + jstop + '!', 'success')
            jstop_db = Config("jamming_time_stop", jstop)
            db.session.add(jstop_db)
        else:
            flash('Jamming stop time is now now ' + jstop + '!', 'success')
            jstop_db.value = jstop

        db.session.commit()
    return redirect(url_for('admin.configs'))


@admin.route('/configs/maintenance', methods=['POST'])
@roles_required("admins")
def admin_maintenance():
    maintenance = ("maintenance" in (request.form))
    maintenance_msg = (request.form['maintenance_msg'])

    if(maintenance_msg == None):
        flash('Missing Data!', 'error')
    else:
        maintenance_db = Config.query.filter_by(key="maintenance").first()
        maintenance_msg_db = Config.query.filter_by(
            key="maintenance_msg").first()
        if(maintenance_db == None):
            flash('Maintenance mode is now now ' +
                  str(maintenance) + '!', 'success')
            maintenance_db = Config("maintenance", str(maintenance))
            db.session.add(maintenance_db)
        else:
            flash('Maintenance mode is now now ' +
                  str(maintenance) + '!', 'success')
            maintenance_db.value = str(maintenance)
        if(maintenance_msg_db == None):
            flash('Maintenance message is now now ' +
                  maintenance_msg + '!', 'success')
            maintenance_msg_db = Config("maintenance_msg", maintenance_msg)
            db.session.add(maintenance_msg_db)
        else:
            flash('Maintenance message is now now ' +
                  maintenance_msg + '!', 'success')
            maintenance_msg_db.value = maintenance_msg

        db.session.commit()
    return redirect(url_for('admin.configs'))


@admin.route('/configs/duration', methods=['POST'])
@roles_required("admins")
def admin_change_max_duration():

    value = (request.form['durations'])
    if(value == None):
        flash('Missing Data (durations)!', 'error')
        return redirect(url_for('admin.configs'))
    values = value.split()

    for v in values:
        try:
            int_value = int(v, 10)
        except ValueError:
            flash('Invalid input (durations)!', 'error')
            return redirect(url_for('admin.configs'))

        if(int_value < 0 or int_value > 36000):
            flash('Invalid Durations ('+value+')!', 'error')
            return redirect(url_for('admin.configs'))

    durations = Config.query.filter_by(key="durations").first()
    if(durations == None):
        flash('Durations are now ' + str(values) + '!', 'success')
        durations = Config("durations", value)
        db.session.add(durations)
    else:
        flash('Durations are now ' + str(values) + '!', 'success')
        durations.value = value
    db.session.commit()

    value = (request.form['max_duration'])
    if(value == None):
        flash('Missing Data (max_duration)!', 'error')
        return redirect(url_for('admin.configs'))
    try:
        int_value = int(value, 10)
    except ValueError:
        flash('Invalid input (max_duration)!', 'error')
        return redirect(url_for('admin.configs'))
    if(int_value < 0 or int_value > 36000):
        flash('Invalid max Duration!', 'error')
        return redirect(url_for('admin.configs'))
    else:
        max_duration = Config.query.filter_by(key="max_duration").first()
        if(max_duration == None):
            flash('Max duration is now ' + value + '!', 'success')
            max_duration = Config("max_duration", int_value)
            db.session.add(max_duration)
        else:
            flash('Max duration is now ' + value + '!', 'success')
            max_duration.value = int_value
        db.session.commit()

    value = (request.form['def_duration'])
    if(value == None):
        flash('Missing Data (def_duration)!', 'error')
        return redirect(url_for('admin.configs'))
    try:
        int_value = int(value, 10)
    except ValueError:
        flash('Invalid input (def_duration)!', 'error')
        return redirect(url_for('admin.configs'))
    if(int_value < 0 or int_value > 36000):
        flash('Invalid default Duration!', 'error')
        return redirect(url_for('admin.configs'))
    else:
        def_duration = Config.query.filter_by(key="def_duration").first()
        if(def_duration == None):
            flash('Default duration is now ' + value + '!', 'success')
            def_duration = Config("def_duration", int_value)
            db.session.add(def_duration)
        else:
            flash('Default duration is now ' + value + '!', 'success')
            def_duration.value = int_value
        db.session.commit()

    return redirect(url_for('admin.configs'))


@admin.route('/configs/leaderboard', methods=['POST'])
@roles_required("admins")
def admin_change_leaderboard():
    leaderboard = ("leaderboard" in (request.form))
    leaderboard_db = Config.query.filter_by(key="leaderboard").first()
    if(leaderboard_db == None):
        flash('Leaderboard mode is now now ' +
              str(leaderboard) + '!', 'success')
        leaderboard_db = Config("leaderboard", str(leaderboard))
        db.session.add(leaderboard_db)
    else:
        flash('Leaderboard mode is now now ' +
              str(leaderboard) + '!', 'success')
        leaderboard_db.value = str(leaderboard)
    db.session.commit()
    return redirect(url_for('admin.configs'))


@admin.route('/admin/logs/')
@roles_required("admins")
def logs():
    logs = Log.query.order_by(Log.id.desc()).limit(100).all()
    return render_template('admin/logs.html', logs=logs)


@admin.route('/queue/')
@roles_required("admins")
def admin_queue():
    page = (request.args.get('page'))
    if page == None:
        page = -1
    else:
        page = int(page, 10)
    return admin_queue_page(page)


@admin.route('/queue/<int:page>')
@roles_required("admins")
def admin_queue_page(page=-1):
    if(page == -1):
        jobs = Job.query.order_by(Job.id.desc()).paginate(page=1, per_page=50)
    else:
        jobs = Job.query.order_by(Job.id.desc()).paginate(page=page, per_page=50)

    scheduler_stop = Config.query.filter_by(key="scheduler_stop").first()
    return render_template('admin/queue.html', jobs=jobs, scheduler_stop=scheduler_stop)


@admin.route('/queue/scheduler/<value>')
@roles_required("admins")
def admin_change_scheduler(value=None):
    if((value == None)):
        flash('Missing Data!', 'error')
    else:
        scheduler = Config.query.filter_by(key="scheduler_stop").first()
        if(scheduler == None):
            flash('Scheduler stop is now ' + value + '!', 'success')
            scheduler = Config("scheduler_stop", value)
            db.session.add(scheduler)
        else:
            flash('Scheduler stop is now ' + value + '!', 'success')
            scheduler.value = value
        db.session.commit()
    return redirect(url_for('admin.admin_queue'))


@admin.route('/firmwares/')
@roles_required("admins")
def firmwares():
    page = (request.args.get('page'))
    if page == None:
        page = -1
    else:
        page = int(page, 10)
    return firmwares_page(page)


@admin.route('/firmwares/<int:page>')
@roles_required("admins")
def firmwares_page(page=-1):
    if(page == -1):
        firmwares = Firmware.query.order_by(Firmware.id.desc()).paginate(page=1, per_page=50)
    else:
        firmwares = Firmware.query.order_by(
            Firmware.id.desc()).paginate(page=page, per_page=50)

    return render_template('admin/firmwares.html', firmwares=firmwares)


@admin.route('/firmwares/download/<int:id>', methods=['GET'])
@roles_required("admins")
def admin_download_firmware(id=None):
    if (id == None):
        flash('Missing Data!', 'error')
        return redirect(url_for('admin.firmwares'))

    firmware = Firmware.query.filter_by(id=id).first()

    ext=request.args.get("ext",default="ihex",type=str)

    if (firmware == None):
        abort(404)

    new_path = os.path.join(os.path.abspath(
        current_app.config['UPLOAD_FOLDER']), firmware.filename)
    new_dir = os.path.join(os.path.abspath(
        current_app.config['UPLOAD_FOLDER']))

    if os.path.isfile(new_path):
        return send_from_directory(directory=new_dir, path=firmware.filename, as_attachment=True,
                                   download_name="firmware_%d.%s"%(id,ext))

    if ((firmware.job == None) or (firmware.job.group == None)):
        abort(404)

    abort(404)


@admin.route('/queue/rerun_job/<int:id>', methods=['POST', 'GET'])
@roles_required("admins")
def admin_rerun_job(id=None):
    if (id == None):
        flash('Missing Data!', 'error')
        return redirect(url_for('frontend.index'))

    job = Job.query.filter_by(id=id).first()

    if (job == None):
        flash('Job does not exist!', 'error')
        return redirect(url_for('frontend.index'))

    if (job.finished == False):
        flash('Job has not finished yet!', 'error')
        return redirect(url_for('frontend.index'))

    if (job.running == True):
        flash('Job is currently running!', 'error')
        return redirect(url_for('frontend.index'))

    Metric.query.filter_by(job_id=id).delete()
    results = Result.query.filter_by(job_id=id).delete()
    scenarios = Scenario.query.filter_by(job_id=id)
    for s in scenarios.all():
        Evaluation.query.filter_by(scenario_id=s.id).delete()
    scenarios.delete()

    dl_dir = current_app.config['EVALUATION_FOLDER']
    if not dl_dir == None:
        rep = os.path.abspath(os.path.join(dl_dir, 'report_'+str(id)+'.pdf'))
        if(os.path.isfile(rep)):
            os.remove(rep)

    job.finished = False
    job.running = False
    job.failed = False
    job.evaluated = False
    db.session.commit()
    flash('Job ' + job.name + "("+str(id)+") will be re-run!", 'success')

    return redirect(url_for('frontend.index'))


@admin.route('/queue/download_logs/<int:id>')
@roles_required("admins")
def download_job_logs(id=None):
    if (id == None):
        flash('Missing Data!', 'error')
        return redirect(url_for('frontend.index'))

    job = Job.query.filter_by(id=id).first()
    if job is None:
        abort(404)
    dl_dir = current_app.config['LOGFILE_FOLDER'] + "/" + str(id)
    if dl_dir is None:
        abort(404)
    return send_from_directory(directory=dl_dir, 
                               path='logs.zip',
                               as_attachment=True,
                               download_name='logs_%s.zip'%(id))


@admin.route('/queue/reeval_all', methods=['GET'])
@roles_required("admins")
def admin_reeval_all_jobs():
    jobs = Job.query.all()
    for job in jobs:
        admin_reeval_job(job.id)
    flash('abandon all hope ye who enter here', 'error')
    return redirect(url_for('frontend.index'))


@admin.route('/queue/reeval_job/<int:id>', methods=['POST', 'GET'])
@roles_required("admins")
def admin_reeval_job(id=None):
    if (id == None):
        flash('Missing Data!', 'error')
        return redirect(url_for('frontend.index'))

    job = Job.query.filter_by(id=id).first()

    if (job == None):
        flash('Job does not exist!', 'error')
        return redirect(url_for('frontend.index'))

    if (job.evaluated == False):
        flash('Job has not evaluated yet!', 'error')
        return redirect(url_for('frontend.index'))

    if (job.running == True):
        flash('Job is currently running!', 'error')
        return redirect(url_for('frontend.index'))

    Metric.query.filter_by(job_id=id).delete()
    scenarios = Scenario.query.filter_by(job_id=id)
    for s in scenarios.all():
        Evaluation.query.filter_by(scenario_id=s.id).delete()
    scenarios.delete()

    dl_dir = current_app.config['EVALUATION_FOLDER']
    if not dl_dir == None:
        rep = os.path.abspath(os.path.join(dl_dir, 'report_'+str(id)+'.pdf'))
        if(os.path.isfile(rep)):
            os.remove(rep)

    job.evaluated = False
    db.session.commit()
    flash('Job ' + job.name + "("+str(id)+") will be re-evaluated!", 'success')
    return redirect(url_for('frontend.index'))


@admin.route('/queue/prioritize_job/<int:id>')
@roles_required("admins")
def admin_prioritize_job(id=None):
    j = Job.query.filter_by(id=id).first()
    if(j == None):
        flash('Job ' + str(id) + " not found!", 'error')
        return redirect(url_for('frontend.index'))
    else:
        j.priority = True
        db.session.commit()
        flash('Job ' + str(id) + " updated!", 'success')
        return redirect(url_for('frontend.index'))


@admin.route('/queue/update_job/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_job(id=None):
    name = (request.form['name'])
    logs = ("logs" in (request.form))
    finished = ("finished" in (request.form))
    running = ("running" in (request.form))
    failed = ("failed" in (request.form))
    priority = ("priority" in (request.form))
    evaluated = ("evaluated" in (request.form))
    description = (request.form['description'])

    if (name == None or id == None):
        flash('Missing Data!', 'error')
    else:
        #job = Job(name,description, dt, logs, current_user.group.id)
        job = Job.query.filter_by(id=id).first()
        job.name = name
        job.description = description
        job.logs = logs
        job.finished = finished
        job.running = running
        job.failed = failed
        job.priority = priority
        job.evaluated = evaluated
        db.session.commit()
        flash('Job ' + name + " updated!", 'success')

    return redirect(url_for('admin.admin_queue'))


def build_layout_dict(composition, rpi=None, show_unused=True):
    patterns = LayoutPi.query.with_entities(LayoutPi.composition_id, LayoutPi.group).filter_by(
        composition_id=composition.id).distinct()
    nodes = []
    edges = []
    for p in patterns:
        br_nodes = []
        border_routers = LayoutPi.query.filter_by(
            composition_id=composition.id, group=p.group, role="border_router").all()
        for br in border_routers:
            node = {"id": br.id, "label": br.rpi,
                    "color": "rgb(67,172,106)", "value": 10}
            if(br.rpi == rpi):
                node['font'] = {"size": 20}
                node['value'] = 20
            br_nodes.append(node)

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
                LayoutPi.role != "sink").filter(LayoutPi.role != "source").filter(LayoutPi.role != "border_router").all()
            for u in unused:
                node = {"id": u.id, "label": u.rpi,
                        "color": "rgb(236,236,236)", "value": 10}
                if(u.rpi == rpi):
                    node['font'] = {"size": 20}
                    node['value'] = 20
                u_nodes.append(node)

        for br1 in br_nodes:
            for br2 in br_nodes:
                if br1==br2:
                    continue
                edge = {"from": br1['id'], "to": br2['id']}
                edges.append(edge)

        for s in s_nodes:
            for d in d_nodes:
                edge = {"from": s['id'], "to": d['id']}
                edges.append(edge)

        nodes += s_nodes+d_nodes+u_nodes+br_nodes
    return {"nodes": nodes, "edges": edges}


@admin.route('/protocols')
@roles_required("admins")
def admin_protocols():
    protocols=Protocol.query.all()
    groups=Group.query.all()
    benchmark_suites=BenchmarkSuite.query.all()
    return render_template('admin/protocols.html', protocols=protocols,
                                                   groups=groups,
                                                   benchmark_suites=benchmark_suites)


@admin.route('/protocols/delete/<int:id>')
@roles_required("admins")
def admin_delete_protocol(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        protocol = Protocol.query.filter_by(id=id).first()

        if(node == None):
            flash('Protocol does not exist!', 'error')
        else:
            flash("Protocol %s deleted!"%protocol.id, 'success')

            db.session.delete(protocol)
            db.session.commit()
    return redirect(url_for('admin.admin_protocols'))


@admin.route('/protocol/update/', methods=['POST'])
@admin.route('/protocol/update/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_protocol(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        protocol = Protocol.query.filter_by(id=id).first()

        if(node == None):
            flash('Protocol does not exist!', 'error')
        else:
            name = request.form.get("name")
            link = request.form.get("link")
            description = request.form.get("description")

            group_id = request.form.get("group")
            group_id = int(group_id)
            group=Group.query.filter_by(id=group_id).first()
            benchmark_suite_id = request.form.get("benchmark_suite")
            benchmark_suite_id = int(benchmark_suite_id)
            benchmark_suite=BenchmarkSuite.query.filter_by(id=benchmark_suite_id).first()

            if(name == None or link == None or description == None or group == None or benchmark_suite == None):
                flash('Missing Protocol Data!', 'error')
                return redirect(url_for('admin.admin_protocols'))

            node.name = name
            node.link = link
            node.description = description
            node.group_id = group_id
            node.benchmark_suite_id = benchmark_suite_id

            flash("Protocol %s updated!"%protocol.id, 'success')
            db.session.commit()
    return redirect(url_for('admin.admin_protocols'))


@admin.route('/protocol/create/', methods=['POST'])
@roles_required("admins")
def admin_create_protocol():

    name = request.form.get("name")
    link = request.form.get("link")
    description = request.form.get("description")

    group_id = request.form.get("group")
    group_id = int(group_id)
    group=Group.query.filter_by(id=group_id).first()
    benchmark_suite_id = request.form.get("benchmark_suite")
    benchmark_suite_id = int(benchmark_suite_id)
    benchmark_suite=BenchmarkSuite.query.filter_by(id=benchmark_suite_id).first()

    if(name == None or link == None or description == None or group == None or benchmark_suite == None):
        flash('Missing Protocol Data!', 'error')
        return redirect(url_for('admin.admin_protocols'))

    protocol = Protocol(name,link,description,group_id,benchmark_suite_id)
    db.session.add(protocol)
    db.session.commit()
    flash("Protocol %s created!"%protocol.id, 'success')
    return redirect(url_for('admin.admin_protocols'))


@admin.route('/nodes')
@roles_required("admins")
def admin_nodes():
    nodes=Node.query.all()
    return render_template('admin/nodes.html', nodes=nodes)


@admin.route('/nodes/delete/<int:id>')
@roles_required("admins")
def admin_delete_node(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        node = Node.query.filter_by(id=id).first()

        if(node == None):
            flash('Node does not exist!', 'error')
        else:
            flash("Node %s deleted!"%node.id, 'success')

            db.session.delete(node)
            db.session.commit()
    return redirect(url_for('admin.admin_nodes'))


@admin.route('/nodes/update/', methods=['POST'])
@admin.route('/nodes/update/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_node(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        node = Node.query.filter_by(id=id).first()

        if(node == None):
            flash('Node does not exist!', 'error')
        else:
            name = request.form.get("name")

            if(name == None):
                flash('Missing Node Data!', 'error')
                return redirect(url_for('admin.admin_nodes'))

            node.name = name

            flash("Node %s updated!"%node.id, 'success')
            db.session.commit()
    return redirect(url_for('admin.admin_nodes'))


@admin.route('/nodes/create')
@roles_required("admins")
def admin_create_node():
    node = Node("New")
    db.session.add(node)
    db.session.commit()
    flash("Node %s created!"%node.id, 'success')
    return redirect(url_for('admin.admin_nodes'))


@admin.route('/benchmark_suite')
@roles_required("admins")
def admin_benchmark_suite():
    benchmark_suites = BenchmarkSuite.query
    benchmark_suite = request.args.get("benchmark_suite")
    if (benchmark_suite == None):
        benchmark_suite = benchmark_suites.first()
    else:
        benchmark_suite = benchmark_suites.filter_by(id=int(benchmark_suite)).first()
        if(benchmark_suite == None):
            benchmark_suite = benchmark_suites.first()

    if not benchmark_suite == None:
        composition = request.args.get("composition")
        compositions = LayoutComposition.query.filter_by(
            benchmark_suite_id=benchmark_suite.id)
        if (composition == None):
            composition = compositions.first()
        else:
            composition = compositions.filter_by(id=int(composition)).first()
            if(composition == None):
                composition = compositions.first()

        if not composition == None:

            pi = request.args.get("pi")
            pis = LayoutPi.query.filter_by(composition_id=composition.id)
            if (pi == None):
                pi = pis.first()
            else:
                pi = pis.filter_by(id=int(pi)).first()
                if(pi == None):
                    pi = pis.first()

            if(pi == None):
                layout_dict = build_layout_dict(composition)
            else:
                layout_dict = build_layout_dict(composition, pi.rpi)
        else:
            pi = None
            pis = LayoutPi.query
            layout_dict = {"nodes": [], "edges": []}

        config = request.args.get("benchmark_config")
        benchmark_configs = BenchmarkConfig.query.filter_by(
                benchmark_suite_id=benchmark_suite.id)

        if not config == None:
            benchmark_config=benchmark_configs.filter_by(id=config).first()
            if benchmark_config == None:
                benchmark_config=benchmark_configs.first()
        else:
            benchmark_config=benchmark_configs.first()

    else:
        composition = None
        compositions = LayoutComposition.query
        benchmark_config = None
        benchmark_configs = BenchmarkConfig.query
        pi = None
        pis = LayoutPi.query
        layout_dict = {"nodes": [], "edges": []}

    nodes = Node.query.all()
    return render_template('admin/benchmark_suites.html',
                            benchmark_suites=benchmark_suites.all(),
                            benchmark_suite=benchmark_suite,
                            compositions=compositions.all(),
                            composition=composition,
                            pis=pis.all(),
                            pi=pi,
                            layout_dict=layout_dict,
                            nodes=nodes,
                            benchmark_configs=benchmark_configs.all(),
                            benchmark_config=benchmark_config
                            )

@admin.route('/benchmark_suite/create_benchmark_config/<int:benchmark_suite_id>')
@roles_required("admins")
def admin_create_benchmark_config(benchmark_suite_id=None):

    benchmark_suite = BenchmarkSuite.query.filter_by(id=benchmark_suite_id).first()
    if(benchmark_suite == None):
        flash('Benchamrk Suite does not exist!', 'error')
        return redirect(url_for('admin.admin_benchmark_suite'))

    config = BenchmarkConfig("None", "0", benchmark_suite_id)

    db.session.add(config)
    db.session.commit()
    flash('Benchmark Conifg ' + str(config.id) + ' created!', 'success')
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite_id, benchmark_config=config.id))

@admin.route('/benchmark_suite/update_benchmark_config/', methods=['POST'])
@admin.route('/benchmark_suite/update_benchmark_config/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_benchmark_config(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        config = BenchmarkConfig.query.filter_by(id=id).first()

        if(config == None):
            flash('Config does not exist!', 'error')
            return redirect(url_for('admin.admin_benchmark_suite'))
        else:

            benchmark_suite = config.benchmark_suite

            key = request.form.get("key")
            value = request.form.get("value")

            if(key == None or value == None):
                flash('Missing Config Data!', 'error')
                return redirect(url_for('admin.admin_benchmark_suite'))

            config.key=key
            config.value=value

            flash('Config ' + str(config.id) + ' updated!', 'success')
            db.session.commit()
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite.id, benchmark_config=config.id))

@admin.route('/benchmark_suite/delete_benchmark_suite/<int:id>')
@roles_required("admins")
def admin_delete_benchmark_suite(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        benchmark_suite = BenchmarkSuite.query.filter_by(id=id).first()

        if(benchmark_suite == None):
            flash('Benchamrk Suite does not exist!', 'error')
        else:
            flash('Benchamrk Suite ' + str(benchmark_suite.id) + ' deleted!', 'success')
            compositions = LayoutComposition.query.filter_by(
                benchmark_suite_id=benchmark_suite.id)
            for composition in compositions.all():
                pis = LayoutPi.query.filter_by(
                    composition_id=composition.id).delete()
            compositions.delete()

            db.session.delete(benchmark_suite)
            db.session.commit()
    return redirect(url_for('admin.admin_benchmark_suite'))


@admin.route('/benchmark_suite/create_benchmark_suite')
@roles_required("admins")
def admin_create_benchmark_suite():
    benchmark_suite = BenchmarkSuite("New", "0")
    db.session.add(benchmark_suite)
    db.session.commit()
    flash('Categroy ' + str(benchmark_suite.id) + ' created!', 'success')
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite.id, composition=None, pi=None))


@admin.route('/benchmark_suite/update_benchmark_suite/', methods=['POST'])
@admin.route('/benchmark_suite/update_benchmark_suite/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_benchmark_suite(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        benchmark_suite = BenchmarkSuite.query.filter_by(id=id).first()

        if(benchmark_suite == None):
            flash('Benchamrk Suite does not exist!', 'error')
        else:
            name = request.form.get("name")
            short = request.form.get("short")

            energy = ("energy" in (request.form))
            latency = ("latency" in (request.form))
            reliability = ("reliability" in (request.form))

            node_id = request.form.get("node")
            node_id = int(node_id)
            node = Node.query.filter_by(id=node_id).first()

            if(name == None or short == None or node == None):
                flash('Missing Benchamrk Suite Data!', 'error')
                return redirect(url_for('admin.admin_benchmark_suite'))

            benchmark_suite.name = name
            benchmark_suite.short = short
            benchmark_suite.node = node
            benchmark_suite.energy = energy
            benchmark_suite.latency = latency
            benchmark_suite.reliability = reliability

            flash('Benchamrk Suite ' + str(benchmark_suite.id) + ' updated!', 'success')
            db.session.commit()
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite.id, composition=None, pi=None))


@admin.route('/benchmark_suite/delete_layout/<int:id>')
@roles_required("admins")
def admin_delete_layout(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        composition = LayoutComposition.query.filter_by(id=id).first()

        if(composition == None):
            flash('Composition does not exist!', 'error')
        else:
            bsid=composition.benchmark_suite.id
            flash('Composition ' + str(composition.id) + ' deleted!', 'success')
            pis = LayoutPi.query.filter_by(composition_id=id).delete()
            db.session.delete(composition)
            db.session.commit()
            return redirect(url_for('admin.admin_benchmark_suite',benchmark_suite=bsid))
    return redirect(url_for('admin.admin_benchmark_suite'))


@admin.route('/benchmark_suite/create_layout/<int:benchmark_suite_id>')
@roles_required("admins")
def admin_create_layout(benchmark_suite_id=None):

    benchmark_suite = BenchmarkSuite.query.filter_by(id=benchmark_suite_id).first()
    if(benchmark_suite == None):
        flash('Benchamrk Suite does not exist!', 'error')
        return redirect(url_for('admin.admin_benchmark_suite'))

    composition = LayoutComposition("New", "0", benchmark_suite_id)

    db.session.add(composition)
    db.session.commit()
    flash('Composition ' + str(composition.id) + ' created!', 'success')
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite_id, composition=composition.id, pi=None))


@admin.route('/benchmark_suite/update_layout/', methods=['POST'])
@admin.route('/benchmark_suite/update_layout/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_layout(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        composition = LayoutComposition.query.filter_by(id=id).first()
        pi_id = None

        if(composition == None):
            flash('Layout does not exist!', 'error')
            return redirect(url_for('admin.admin_benchmark_suite'))
        else:

            benchmark_suite = composition.benchmark_suite

            short = request.form.get("short")
            name = request.form.get("name")

            if(short == None or name == None):
                flash('Missing Layout Data!', 'error')
                return redirect(url_for('admin.admin_benchmark_suite'))

            composition.short = short
            composition.name = name
            pi = LayoutPi.query.filter_by(
                composition_id=composition.id).first()
            if(not pi == None):
                pi_id = pi.id

            flash('Layout ' + str(composition.id) + ' updated!', 'success')
            db.session.commit()
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite.id, composition=composition.id, pi=pi_id))


@admin.route('/benchmark_suite/layout/delete_node/<int:id>')
@roles_required("admins")
def admin_delete_pi(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        pi = LayoutPi.query.filter_by(id=id).first()

        if(pi == None):
            flash('Node does not exist!', 'error')
        else:
            composition = LayoutComposition.query.filter_by(
                id=pi.composition_id).first()
            benchmark_suite = composition.benchmark_suite

            flash('Node ' + str(pi.id) + ' deleted!', 'success')
            db.session.delete(pi)
            db.session.commit()
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite.id, composition=composition.id))


@admin.route('/benchmark_suite/layout/create_node/<int:composition_id>')
@roles_required("admins")
def admin_create_pi(composition_id=None):
    pi = LayoutPi("None", "None", "None", "None", composition_id)
    composition = LayoutComposition.query.filter_by(id=composition_id).first()
    benchmark_suite = composition.benchmark_suite

    db.session.add(pi)
    db.session.commit()
    flash('Node ' + str(pi.id) + ' created!', 'success')
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite.id, composition=composition.id, pi=pi.id))


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


@admin.route('/benchmark_suite/layout/update_node/', methods=['POST'])
@admin.route('/benchmark_suite/layout/update_node/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_pi(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        pi = LayoutPi.query.filter_by(id=id).first()

        if(pi == None):
            flash('Node does not exist!', 'error')
        else:

            composition = LayoutComposition.query.filter_by(
                id=pi.composition_id).first()
            benchmark_suite = composition.benchmark_suite

            rpi = request.form.get("rpi")
            group = request.form.get("group")
            role = request.form.get("role")
            command = request.form.get("command")

            if(rpi == None or group == None or role == None or command == None):
                flash('Missing Node Data!', 'error')
                return redirect(url_for('admin.admin_benchmark_suite'))

            pi.rpi = rpi
            pi.group = group
            pi.role = role
            pi.command = command

            flash('Node ' + str(pi.id) + ' updated!', 'success')
            db.session.commit()
    return redirect(url_for('admin.admin_benchmark_suite', benchmark_suite=benchmark_suite.id, composition=composition.id, pi=pi.id))


@admin.route('/jamming')
@roles_required("admins")
def admin_jamming():
    composition = request.args.get("composition")
    compositions = JammingComposition.query
    if (composition == None):
        composition = compositions.first()
    else:
        composition = compositions.filter_by(id=int(composition)).first()
        if(composition == None):
            composition = compositions.first()

    if not composition == None:
        pi = request.args.get("pi")
        pis = JammingPi.query.filter_by(composition_id=composition.id)
        if (pi == None):
            pi = pis.first()
        else:
            pi = pis.filter_by(id=int(pi)).first()
            if(pi == None):
                pi = pis.first()
    else:
        pis = JammingPi.query
        pi = None

    scenario = request.args.get("scenario")
    scenarios = JammingScenario.query

    if (scenario == None):
        scenario = scenarios.first()
    else:
        scenario = scenarios.filter_by(id=int(scenario)).first()
        if(scenario == None):
            scenario = scenarios.first()

    if scenario == None:
        sid = None
    else:
        sid = scenario.id

    if pi == None:
        pid = None
    else:
        pid = pi.id

    if not composition == None:
        jamming_dict = build_jamming_dict(composition, sid, pid)
        preview_dict = build_jamming_composition_dict(composition)
    else:
        jamming_dict = {"nodes": [], "edges": []}
        preview_dict = {"items": [], "groups": []}

    return render_template('admin/jamming.html', composition=composition, compositions=compositions.all(), pis=pis.all(), pi=pi, scenarios=scenarios.all(), scenario=scenario, jamming_dict=jamming_dict, preview_dict=preview_dict)


@admin.route('/jamming/create_composition')
@roles_required("admins")
def admin_create_jamming_composition():
    composition = JammingComposition("None", "None", False)

    db.session.add(composition)
    db.session.commit()
    flash('Composition ' + str(composition.id) + ' created!', 'success')
    return redirect(url_for('admin.admin_jamming', composition=composition.id))


@admin.route('/jamming/update_composition/', methods=['POST'])
@admin.route('/jamming/update_composition/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_jamming_composition(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        composition = JammingComposition.query.filter_by(id=id).first()

        if(composition == None):
            flash('Level does not exist!', 'error')
            return redirect(url_for('admin.admin_jamming'))
        else:

            short = request.form.get("short")
            name = request.form.get("name")
            public = ("public" in (request.form))

            if(short == None or name == None):
                flash('Missing Layout Data!', 'error')
                return redirect(url_for('admin.admin_benchmark_suite'))

            composition.short = short
            composition.name = name
            composition.public = public

            flash('Level ' + str(composition.id) + ' updated!', 'success')
            db.session.commit()

    scenario = request.args.get('scenario')
    pi = request.args.get('pi')

    return redirect(url_for('admin.admin_jamming', composition=composition.id, pi=pi, scenario=scenario))


@admin.route('/jamming/delete_composition/<int:id>')
@roles_required("admins")
def admin_delete_jamming_composition(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        composition = JammingComposition.query.filter_by(id=id).first()

        if(composition == None):
            flash('Composition does not exist!', 'error')
        else:
            flash('Composition ' + str(composition.id) + ' deleted!', 'success')
            pis = JammingPi.query.filter_by(
                composition_id=composition.id).delete()
            db.session.delete(composition)
            db.session.commit()

    return redirect(url_for('admin.admin_jamming'))


@admin.route('/jamming/create_scenario')
@roles_required("admins")
def admin_create_jamming_scenario():

    scenario = JammingScenario("None")

    db.session.add(scenario)
    db.session.commit()

    composition = request.args.get('composition')
    pi = request.args.get('pi')

    flash('Scenario ' + str(scenario.id) + ' created!', 'success')
    return redirect(url_for('admin.admin_jamming', scenario=scenario.id, composition=composition, pi=pi))


@admin.route('/jamming/update_scenario/', methods=['POST'])
@admin.route('/jamming/update_scenario/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_jamming_scenario(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        scenario = JammingScenario.query.filter_by(id=id).first()

        if(scenario == None):
            flash('Scenario does not exist!', 'error')
            return redirect(url_for('admin.admin_jamming'))
        else:

            name = request.form.get("name")

            if(name == None):
                flash('Missing Layout Data!', 'error')
                return redirect(url_for('admin.admin_benchmark_suite'))

            scenario.name = name

            db.session.commit()
            flash('Scenario ' + str(scenario.id) + ' updated!', 'success')

    composition = request.args.get('composition')
    pi = request.args.get('pi')

    return redirect(url_for('admin.admin_jamming', scenario=scenario.id, composition=composition, pi=pi))


@admin.route('/jamming/delete_scenario/<int:id>')
@roles_required("admins")
def admin_delete_jamming_scenario(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        scenario = JammingScenario.query.filter_by(id=id).first()

        if(scenario == None):
            flash('Scenario does not exist!', 'error')
        else:
            flash('Scenario ' + str(scenario.id) + ' deleted!', 'success')
            pis = JammingPi.query.filter_by(scenario_id=scenario.id).delete()
            db.session.delete(scenario)
            db.session.commit()

    composition = request.args.get('composition')
    pi = request.args.get('pi')

    return redirect(url_for('admin.admin_jamming', pi=pi, composition=composition))


@admin.route('/jamming/create_node/<int:composition_id>/<int:scenario_id>')
@roles_required("admins")
def admin_create_jamming_node(composition_id=None, scenario_id=None):
    if((composition_id == None or scenario_id == None)):
        flash('Missing Data!', 'error')

    composition = JammingComposition.query.filter_by(id=composition_id).first()
    if(composition == None):
        flash('Level does not exist!', 'error')
        return redirect(url_for('admin.admin_jamming'))

    scenario = JammingScenario.query.filter_by(id=scenario_id).first()
    if(scenario == None):
        flash('Scenario does not exist!', 'error')
        return redirect(url_for('admin.admin_jamming'))

    # rpi,composition_id,scenario_id
    pi = JammingPi("None", composition.id, scenario.id)

    db.session.add(pi)
    db.session.commit()
    flash('Node ' + str(composition.id) + ' created!', 'success')

    return redirect(url_for('admin.admin_jamming', composition=composition.id, pi=pi.id, scenario=scenario.id))


@admin.route('/jamming/update_node/', methods=['POST'])
@admin.route('/jamming/update_node/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_jamming_node(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        pi = JammingPi.query.filter_by(id=id).first()

        if(pi == None):
            flash('Node does not exist!', 'error')
            return redirect(url_for('admin.admin_jamming'))
        else:

            rpi = request.form.get("rpi")
            relative = ("relative" in (request.form))
            sync = ("sync" in (request.form))

            if(rpi == None):
                flash('Missing Layout Data!', 'error')
                return redirect(url_for('admin.admin_benchmark_suite'))

            pi.rpi = rpi
            pi.relative = relative
            pi.sync = sync

            flash('Node ' + str(pi.id) + ' updated!', 'success')
            db.session.commit()
    return redirect(url_for('admin.admin_jamming', pi=pi.id, composition=pi.composition_id, scenario=pi.scenario_id))


@admin.route('/jamming/delete_node/<int:id>')
@roles_required("admins")
def admin_delete_jamming_node(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        pi = JammingPi.query.filter_by(id=id).first()

        if(pi == None):
            flash('Node does not exist!', 'error')
        else:
            flash('Node ' + str(pi.id) + ' deleted!', 'success')
            db.session.delete(pi)
            db.session.commit()

    composition = request.args.get('composition')
    scenario = request.args.get('scenario')

    return redirect(url_for('admin.admin_jamming', scenario=scenario, composition=composition))


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


@admin.route('/jamming/edit_scenario/<int:id>')
@roles_required("admins")
def admin_jamming_edit_scenario(id=None):
    scenarios = JammingScenario.query
    configs = JammingConfig.query

    scenario = JammingScenario.query.filter_by(id=id).first()

    if (scenario == None):
        abort(404)

    jamming_scenario_dict = build_jamming_scenario_dict(scenario)
    jamming_config_dict = build_jamming_config_dict(configs.all())
    return render_template('admin/jamming_scenario.html', configs=configs.all(), scenarios=scenarios.all(), scenario=scenario, jamming_scenario_dict=jamming_scenario_dict, jamming_config_dict=jamming_config_dict, scenario_id=id)


@admin.route('/jamming/update_config/', methods=['POST'])
@admin.route('/jamming/update_config/<int:id>', methods=['POST'])
@roles_required("admins")
def admin_update_jamming_config(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        config = JammingConfig.query.filter_by(id=id).first()

        if(config == None):
            flash('Config does not exist!', 'error')
            return redirect(url_for('admin.admin_jamming'))
        else:

            name = request.form.get("name")
            channel = request.form.get("channel")
            power = request.form.get("power")
            length = request.form.get("length")
            period = request.form.get("period")

            if(name == None or channel == None or power == None or length == None or period == None):
                flash('Missing Data!', 'error')
                return redirect(url_for('admin.admin_benchmark_suite'))

            config.name = name
            config.channel = channel
            config.power = power
            config.length = length
            config.periode = period

            flash('Config ' + str(config.id) + ' updated!', 'success')
            db.session.commit()

    scenario = request.args.get('scenario')
    return redirect(url_for('admin.admin_jamming_edit_scenario', id=scenario))


@admin.route('/jamming/create_config')
@roles_required("admins")
def admin_create_jamming_config():

    config = JammingConfig("None", 0, 0, 13, 16)

    db.session.add(config)
    db.session.commit()

    scenario = request.args.get('scenario')

    flash('Config ' + str(config.id) + ' created!', 'success')
    return redirect(url_for('admin.admin_jamming_edit_scenario', id=scenario))


@admin.route('/jamming/edit_scenario/<int:id>/update', methods=["POST"])
@roles_required("admins")
def admin_jamming_edit_scenario_update(id=None):
    scenario = JammingScenario.query.filter_by(id=id).first()
    timings = JammingTiming.query.filter_by(scenario_id=scenario.id)

    old_sc = build_jamming_scenario_dict(scenario)
    new_sc = request.form.get("timings")

    nd = json.loads(new_sc)

    for s in nd:
        if isinstance(s['id'], str) and s['id'].startswith("dummy-"):
            c = JammingConfig.query.filter_by(id=int(s['cid'])).first()
            if(c == None):
                abort(404)
            t = JammingTiming(s['start'], c.id, scenario.id)
            flash('Added new timing for config {0} at {1}!'.format(
                s['content'], s['start']), 'success')
            db.session.add(t)
            continue

        t = JammingTiming.query.filter_by(id=s['id']).first()
        if not (t == None):
            if not (t.timestamp == int(s['start'])):
                flash('Updated time on {0} from {1} to {2}!'.format(
                    s['id'], t.timestamp, s['start']), 'success')
                ts = int(s['start'])
                if(s < 0):
                    abort(404)
                t.timestamp = int(s['start'])
        else:
            abort(404)

    for o in old_sc:
        found = False
        for n in nd:
            if n['id'] == o['id']:
                found = True
                break
        if not found:
            flash('Removed timing {0}!'.format(o['id']), 'success')
            t = JammingTiming.query.filter_by(id=o['id'])
            if t.first() == None or (not len(t.all()) == 1):
                abort(404)
            t.delete()

    db.session.commit()
    return redirect(url_for('admin.admin_jamming_edit_scenario', id=scenario.id))


@admin.route('/queue/delete_job/<int:id>')
@roles_required("admins")
def admin_delete_job(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        job = Job.query.filter_by(id=id).first()
        if(job == None):
            flash('Job does not exist!', 'error')
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
    return redirect(url_for('admin.admin_queue'))


@admin.route('/protocol/unlock/<int:id>')
@login_required
def unlock_protocol(id=None):
    if((id == None)):
        flash('Missing Data!', 'error')
        return redirect(url_for('frontend.index'))
    else:
        protocol = Protocol.query.filter_by(id=id).first()

        if(protocol == None):
            flash('Protocol does not exist!', 'error')
        else:
            protocol.final_job_id = None

            flash("Protocol %s unlocked!"%protocol.id, 'success')
            db.session.commit()
    return redirect(url_for('frontend.protocol_details',id=protocol.id))

