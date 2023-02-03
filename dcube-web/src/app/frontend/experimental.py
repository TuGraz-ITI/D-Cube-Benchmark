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
from flask import Blueprint, redirect, request, render_template, current_app, url_for, flash
from flask_security import login_required, roles_required, current_user
from werkzeug.utils import secure_filename

from helpers import *

from models.user import User
from models.group import Group

from models.job import Job
from models.firmware import Firmware

from models.jamming_pi import JammingPi
from models.jamming_scenario import JammingScenario
from models.jamming_timing import JammingTiming
from models.jamming_config import JammingConfig
from models.jamming_composition import JammingComposition

from models.layout_pi import LayoutPi
from models.layout_composition import LayoutComposition
from models.layout_category import LayoutCategory

from backend.database import db
from backend.security import user_datastore

from frontend import maintenance_mode, frontend

import calendar
import os

experimental = Blueprint('experimental', __name__)

import pandas as pd
import numpy as np
import collections

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import io
import base64


@experimental.route('/admin/leaderboard/sum/')
@roles_required("admins")
def admin_leaderboard_sum():
    durations_string = Config.get_string("durations", "30 60 120 180 300")
    durations = map(int, durations_string.split())
    def_duration = Config.get_int("def_duration", 300)

    jammings = JammingComposition.query

    categories = LayoutCategory.query
    layouts = LayoutComposition.query

    periods = [0, 5000, 30000]
    lengths = [8, 32, 64]
    return render_template('admin/leaderboard_sum.html', durations=durations, jammings=jammings, def_duration=def_duration, categories=categories,
                           layouts=layouts, periods=periods, lengths=lengths)


@experimental.route('/admin/leaderboard/')
@roles_required("admins")
def admin_leaderboard():
    metrics = Metric.query

    do_json = request.args.get("json")
    if (do_json == None):
        do_json = False
    else:
        do_json = True

    show_failed = request.args.get("failed")
    if (show_failed == None):
        show_failed = False
    else:
        if(show_failed == "show"):
            show_failed = True
        else:
            show_failed = False

    do_sort = request.args.get("sort")
    if (do_sort == None):
        do_sort = "total"
    else:
        if not (do_sort == "total" or do_sort == "job_name"):
            do_sort = "total"

    threshold = request.args.get("threshold")
    if (threshold == None):
        threshold = 0.0
    else:
        threshold = float(threshold)

    margin = request.args.get("margin")
    if (margin == None):
        margin = 0.0
    else:
        margin = float(margin)/100.0

    points = request.args.get("points")
    if (points == None):
        points = "5,4,3,2,1"
        # points=""

    if(threshold > 0):
        metrics = Metric.query.filter(Metric.reliability != None).filter(
            Metric.reliability >= threshold/100.0)

    coeff_rel = request.args.get("coeff_rel")
    if (coeff_rel == None):
        coeff_rel = 1.0
    else:
        coeff_rel = float(coeff_rel)

    coeff_energy = request.args.get("coeff_energy")
    if (coeff_energy == None):
        coeff_energy = 1.0
    else:
        coeff_energy = float(coeff_energy)

    coeff_latency = request.args.get("coeff_latency")
    if (coeff_latency == None):
        coeff_latency = 1.0
    else:
        coeff_latency = float(coeff_latency)

    jammings = JammingComposition.query
    jamming = request.args.get("jamming")

    if (jamming == None):
        jam = jammings.first()
        jamming = jam.id
        # jamming=Config.get_int("jamming_max",0)

    if not jamming == "any":
        jam = jammings.filter_by(id=int(jamming)).first()
        if (jam == None):
            jam = jammings.first()
            jamming = jam.id

        metrics = metrics.filter(Metric.job.has(
            Job.jamming_composition_id == int(jamming)))

    categories = LayoutCategory.query
    category = request.args.get("category")

    layouts = LayoutComposition.query
    layout = request.args.get("layout")

    if (category == None):
        cat = categories.first()
        category = cat.id

    if not (category == "any"):
        cat = categories.filter_by(id=int(category)).first()
        if(cat == None):
            cat = categories.first()
            category = cat.id
        layouts = layouts.filter_by(category_id=category)
        metrics = metrics.filter(Metric.job.has(Job.layout.has(
            LayoutComposition.category_id == int(category))))
    else:
        layout = "any"

    if (layout == None):
        lay = layouts.first()
        layout = lay.id

    if not layout == "any":
        lay = layouts.filter_by(id=int(layout)).first()
        if(lay == None):
            lay = layouts.first()
            layout = lay.id
        metrics = metrics.filter(Metric.job.has(
            Job.layout_composition_id == int(layout)))

    # TODO put me somewhere and merge with traffic_load
    periods = [0, 5000, 30000]
    period = request.args.get("period")

    if (period == None):
        period = 0

    if not (period == "any" or period == "periodic"):
        period = int(period)
        if not period in periods:
            period = 0

        metrics = metrics.filter(Metric.job.has(Job.traffic_load == period))

    if period == "periodic":
        metrics = metrics.filter(Metric.job.has(Job.traffic_load != 0))

    # TODO put me somewhere and merge with msg_len
    lengths = [8, 32, 64]
    length = request.args.get("length")

    if (length == None):
        length = 8

    if not length == "any":
        length = int(length)
        if not length in lengths:
            length = 8

        metrics = metrics.filter(Metric.job.has(Job.msg_len == length))

    duration = request.args.get("duration")
    if (duration == None):
        duration = Config.get_int("def_duration", 300)
    if not duration == "any":
        metrics = metrics.filter(Metric.job.has(Job.duration == int(duration)))

#    metrics=metrics.filter(Metric.job.has(Job.id>3000))

#    metrics=metrics.filter(Metric.job.has(Job.duration==4200))
    metrics = metrics.filter(Metric.job.has(Job.logs == False))
#    metrics=metrics.filter(Metric.job!=None).filter(Metric.latency!=None).filter(Metric.reliability!=None).filter(Metric.reliability<=1).filter(Metric.reliability>0.5)
#    metrics=metrics.filter(Metric.job.has(Job.jamming_composition.has(JammingComposition.id==jamming)))

    metrics = metrics.filter(Metric.job.has(Job.id > FIRST_JOB)).join(Job).join(Group).add_columns(Group.name).join(
        Firmware).add_columns(Firmware.name.label("filename")).add_columns(Job.description).add_columns(Job.name.label("job_name"))

    df = pd.read_sql(metrics.statement, metrics.session.bind)
    if(show_failed == False):
        df = df.dropna()

    df['latency'] = df['latency']/1000
    df['plot_reliability'] = df['reliability']*100

    min_energy = df['energy'].min()
    min_latency = df['latency'].min()
    max_reliability = df['reliability'].max()

    df['rel_energy'] = (df['energy']-min_energy)/min_energy*coeff_energy
    df['rel_latency'] = (df['latency']-min_latency)/min_latency*coeff_latency
    df['rel_reliability'] = (
        max_reliability-df['reliability'])/max_reliability*coeff_rel

    df['total'] = df['rel_energy']+df['rel_latency']+df['rel_reliability']
    # df=df.sort_values("total")
    df = df.sort_values("total")
    df['plot_total'] = df['total']*100
    df['points'] = 0

    df.job_name = df.job_name.str.slice(4)

    count = request.args.get("count")
    if (count == None):
        count = 0

    if count == "stats":
        try:
            df_mean = df.groupby("job_name").agg(
                np.mean).reset_index(drop=False)
            df_count = df.groupby("job_name").count().reset_index(drop=False)
            df_var = df.groupby("job_name").agg(
                np.std, ddof=0).reset_index(drop=False)
            df_mean["energy_var"] = df_var["energy"]
            df_mean["latency_var"] = df_var["latency"]
            df_mean["reliability_var"] = df_var["plot_reliability"]
            df_mean["total_var"] = df_var["plot_total"]
            df_mean["count"] = df_count["total"]
            df = df_mean
            df = df.sort_values("total")
            capsize = 4

        except Exception:
            df["energy_var"] = 0
            df["latency_var"] = 0
            df["reliability_var"] = 0
            df["total_var"] = 0
            capsize = 0

    elif count == "median":
        try:
            df_mean = df.groupby("job_name").agg(
                np.median).reset_index(drop=False)
            df_count = df.groupby("job_name").count().reset_index(drop=False)
            df_mean["energy_var"] = 0
            df_mean["latency_var"] = 0
            df_mean["reliability_var"] = 0
            df_mean["total_var"] = 0
            df_mean["count"] = df_count["total"]
            df = df_mean
            df = df.sort_values("total")
            capsize = 0

        except Exception:
            df["energy_var"] = 0
            df["latency_var"] = 0
            df["reliability_var"] = 0
            df["total_var"] = 0
            capsize = 0

    else:
        count = int(count)
        df["energy_var"] = 0
        df["latency_var"] = 0
        df["reliability_var"] = 0
        df["total_var"] = 0
        capsize = 0

        if not (count == 0):
            df = df.groupby("job_name").head(count).reset_index(drop=True)
            # df=df.groupby("description").head(count).reset_index(drop=True)

    df = df.reset_index(drop=True)

    try:
        df['rel_total'] = df['total']/df['total'].min()
        df['diff_total'] = df['total']-df['total'].min()
        # df['plot_total']=df['plot_total']-df['plot_total'].min()
    except KeyError:
        pass

    if ('rel_total' in df.columns) and (count == "stats" or count == "median" or count == 1):
        pt = points.split(",")
        idx = 0
        idxh = 0

        diff = df['rel_total'].diff()
        for p in pt:
            if idx > (len(df)-1):
                break

            if(idxh > 0):
                idxh -= 1
                continue

            sigma = True
            while(sigma):
                sigma = False
                try:
                    if(diff.at[idx+1] < margin):
                        idxh += 1
                        sigma = True
                except KeyError:
                    pass

                df.at[idx, 'points'] = p
                idx += 1

    durations_string = Config.get_string("durations", "30 60 120 180 300")
    durations = map(int, durations_string.split())

    if(do_json):
        di = {}
        di['data'] = json.loads(df.to_json())
        di['settings'] = {
            'duration': duration,
            'jamming': jamming,
            'category': category,
            'layout': layout,
            'period': period,
            'msg_len': length
        }
        return jsonify(di)

    try:
        df = df.sort_values([do_sort, "id"])
    except KeyError:
        pass

    # colors=cm.rainbow(np.linspace(0,1,TEAMS+1))
    colors = cm.rainbow(np.linspace(0, 1, TEAMS+1))
    cmap = []
    for d in df["job_name"]:
        cmap.append(colors[int(d)])

    try:
        f, axs = plt.subplots(1, 4)
        # df.plot(ax=axs[0],kind="bar",x="job_name",y="energy",yerr="energy_var",capsize=capsize,figsize=(12,4),color="0.8",edgecolor="k",legend=False)
        df.plot(ax=axs[0], kind="bar", x="job_name", y="energy", yerr="energy_var",
                capsize=capsize, figsize=(12, 4), edgecolor="k", legend=False, color=cmap)
        # df.plot(ax=axs[1],kind="bar",x="job_name",y="latency",yerr="latency_var",capsize=capsize,figsize=(12,4),color="0.6",edgecolor="k",legend=False)
        df.plot(ax=axs[1], kind="bar", x="job_name", y="latency", yerr="latency_var",
                capsize=capsize, figsize=(12, 4), edgecolor="k", legend=False, color=cmap)
        # df.plot(ax=axs[2],kind="bar",x="job_name",y="plot_reliability",yerr="reliability_var",capsize=capsize,figsize=(12,4),color="0.4",edgecolor="k",legend=False)
        df.plot(ax=axs[2], kind="bar", x="job_name", y="plot_reliability", yerr="reliability_var",
                capsize=capsize, figsize=(12, 4), edgecolor="k", legend=False, color=cmap)
        # df.plot(ax=axs[3],kind="bar",x="job_name",y="plot_total",yerr="total_var",capsize=capsize,figsize=(12,4),color="0.2",edgecolor="k",legend=False)
        df.plot(ax=axs[3], kind="bar", x="job_name", y="plot_total", yerr="total_var",
                capsize=capsize, figsize=(12, 4), edgecolor="k", legend=False, color=cmap)
        axs[0].set_ylabel("Energy [J]")
        axs[0].set_xlabel("Team")
        axs[1].set_ylabel("Latency [ms]")
        axs[1].set_xlabel("Team")
        axs[1].set_ylim(0, df['latency'].median()*3)
        axs[2].set_ylabel("Reliablity [%]")
        axs[2].set_xlabel("Team")
        (min2, max2) = axs[2].set_ylim()
        axs[2].set_ylim(0, max2)
        axs[3].set_ylabel("Total [%]")
        axs[3].set_xlabel("Team")
        if(df['plot_total'].max() > df['plot_total'].median()*3):
            axs[3].set_ylim(df['plot_total'].min(),
                            df['plot_total'].median()*3)
        else:
            (min3, max3) = axs[3].set_ylim()
            axs[3].set_ylim(df['plot_total'].min(), max3)
        plt.tight_layout()

        output = io.BytesIO()
        plt.savefig(output, format='png')
        output.seek(0)
        png = base64.b64encode(output.getvalue())
    except TypeError:
        png = None
    except KeyError:
        png = None

    return render_template('admin/leaderboard.html', df=df, jammings=jammings, jamming=jamming, count=count, min_energy=min_energy, min_latency=min_latency, png=png,
                           max_reliability=max_reliability, coeff_energy=coeff_energy, coeff_rel=coeff_rel, coeff_latency=coeff_latency, durations=durations, default_duration=duration,
                           periods=periods, period=period, lengths=lengths, length=length, layouts=layouts, layout=layout, categories=categories, category=category,
                           threshold=threshold, points=points, margin=margin*100, show_failed=show_failed, do_sort=do_sort)


def admin_make_all_df(jamming):
    metrics = Metric.query

    jamming_str = jamming
    if(jamming == "super"):
        metrics = metrics.filter(Metric.job.has(
            (Job.duration == 1800) | (Job.duration == 4200)))
        metrics = metrics.filter(~Metric.job.has(Job.jamming == 0))
        metrics = metrics.filter(~Metric.job.has(Job.jamming == 3))
    elif(jamming == "any"):
        metrics = metrics.filter(Metric.job.has(
            (Job.duration == 1800) | (Job.duration == 4200)))
        metrics = metrics.filter(~Metric.job.has(Job.jamming == 3))
        # metrics=metrics.filter(~Metric.job.has(Job.jamming==0))
        # metrics=metrics.filter(~Metric.job.has(Job.jamming==3))
    else:
        if (jamming == None):
            jamming = 7
        else:
            jamming = int(jamming)

        if((jamming == 7) or (jamming == 11)):
            duration = 4200
        else:
            duration = 1800
        metrics = metrics.filter(Metric.job.has(Job.jamming == jamming))
        metrics = metrics.filter(Metric.job.has(Job.duration == duration))

    metrics = metrics.filter(Metric.job.has(Job.logs == False))
    metrics = metrics.filter(Metric.job.has(Job.id >= 5588))
    metrics = metrics.filter(Metric.job.has(Job.id <= 5859))
    metrics = metrics.filter(~Metric.job.has(Job.id == 5597))
    metrics = metrics.filter(~Metric.job.has(Job.id == 5791))
    metrics = metrics.filter(~Metric.job.has(Job.id == 5852))
    metrics = metrics.join(Job).add_columns(Job.description)

    df = pd.read_sql(metrics.statement, metrics.session.bind)

    line = df.loc[(df["job_id"] == 5829)].copy()
    if(len(line) > 0):
        line["job_id"] = 99999
        df = df.append(line)

    # df=df.dropna()
    try:
        df['latency'] = df['latency']/1000
    except KeyError:
        df['latency'] = None

    df = df.fillna(value=np.nan)

    try:
        df['reliability'] = df['reliability']*100
    except KeyError:
        df['reliability'] = 0

    df_tmp = df.groupby("description").agg(np.mean).reset_index(drop=False)
    df_mean = pd.DataFrame()
    df_mean['description'] = df_tmp['description']
    df_mean[jamming_str+'-energy'] = df_tmp['energy']
    df_mean[jamming_str+'-reliability'] = df_tmp['reliability']
    df_mean[jamming_str+'-latency'] = df_tmp['latency']

    df_mean = df_mean.reindex([0, 1, 2, 4, 6, 8, 7, 3, 5])
    # df_mean=df_mean.reindex([0,1,2,4,6,3,5,7,8])
    # df_mean=df_mean.reindex([2,1,4,0,6,8,7,3,5])
    df_mean['description'] = df_mean['description'].str.replace(
        "Team", re.escape("Team\\n"))

    return df_mean


def admin_make_eval_df(jamming, scenario):
    evaluations = Evaluation.query
    jamming_str = jamming
    if(jamming == "super"):
        evaluations = evaluations.filter(Evaluation.scenario.has(
            Scenario.job.has((Job.duration == 1800) | (Job.duration == 4200))))
        evaluations = evaluations.filter(
            ~Evaluation.scenario.has(Scenario.job.has(Job.jamming == 0)))
        evaluations = evaluations.filter(
            ~Evaluation.scenario.has(Scenario.job.has(Job.jamming == 3)))
    elif(jamming == "any"):
        evaluations = evaluations.filter(Evaluation.scenario.has(
            Scenario.job.has((Job.duration == 1800) | (Job.duration == 4200))))
        evaluations = evaluations.filter(
            ~Evaluation.scenario.has(Scenario.job.has(Job.jamming == 3)))
    else:
        if (jamming == None):
            jamming = 7
        else:
            jamming = int(jamming)

        if((jamming == 7) or (jamming == 11)):
            duration = 4200
        else:
            duration = 1800
        evaluations = evaluations.filter(Evaluation.scenario.has(
            Scenario.job.has(Job.jamming == jamming)))
        evaluations = evaluations.filter(Evaluation.scenario.has(
            Scenario.job.has(Job.duration == duration)))

    evaluations = evaluations.filter((Evaluation.key == "Reliability [%]") | (
        Evaluation.key == ["Latency combined [us]"]) | (Evaluation.key == "Total Energy [J]"))
    evaluations = evaluations.filter(
        Evaluation.scenario.has(Scenario.job.has(Job.id >= 5588)))
    evaluations = evaluations.filter(
        Evaluation.scenario.has(Scenario.job.has(Job.id <= 5859)))
    evaluations = evaluations.filter(
        ~Evaluation.scenario.has(Scenario.job.has(Job.id == 5597)))
    evaluations = evaluations.filter(
        ~Evaluation.scenario.has(Scenario.job.has(Job.id == 5791)))
    evaluations = evaluations.filter(
        ~Evaluation.scenario.has(Scenario.job.has(Job.id == 5852)))
    evaluations = evaluations.filter(
        Evaluation.scenario.has(Scenario.job.has(Job.logs == False)))
    evaluations = evaluations.join(Scenario).add_columns(Scenario.source).add_columns(Scenario.destination).add_columns(
        Scenario.job_id).join(Job).add_column(Job.description).add_columns(Scenario.job_id)

    df = pd.read_sql(evaluations.statement, evaluations.session.bind)
    df = df.dropna()

    line = df.loc[(df["job_id"] == 5829)].copy()
    if(len(line) > 0):
        line["job_id"] = 99999
        df = df.append(line)

    if(scenario == "p2p"):
        df = df.loc[((df["source"] == "118") & (df["destination"] == "209")) | ((df["source"] == "206") & (
            df["destination"] == "210")) | ((df["source"] == "213") & (df["destination"] == "225"))]
    elif(scenario == "p2p1"):
        df = df.loc[((df["source"] == "118") & (df["destination"] == "209"))]
    elif(scenario == "p2p2"):
        df = df.loc[((df["source"] == "206") & (df["destination"] == "210"))]
    elif(scenario == "p2p3"):
        df = df.loc[((df["source"] == "213") & (df["destination"] == "225"))]

    elif(scenario == "p2mp"):
        df = df.loc[((df["source"] == "119") & (df["destination"] == "[217*224]")) | ((df["source"] == "213") &
                                                                                      (df["destination"] == "[108*200]")) | ((df["source"] == "201") & (df["destination"] == "[209*211*224*225]"))]
    elif(scenario == "p2mp1"):
        df = df.loc[((df["source"] == "119") & (
            df["destination"] == "[217*224]"))]
    elif(scenario == "p2mp2"):
        df = df.loc[((df["source"] == "213") & (
            df["destination"] == "[108*200]"))]
    elif(scenario == "p2mp3"):
        df = df.loc[((df["source"] == "201") & (
            df["destination"] == "[209*211*224*225]"))]

    elif(scenario == "mp2p"):
        df = df.loc[((df["source"] == "[117+207+226]") & (df["destination"] == "222"))
                    | ((df["source"] == "[219+110]") & (df["destination"] == "220"))]
    elif(scenario == "mp2p1"):
        df = df.loc[((df["source"] == "[117+207+226]")
                     & (df["destination"] == "222"))]
    elif(scenario == "mp2p2"):
        df = df.loc[((df["source"] == "[219+110]") &
                     (df["destination"] == "220"))]

    df.value = df.value.apply(pd.to_numeric, errors='coerce')

    df_reliability = df.loc[df['key'] == "Reliability [%]"]
    df_energy = df.loc[df['key'] == "Total Energy [J]"]
    df_latency = df.loc[df['key'] == "Latency combined [us]"]

    df_mean_energy = df_energy.groupby("description").agg(
        np.mean).reset_index(drop=False)
    df_mean_reliability = df_reliability.groupby(
        "description").agg(np.mean).reset_index(drop=False)
    df_mean_latency = df_latency.groupby(
        "description").agg(np.mean).reset_index(drop=False)

    df_mean_latency["value"] = df_mean_latency["value"]/1000

    df_merged = pd.DataFrame()
    df_merged['description'] = df_mean_energy['description'].str.replace(
        "Team", re.escape("Team\\n"))
    df_merged[jamming_str+'-energy'] = df_mean_energy['value']
    df_merged[jamming_str+'-reliability'] = df_mean_reliability['value']
    df_merged[jamming_str+'-latency'] = df_mean_latency['value']
    # df_merged=df_merged.reindex([0,1,2,4,6,3,5,7,8])
    # df_merged=df_merged.reindex([2,1,4,0,6,8,7,3,5])
    df_merged = df_merged.reindex([0, 1, 2, 4, 6, 8, 7, 3, 5])
    return df_merged


@experimental.route('/admin/ewsn2018_dl/<scenario>')
@roles_required("admins")
def admin_ewsn_dl(scenario=None):
    jamming_list = ["any", "0", "1", "7", "8", "9", "10", "11"]
    df = None
    for j in jamming_list:
        if scenario == "all":
            df_n = admin_make_all_df(j)
        else:
            df_n = admin_make_eval_df(j, scenario)
        if(df is None):
            df = df_n
        else:
            df = pd.merge(df, df_n, on="description")

    resp = make_response(df.to_csv())
    resp.headers["Content-Disposition"] = "attachment; filename=export-"+scenario+".csv"
    resp.headers["Content-Type"] = "text/csv"
    return resp


@experimental.route('/admin/honorable')
@experimental.route('/admin/honorable/')
@roles_required("admins")
def admin_honorable():
    evaluations = Evaluation.query

    jamming_max = Config.get_int("jamming_max", 0)

    durations_string = Config.get_string("durations", "30 60 120 180 300")
    durations = map(int, durations_string.split())

    reference = request.args.get("reference")
    if (reference == None):
        reference = "None"
    if (reference == "null"):
        reference = "None"

    coeff_rel = request.args.get("coeff_rel")
    if (coeff_rel == None):
        coeff_rel = 10.0
    else:
        coeff_rel = float(coeff_rel)

    coeff_energy = request.args.get("coeff_energy")
    if (coeff_energy == None):
        coeff_energy = 1.0
    else:
        coeff_energy = float(coeff_energy)

    coeff_latency = request.args.get("coeff_latency")
    if (coeff_latency == None):
        coeff_latency = 1.0
    else:
        coeff_latency = float(coeff_latency)

    jamming = request.args.get("jamming")
    if(jamming == "super"):
        evaluations = evaluations.filter(Evaluation.scenario.has(
            Scenario.job.has((Job.duration == 1800) | (Job.duration == 4200))))
        evaluations = evaluations.filter(
            ~Evaluation.scenario.has(Scenario.job.has(Job.jamming == 0)))
        evaluations = evaluations.filter(
            ~Evaluation.scenario.has(Scenario.job.has(Job.jamming == 3)))
    elif(jamming == "any"):
        evaluations = evaluations.filter(Evaluation.scenario.has(
            Scenario.job.has((Job.duration == 1800) | (Job.duration == 4200))))
        evaluations = evaluations.filter(
            ~Evaluation.scenario.has(Scenario.job.has(Job.jamming == 3)))
    else:
        if (jamming == None):
            jamming = 7
        else:
            jamming = int(jamming)

        if((jamming == 7) or (jamming == 11)):
            duration = 4200
        else:
            duration = 1800
        evaluations = evaluations.filter(Evaluation.scenario.has(
            Scenario.job.has(Job.jamming == jamming)))
        evaluations = evaluations.filter(Evaluation.scenario.has(
            Scenario.job.has(Job.duration == duration)))

    evaluations = evaluations.filter((Evaluation.key == "Reliability [%]") | (
        Evaluation.key == ["Latency combined [us]"]) | (Evaluation.key == "Total Energy [J]"))
    evaluations = evaluations.filter(
        Evaluation.scenario.has(Scenario.job.has(Job.id >= 5588)))
    evaluations = evaluations.filter(
        Evaluation.scenario.has(Scenario.job.has(Job.id <= 5859)))
    evaluations = evaluations.filter(
        ~Evaluation.scenario.has(Scenario.job.has(Job.id == 5597)))
    evaluations = evaluations.filter(
        ~Evaluation.scenario.has(Scenario.job.has(Job.id == 5791)))
    evaluations = evaluations.filter(
        ~Evaluation.scenario.has(Scenario.job.has(Job.id == 5852)))
    evaluations = evaluations.filter(
        Evaluation.scenario.has(Scenario.job.has(Job.logs == False)))
    evaluations = evaluations.join(Scenario).add_columns(Scenario.source).add_columns(Scenario.destination).add_columns(
        Scenario.job_id).join(Job).add_column(Job.description).add_columns(Scenario.job_id)

    # df_jobs=pd.read_sql(jobs.statement,jobs.session.bind)
    # df_scenarios=pd.read_sql(scenarios.statement,scenarios.session.bind)
    df = pd.read_sql(evaluations.statement, evaluations.session.bind)
    df = df.dropna()

    line = df.loc[(df["job_id"] == 5829)].copy()
    if(len(line) > 0):
        line["job_id"] = 99999
        df = df.append(line)

    scenario = request.args.get("scenario")
#    if (scenario==None or (not (scenario=="p2p" or scenario=="mp2p" or scenario=="p2mp")) ):
#        scenario="p2p"

    if(scenario == "p2p"):
        df = df.loc[((df["source"] == "118") & (df["destination"] == "209")) | ((df["source"] == "206") & (
            df["destination"] == "210")) | ((df["source"] == "213") & (df["destination"] == "225"))]
    elif(scenario == "p2p1"):
        df = df.loc[((df["source"] == "118") & (df["destination"] == "209"))]
    elif(scenario == "p2p2"):
        df = df.loc[((df["source"] == "206") & (df["destination"] == "210"))]
    elif(scenario == "p2p3"):
        df = df.loc[((df["source"] == "213") & (df["destination"] == "225"))]

    elif(scenario == "p2mp"):
        df = df.loc[((df["source"] == "119") & (df["destination"] == "[217*224]")) | ((df["source"] == "213") &
                                                                                      (df["destination"] == "[108*200]")) | ((df["source"] == "201") & (df["destination"] == "[209*211*224*225]"))]
    elif(scenario == "p2mp1"):
        df = df.loc[((df["source"] == "119") & (
            df["destination"] == "[217*224]"))]
    elif(scenario == "p2mp2"):
        df = df.loc[((df["source"] == "213") & (
            df["destination"] == "[108*200]"))]
    elif(scenario == "p2mp3"):
        df = df.loc[((df["source"] == "201") & (
            df["destination"] == "[209*211*224*225]"))]

    elif(scenario == "mp2p"):
        df = df.loc[((df["source"] == "[117+207+226]") & (df["destination"] == "222"))
                    | ((df["source"] == "[219+110]") & (df["destination"] == "220"))]
    elif(scenario == "mp2p1"):
        df = df.loc[((df["source"] == "[117+207+226]")
                     & (df["destination"] == "222"))]
    elif(scenario == "mp2p2"):
        df = df.loc[((df["source"] == "[219+110]") &
                     (df["destination"] == "220"))]

    df.value = df.value.apply(pd.to_numeric, errors='coerce')

    df_reliability = df.loc[df['key'] == "Reliability [%]"]
    df_energy = df.loc[df['key'] == "Total Energy [J]"]
    df_latency = df.loc[df['key'] == "Latency combined [us]"]

    df_mean_energy = df_energy.groupby("description").agg(
        np.mean).reset_index(drop=False)
    df_mean_reliability = df_reliability.groupby(
        "description").agg(np.mean).reset_index(drop=False)
    df_mean_latency = df_latency.groupby(
        "description").agg(np.mean).reset_index(drop=False)

    df_count = df_energy.groupby("description").count().reset_index(drop=False)

    df_mean_latency["value"] = df_mean_latency["value"]/1000

    df_std_energy = df_energy.groupby("description").agg(
        np.std, ddof=0).reset_index(drop=False)
    df_std_reliability = df_reliability.groupby(
        "description").agg(np.std, ddof=0).reset_index(drop=False)
    df_std_latency = df_latency.groupby("description").agg(
        np.std, ddof=0).reset_index(drop=False)

    df_std_latency["value"] = df_std_latency["value"]/1000

    teams = df_mean_energy['description'].tolist()
    teams = ["None"]+teams

    if(reference == "None"):
        min_energy = df_mean_energy['value'].min()
        min_latency = df_mean_latency['value'].min()
        max_reliability = df_reliability['value'].max()
    else:
        min_energy = df_mean_energy['value'].loc[df_mean_energy['description']
                                                 == reference].iloc[0]
        min_latency = df_mean_latency['value'].loc[df_mean_latency['description']
                                                   == reference].iloc[0]
        max_reliability = df_mean_reliability['value'].loc[df_mean_reliability['description']
                                                           == reference].iloc[0]

    df_merged = pd.DataFrame()
    df_merged['description'] = df_mean_energy['description']
    df_merged['energy'] = df_mean_energy['value']
    df_merged['energy_std'] = df_std_energy['value']
    df_merged['reliability'] = df_mean_reliability['value']
    df_merged['reliability_std'] = df_std_reliability['value']
    df_merged['latency'] = df_mean_latency['value']
    df_merged['latency_std'] = df_std_latency['value']
    df_merged['rel_energy'] = (
        df_merged['energy']-min_energy)/min_energy*coeff_energy*100
    df_merged['rel_latency'] = (
        df_merged['latency']-min_latency)/min_latency*coeff_latency*100
    df_merged['rel_reliability'] = (
        max_reliability-df_merged['reliability'])/max_reliability*coeff_rel*100
    df_merged['count'] = df_count['value']

    df_merged['total'] = df_merged['rel_energy'] + \
        df_merged['rel_latency']+df_merged['rel_reliability']

    df_merged = df_merged.sort_values("total")

    return render_template('admin/honorable.html', df=df_merged, jamming_max=jamming_max, jamming=jamming, scenario=scenario, teams=teams, reference=reference,
                           coeff_energy=coeff_energy, coeff_rel=coeff_rel, coeff_latency=coeff_latency)


@experimental.route('/admin/finals/')
@roles_required("admins")
def admin_finals():
    metrics = Metric.query

    jamming_max = Config.get_int("jamming_max", 0)

    coeff_rel = request.args.get("coeff_rel")
    if (coeff_rel == None):
        coeff_rel = 10.0
    else:
        coeff_rel = float(coeff_rel)

    coeff_energy = request.args.get("coeff_energy")
    if (coeff_energy == None):
        coeff_energy = 1.0
    else:
        coeff_energy = float(coeff_energy)

    coeff_latency = request.args.get("coeff_latency")
    if (coeff_latency == None):
        coeff_latency = 1.0
    else:
        coeff_latency = float(coeff_latency)

    jamming = request.args.get("jamming")
    if(jamming == "super"):
        metrics = metrics.filter(Metric.job.has(
            (Job.duration == 1800) | (Job.duration == 4200)))
        metrics = metrics.filter(~Metric.job.has(Job.jamming == 0))
        metrics = metrics.filter(~Metric.job.has(Job.jamming == 3))
    elif(jamming == "any"):
        metrics = metrics.filter(Metric.job.has(
            (Job.duration == 1800) | (Job.duration == 4200)))
        metrics = metrics.filter(~Metric.job.has(Job.jamming == 3))
        # metrics=metrics.filter(~Metric.job.has(Job.jamming==0))
        # metrics=metrics.filter(~Metric.job.has(Job.jamming==3))
    else:
        if (jamming == None):
            jamming = 7
        else:
            jamming = int(jamming)

        if((jamming == 7) or (jamming == 11)):
            duration = 4200
        else:
            duration = 1800
        metrics = metrics.filter(Metric.job.has(Job.jamming == jamming))
        metrics = metrics.filter(Metric.job.has(Job.duration == duration))

    reference = request.args.get("reference")
    if (reference == None):
        reference = "None"
    if (reference == "null"):
        reference = "None"

    metrics = metrics.filter(Metric.job.has(Job.logs == False))
    metrics = metrics.filter(Metric.job.has(Job.id >= 5588))
    metrics = metrics.filter(Metric.job.has(Job.id <= 5859))
    metrics = metrics.filter(~Metric.job.has(Job.id == 5597))
    metrics = metrics.filter(~Metric.job.has(Job.id == 5791))
    metrics = metrics.filter(~Metric.job.has(Job.id == 5852))
    metrics = metrics.join(Job).join(Group).add_columns(
        Group.name).add_columns(Job.description)

    #print metrics.first()

    df = pd.read_sql(metrics.statement, metrics.session.bind)
    # df=df.dropna()
    if len(df) == 0:
        min_energy = 0
        max_reliability = 0
        min_latency = 0
        teams = ["None"]
        reference = "None"
        return render_template('admin/finals.html', df=df, jamming_max=jamming_max, jamming=jamming, min_energy=min_energy, min_latency=min_latency,
                               max_reliability=max_reliability, coeff_energy=coeff_energy, coeff_rel=coeff_rel, coeff_latency=coeff_latency, teams=teams, reference=reference)

    #print df
    try:
        df['latency'] = df['latency']/1000
    except KeyError:
        df['latency'] = None

    df = df.fillna(value=np.nan)

    try:
        df['reliability'] = df['reliability']*100
    except KeyError:
        df['reliability'] = 0

    # nothing to see here, move along
    line = df.loc[(df["job_id"] == 5829)].copy()
    if(len(line) > 0):
        line["job_id"] = 99999
        df = df.append(line)

    df['abs_energy'] = df['energy']
    df['abs_latency'] = df['latency']
    df['abs_reliability'] = df['reliability']

    df_tmp = df.groupby("description").agg(np.mean).reset_index(drop=False)

    teams = df_tmp['description'].tolist()
    teams = ["None"]+teams

    df_abs = pd.DataFrame()
    df_abs['description'] = df_tmp['description']
    df_abs['abs_energy_mean'] = df_tmp['energy']
    df_abs['abs_latency_mean'] = df_tmp['latency']
    df_abs['abs_reliability_mean'] = df_tmp['reliability']

    if(reference == "None"):
        min_energy = df_abs['abs_energy_mean'].min()
        min_latency = df_abs['abs_latency_mean'].min()
        max_reliability = df_abs['abs_reliability_mean'].max()
    else:
        min_energy = df_abs['abs_energy_mean'].loc[df_abs['description']
                                                   == reference].iloc[0]
        min_latency = df_abs['abs_latency_mean'].loc[df_abs['description']
                                                     == reference].iloc[0]
        max_reliability = df_abs['abs_reliability_mean'].loc[df_abs['description']
                                                             == reference].iloc[0]

    df['rel_energy'] = (df['energy']-min_energy)/min_energy*coeff_energy
    df['rel_latency'] = (df['latency']-min_latency)/min_latency*coeff_latency
    df['rel_reliability'] = (
        max_reliability-df['reliability'])/max_reliability*coeff_rel

    df['total'] = df['rel_energy']+df['rel_latency']+df['rel_reliability']

    df_tmp = df.groupby("description").agg(np.mean).reset_index(drop=False)
    df_x = df.groupby("description").count().reset_index(drop=False)
    df_mean = pd.DataFrame()
    df_mean['description'] = df_tmp['description']
    df_mean['energy_mean'] = df_tmp['rel_energy']
    df_mean['latency_mean'] = df_tmp['rel_latency']
    df_mean['reliability_mean'] = df_tmp['rel_reliability']
    df_mean['abs_energy_mean'] = df_tmp['abs_energy']
    df_mean['abs_latency_mean'] = df_tmp['abs_latency']
    df_mean['abs_reliability_mean'] = df_tmp['abs_reliability']
    df_mean['total_mean'] = df_tmp['total']
    df_mean['count'] = df_x['energy']

    df_tmp = df.groupby("description").agg(
        np.std, ddof=0).reset_index(drop=False)
    df_std = pd.DataFrame()
    df_std['description'] = df_tmp['description']
    df_std['energy_std'] = df_tmp['rel_energy']
    df_std['latency_std'] = df_tmp['rel_latency']
    df_std['reliability_std'] = df_tmp['rel_reliability']
    df_std['abs_energy_std'] = df_tmp['abs_energy']
    df_std['abs_latency_std'] = df_tmp['abs_latency']
    df_std['abs_reliability_std'] = df_tmp['abs_reliability']
    df_std['total_std'] = df_tmp['total']

    df = df.groupby("description").head(1).reset_index(drop=True)
    df = pd.merge(df, df_std, on='description')
    df = pd.merge(df, df_mean, on='description')

    df = df.sort_values("total_mean")

    return render_template('admin/finals.html', df=df, jamming_max=jamming_max, jamming=jamming, min_energy=min_energy, min_latency=min_latency,
                           max_reliability=max_reliability, coeff_energy=coeff_energy, coeff_rel=coeff_rel, coeff_latency=coeff_latency, teams=teams, reference=reference)
