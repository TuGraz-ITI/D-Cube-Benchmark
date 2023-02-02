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

# This contains our frontend; since it is a bit messy to use the @app.route
# decorator style when using application factories, all of our routes are
# inside blueprints. This is the front-facing blueprint.
#
# You can find out more about blueprints at
# http://flask.pocoo.org/docs/blueprints/

from flask import Blueprint, render_template, flash, redirect, request, \
    Response, url_for, current_app, abort, jsonify
from flask_security import login_required, roles_required, current_user

from .helpers import maintenance_mode, check_scheduler_time, \
    check_jamming_time, key_gen, build_jamming_composition_dict, \
    build_node_dict, build_layout_dict

from models.user import User
from models.group import Group

from models.job import Job
from models.result import Result
from models.config import Config
from models.metric import Metric
from models.jamming_composition import JammingComposition
from models.layout_composition import LayoutComposition

from models.benchmark_suite import BenchmarkSuite
from models.benchmark_config import BenchmarkConfig

#placeholder
from models.node import Node
from models.protocol import Protocol

from backend.security import user_datastore
from backend.database import db

import requests

JOB_OVERHEAD = 120

frontend = Blueprint('frontend', __name__)

@frontend.before_app_first_request
def setup_defaults():
    db.create_all()

@frontend.route('/')
def wiki():
    return redirect(current_app.config['LANDING_PAGE'])

@frontend.route('/overview')
def index():
    page = (request.args.get('page'))
    if page is None:
        page = 1
    else:
        page = int(page, 10)
    return index_page(page)


def index_page(page=1):
    pagetitle = Config.get_string("pagetitle", "CPS Testbed")
    pagesubtitle = Config.get_string("pagesubtitle", None)

    if maintenance_mode():
        msg = Config.get_string("maintenance_msg", "")
        return render_template('index.html', jobs=None, upcomming=None,
                               est=0, msg=msg, pagetitle=pagetitle,
                               pagesubtitle=pagesubtitle)

    #results = Result.query.order_by(Result.id.desc()).limit(30).subquery()
    results = Result.query.order_by(Result.id.desc()).subquery()

    jobs = Job.query.join(results).order_by(
        results.c.begin.desc())

    if(page == -1):
        xjobs = jobs.paginate(page=1, per_page=30)
        last = xjobs.pages
        if last == 0:
            last = 1
        jobs = jobs.paginate(page=last, per_page=30)
    else:
        jobs = jobs.paginate(page=page, per_page=30)

    #jobs = Job.query.join(results).order_by(
    #    results.c.begin.desc()).limit(30).all()

    if page==1:
        running = Job.query.filter(Job.running == True).first()
        if not (running is None):
            jobs.items = [running, ] + jobs.items
    else:
        running=None

    upcomming = Job.query.filter((Job.finished == False) & (
        Job.running == False)).order_by(Job.id.asc())
    num_upcomming=upcomming.count()
    upcomming=upcomming.limit(30).all()

    j = Job.query.filter_by(finished=False)
    est = 0.0
    for job in j:
        est += ((job.duration + JOB_OVERHEAD) / 60.0)

    return render_template('index.html',
                           jobs=jobs,
                           running=running,
                           upcomming=upcomming,
                           num_upcomming=num_upcomming,
                           est=est,
                           pagetitle=pagetitle,
                           pagesubtitle=pagesubtitle,
                           )


@frontend.route('/proxy/nodes/')
@frontend.route('/proxy/nodes/<int:composition_id>')
def show_nodes(composition_id=None):
    composition = LayoutComposition.query.filter_by(id=composition_id).first()
    if(composition is None):
        abort(404)
    return jsonify(build_node_dict(composition))


@frontend.route('/proxy/dashboards')
def proxy_dashboards():
    if (current_app.config['GRAFANA_URL'].startswith("https://")) or \
            (current_app.config['GRAFANA_URL'].startswith("http://")):
        url_prefix = ""
    else:
        url_prefix = "http://localhost"
    url = url_prefix + current_app.config['GRAFANA_URL'] + \
        "/api/search" + current_app.config['GRAFANA_DASHBOARD_FOLDER']
    r = requests.get(url)
    headers = dict(r.headers)

    def generate():
        for chunk in r.iter_content(1024):
            yield chunk

    return Response(generate(), headers=headers)

@frontend.route('/proxy/dashboards/templab')
def proxy_templab_dashboards():
    if (current_app.config['GRAFANA_URL'].startswith("https://")) or \
            (current_app.config['GRAFANA_URL'].startswith("http://")):
        url_prefix = ""
    else:
        url_prefix = "http://localhost"
    url = url_prefix + current_app.config['GRAFANA_URL'] + \
        "/api/search" + current_app.config['GRAFANA_TEMPLAB_FOLDER']
    r = requests.get(url)
    headers = dict(r.headers)

    def generate():
        for chunk in r.iter_content(1024):
            yield chunk
    return Response(generate(), headers=headers)

@frontend.route('/layout')
def show_layout():
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    benchmark_suites = BenchmarkSuite.query
    benchmark_suite = request.args.get("benchmark_suite")
    if (benchmark_suite is None):
        benchmark_suite = benchmark_suites.first()
    else:
        benchmark_suite = benchmark_suites.filter_by(id=int(benchmark_suite)).first()
        if(benchmark_suite is None):
            benchmark_suite = benchmark_suites.first()

    if (benchmark_suite is not None):
        composition = request.args.get("composition")
        compositions = LayoutComposition.query.filter_by(benchmark_suite_id=benchmark_suite.id)
        if (composition is None):
            composition = compositions.first()
        else:
            composition = compositions.filter_by(id=int(composition)).first()
            if(composition is None):
                composition = compositions.first()
        layout_dict = build_layout_dict(composition, show_unused=False)
    else:
        composition = None
        compositions = LayoutComposition.query
        layout_dict = {"nodes": [], "edges": []}

    return render_template('layout.html',
                           benchmark_suites=benchmark_suites.all(),
                           benchmark_suite=benchmark_suite,
                           compositions=compositions.all(),
                           composition=composition,
                           layout_dict=layout_dict)


@frontend.route('/jamming')
@roles_required("admins")
def show_jamming():
    composition = request.args.get("composition")
    compositions = JammingComposition.query
    if (composition is None):
        composition = compositions.first()
    else:
        composition = compositions.filter_by(id=int(composition)).first()
        if(composition is None):
            composition = compositions.first()

    if (composition is not None):
        preview_dict = build_jamming_composition_dict(composition)
    else:
        preview_dict = {"items": [], "groups": []}

    return render_template('jamming.html',
                           composition=composition,
                           compositions=compositions.all(),
                           preview_dict=preview_dict)


@frontend.route('/user/apikey/generate')
@login_required
def user_generate_api_key():
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    if current_user.api_key is None:
        current_user.api_key = key_gen()
        db.session.commit()
        flash('API key for User ' + current_user.username +
              ' generated!', 'success')
        return redirect(url_for('frontend.user_manage_api_key'))
    else:
        flash('User ' + current_user.username +
              ' already has an API key!', 'error')
        return redirect(url_for('frontend.user_manage_api_key'))


@frontend.route('/user/apikey')
@login_required
def user_manage_api_key():
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    return render_template('api_key.html')


@frontend.route('/user/apikey/delete')
@login_required
def user_delete_api_key():
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    if current_user.api_key is None:
        flash('User ' + current_user.username + ' has no API key!', 'error')
        return redirect(url_for('frontend.user_manage_api_key'))

    current_user.api_key = None
    db.session.commit()
    flash('API key for User ' + current_user.username + ' deleted!', 'success')
    return redirect(url_for('frontend.user_manage_api_key'))


@frontend.route('/protocol')
@login_required
def show_protocols():
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    protocols=Protocol.query.filter_by(group_id=current_user.group.id).all()
    benchmark_suites=BenchmarkSuite.query

    if not (current_user.has_role("sky")):
        benchmark_suites=benchmark_suites.filter(~BenchmarkSuite.node.has(Node.name.contains("Sky")))

    if not (current_user.has_role("nordic")):
        benchmark_suites=benchmark_suites.filter(~BenchmarkSuite.node.has(Node.name.contains("Nordic")))



    return render_template('protocols.html', protocols=protocols,
                                             benchmark_suites=benchmark_suites.all())


@frontend.route('/protocol/delete/<int:id>')
@login_required
def delete_protocol(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        protocol = Protocol.query.filter_by(id=id).first()
        if not protocol.group == current_user.group:
            flash('Protocol belongs do a different group!', 'error')
            return redirect(url_for('frontend.show_protocols'))

        if(protocol == None):
            flash('Protocol does not exist!', 'error')
        else:
            flash("Protocol %s deleted!"%protocol.id, 'success')

            db.session.delete(protocol)
            db.session.commit()
    return redirect(url_for('frontend.show_protocols'))


@frontend.route('/protocol/update/', methods=['POST'])
@frontend.route('/protocol/update/<int:id>', methods=['POST'])
@login_required
def update_protocol(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    if((id == None)):
        flash('Missing Data!', 'error')
    else:
        protocol = Protocol.query.filter_by(id=id).first()
        if not protocol.group == current_user.group:
            flash('Protocol belongs do a different group!', 'error')
            return redirect(url_for('frontend.show_protocols'))

        if(protocol == None):
            flash('Protocol does not exist!', 'error')
        else:
            name = request.form.get("name")
            link = request.form.get("link")
            description = request.form.get("description")

            if(name == None or link == None or description == None):
                flash('Missing Protocol Data!', 'error')
                return redirect(url_for('frontend.show_protocols'))

            protocol.name = name
            protocol.link = link
            protocol.description = description

            flash("Protocol %s updated!"%protocol.id, 'success')
            db.session.commit()
    return redirect(url_for('frontend.show_protocols'))


@frontend.route('/protocol/finalize/', methods=['POST'])
@frontend.route('/protocol/finalize/<int:id>', methods=['POST'])
@login_required
def finalize_protocol(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    if((id == None)):
        flash('Missing Data!', 'error')
        return redirect(url_for('frontend.show_protocols'))
    else:
        protocol = Protocol.query.filter_by(id=id).first()
        if not protocol.group == current_user.group:
            flash('Protocol belongs do a different group!', 'error')
            return redirect(url_for('frontend.show_protocols'))

        if(protocol == None):
            flash('Protocol does not exist!', 'error')
        else:
            final_job_id = request.form.get("final_job")
            final_job = Job.query.filter_by(id=final_job_id).filter_by(protocol_id=protocol.id).first()

            if(final_job == None):
                flash('Invalid Job selected!', 'error')
                return redirect(url_for('frontend.protocol_details',id=protocol.id))

            if(protocol.final_job):
                flash('Protocol already finalized!', 'error')
                return redirect(url_for('frontend.protocol_details',id=protocol.id))

            protocol.final_job_id = final_job_id

            flash("Protocol %s finalized!"%protocol.id, 'success')
            db.session.commit()
    return redirect(url_for('frontend.protocol_details',id=protocol.id))


@frontend.route('/protocol/create/', methods=['POST'])
@login_required
def create_protocol():
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    name = request.form.get("name")
    link = request.form.get("link")
    description = request.form.get("description")

    group=current_user.group
    group_id=group.id
    benchmark_suite_id = request.form.get("benchmark_suite")
    benchmark_suite_id = int(benchmark_suite_id)
    benchmark_suite=BenchmarkSuite.query.filter_by(id=benchmark_suite_id).first()

    if(name == None or link == None or description == None or group == None or benchmark_suite == None):
        flash('Missing Protocol Data!', 'error')
        return redirect(url_for('frontend.show_protocols'))

    protocol = Protocol(name,link,description,group_id,benchmark_suite_id)
    db.session.add(protocol)
    db.session.commit()
    flash("Protocol %s created!"%protocol.id, 'success')
    return redirect(url_for('frontend.show_protocols'))


@frontend.route("/protocol/show/<int:id>")
@login_required
def protocol_details(id=None):
    if maintenance_mode():
        return redirect(url_for('frontend.index'))

    if id==None:
        flash("Missing Data!","error")
        return redirect(url_for('frontend.index'))

    protocol=Protocol.query.filter_by(id=id).first()

    if protocol==None:
        abort(404)

    if not protocol.group.id==current_user.group.id:
        abort(401)

    return render_template('protocol_details.html',protocol=protocol)
