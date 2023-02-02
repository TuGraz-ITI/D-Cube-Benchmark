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
from flask import Blueprint, render_template, flash, redirect, request, \
    Response, url_for, current_app, abort, jsonify

from flask_security import login_required, roles_required, current_user

from models.config import Config
from models.job import Job
from models.group import Group
from models.metric import Metric
from models.jamming_composition import JammingComposition
from models.layout_composition import LayoutComposition
from models.benchmark_suite import BenchmarkSuite
from models.protocol import Protocol

import pandas as pd
import numpy as np

# generate bar charts
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import io
import base64

POINTS = [9, 6, 4, 3, 2, 1]
LENGTHS = [8, 32, 64]
PERIODS = [0, 5000, 30000]

COEFF_REL = 20.0
COEFF_ENERGY = 1.0
COEFF_LATENCY = 1.0
THRESHOLD = 30.0
MARGIN = 10.0
NUMBARS = 30

leaderboard = Blueprint('leaderboard', __name__)

@leaderboard.route('/benchmarksuite/<int:benchmark_suite_id>')
def show_benchmark_suite(benchmark_suite_id=None):
    metrics = Metric.query
    if not (current_user.is_authenticated and current_user.has_role("admins")):
        metrics = metrics.filter(Job.id>20828)
        metrics = metrics.filter(Job.group.has(Group.id>1))

    jammings = JammingComposition.query
    jamming = request.args.get("jamming")

    if not "duration" in request.args:
        duration = None
    else:
        duration = request.args.get("duration")

    if not "logs" in request.args:
        logs = None
    else:
        logs = request.args.get("logs")


    if (jamming == None):
        jam = jammings.first()
        jamming = jam.id

    if not jamming == "any":
        try:
            ijam = int(jamming)
        except ValueError:
            ijam = 0
        jam = jammings.filter_by(id=ijam).first()
        if (jam == None):
            jam = jammings.first()
            jamming = jam.id

        metrics = metrics.filter(Metric.job.has(
            Job.jamming_composition_id == int(jamming)))

    benchmark_suites = BenchmarkSuite.query
    #benchmark_suite = request.args.get("benchmark_suite")
    benchmark_suite = benchmark_suites.filter(BenchmarkSuite.id==benchmark_suite_id).first()
    if benchmark_suite==None:
        abort(404)

    layouts = LayoutComposition.query
    layout = request.args.get("layout")

    #if (benchmark_suite == None):
    #    cat = benchmark_suites.first()
    #    benchmark_suite = cat.id

    #if not (benchmark_suite == "any"):
    #    try:
    #        icat = int(benchmark_suite)
    #    except ValueError:
    #        icat = 0
    #    cat = benchmark_suites.filter_by(id=icat).first()
    #    if(cat == None):
    #        cat = benchmark_suites.first()
    #        benchmark_suite = cat.id
    layouts = layouts.filter_by(benchmark_suite_id=benchmark_suite_id)
    metrics = metrics.filter(Metric.job.has(Job.layout.has(
        LayoutComposition.benchmark_suite_id == benchmark_suite_id)))
    #else:
    #    layout = "any"

    if (layout == None):
        lay = layouts.first()
        layout = lay.id

    if not layout == "any":
        try:
            ilay = int(layout)
        except ValueError:
            ilay = 0

        lay = layouts.filter_by(id=ilay).first()
        if(lay == None):
            lay = layouts.first()
            layout = lay.id
        metrics = metrics.filter(Metric.job.has(
            Job.layout_composition_id == int(layout)))

    period = request.args.get("period")

    if (period == None):
        period = 0

    if not (period == "any" or period == "periodic"):
        try:
            period = int(period)
        except ValueError:
            period = 0
        if not period in PERIODS:
            period = 0

        metrics = metrics.filter(Metric.job.has(Job.traffic_load == period))

    if period == "periodic":
        metrics = metrics.filter(Metric.job.has(Job.traffic_load != 0))

    length = request.args.get("length")

    if (length == None):
        length = 8

    if not length == "any":
        try:
            length = int(length)
        except ValueError:
            length = 0
        if not length in LENGTHS:
            length = 8

        metrics = metrics.filter(Metric.job.has(Job.msg_len == length))

    if not duration == "any":
        try:
            duration = int(duration)
        except (ValueError,TypeError):
            duration = None

        if duration == None:
            duration = 600

        metrics = metrics.filter(Metric.job.has(Job.duration == duration))

    if not logs == "any":
        try:
            logs = True if (logs=="True" or logs=="true") else False
        except (ValueError,TypeError):
            logs = None

        if logs == None:
            logs=False

        metrics = metrics.filter(Metric.job.has(Job.logs == logs))


#    metrics = metrics.filter(Metric.job.has(Job.logs == False))

#    metrics = metrics.filter(Metric.job.has(Job.id >= FIRST_JOB)).filter(
#        Metric.job.has(Job.id <= LAST_JOB))
    metrics = metrics.join(Job, (Job.id==Metric.job_id)).join(Protocol, (Protocol.id==Job.protocol_id)).add_columns(Protocol.name.label("protocol")).add_columns(Protocol.id.label("pid"))


    count = request.args.get("count")

    try:
        df = pd.read_sql(metrics.statement, metrics.session.bind)
    
        df['latency'] = df['latency']/1000
        df['plot_reliability'] = df['reliability']*100
    
        min_energy = df['energy'].min()
        min_latency = df['latency'].min()
        max_reliability = df['reliability'].max()
    
        df['rel_energy'] = (df['energy']-min_energy)/min_energy
        df['rel_latency'] = (df['latency']-min_latency)/min_latency
        df['rel_reliability'] = (max_reliability-df['reliability'])/max_reliability
    
        df['total'] = df['rel_energy']*COEFF_ENERGY+df['rel_latency'] * \
            COEFF_LATENCY+df['rel_reliability']*COEFF_REL
        df = df.sort_values("total")
        df['plot_total'] = df['total']*100
        df['points'] = 0
    
        if (count == None):
            count = "median"
    
        if count == "median":
            try:
                df_mean = df.groupby("protocol").agg(
                    np.median).reset_index(drop=False)
                df_count = df.groupby("protocol").count().reset_index(drop=False)
                df_mean["count"] = df_count["total"]
                df = df_mean
                df = df[df.reliability >= (THRESHOLD/100.0)]
                df = df.sort_values("total")
            except Exception as e:
                pass
    
        else:
            try:
                count = int(count)
            except ValueError:
                count = 1
    
            if not (count == 0):
                df = df.groupby("protocol").head(count).reset_index(drop=True)
    
        df = df.reset_index(drop=True)
    
        try:
            df['rel_total'] = df['total']/df['total'].min()
            df['diff_total'] = df['total']-df['total'].min()
        except KeyError:
            pass
    
        try:
            df = df.sort_values(["total", "id"])
        except KeyError:
            pass
    
        if(len(df) < NUMBARS):
    
            try:
                f, axs = plt.subplots(1, 3)
                df.plot(ax=axs[0], kind="bar", x="pid", y="energy", figsize=(
                    12, 4), edgecolor="k", legend=False)
                df.plot(ax=axs[1], kind="bar", x="pid", y="latency", figsize=(
                    12, 4), edgecolor="k", legend=False)
                df.plot(ax=axs[2], kind="bar", x="pid", y="plot_reliability", figsize=(
                    12, 4), edgecolor="k", legend=False)
                axs[0].set_ylabel("Energy [J]")
                axs[0].set_xlabel("Protocol ID")
                axs[1].set_ylabel("Latency [ms]")
                axs[1].set_xlabel("Protocol ID")
                axs[1].set_ylim(0, df['latency'].median()*3)
                axs[2].set_ylabel("Reliablity [%]")
                axs[2].set_xlabel("Protocol ID")
                (min2, max2) = axs[2].set_ylim()
                axs[2].set_ylim(0, max2)
                plt.tight_layout()
                output = io.BytesIO()
                plt.savefig(output, format='png')
                plt.close()
                output.seek(0)
                png = base64.b64encode(output.getvalue()).decode()
            except (ValueError,TypeError,KeyError):
                png = None
                plt.close()
        else:
            png = None
    
    except AttributeError:
        df=pd.DataFrame()
        png=None
        pass

    durations_string = Config.get_string("durations", "120 480")
    durations = map(int, durations_string.split())


    return render_template('shiny_leaderboard.html', df=df, 
                                                     jammings=jammings, 
                                                     jamming=jamming,
                                                     count=count,
                                                     png=png,
                                                     periods=PERIODS,
                                                     period=period,
                                                     lengths=LENGTHS,
                                                     length=length,
                                                     layouts=layouts,
                                                     layout=layout,
                                                     benchmark_suite=benchmark_suite,
                                                     duration=duration,
                                                     durations=durations,
                                                     )
