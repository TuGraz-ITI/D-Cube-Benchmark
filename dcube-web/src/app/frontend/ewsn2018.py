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
from flask import Blueprint, render_template, flash, redirect, request, Response, url_for, current_app, abort, send_from_directory, make_response
from flask_bootstrap import __version__ as FLASK_BOOTSTRAP_VERSION
from flask_nav.elements import Navbar, View, Subgroup, RawTag, Link, Text, Separator
from flask_security import login_required, roles_required, current_user
from markupsafe import escape, Markup
from werkzeug.utils import secure_filename
from datetime import datetime

from nav import nav, ExtendedNavbar, Menustore

from models.user import User
from models.role import Role
from models.group import Group
from models.job import Job
from models.firmware import Firmware
from models.result import Result
from models.log import Log
from models.config import Config
from models.scenario import Scenario
from models.evaluation import Evaluation
from models.metric import Metric

from backend.security import user_datastore
from backend.database import db

import json
import calendar
import os
import requests
import subprocess
import base64
import string
import random

import pandas as pd
import numpy as np
import collections


ewsn2018 = Blueprint('ewsn2018', __name__)


def ewsn2018_register_navbar():
    ms = Menustore()
    items = (Subgroup('EWSN2018',
                      View('Total', 'ewsn2018.admin_finals'),
                      View('Per Scenario', 'ewsn2018.admin_honorable'),
                      ),)
    ms.left()["EWSN2018"] = items


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


@ewsn2018.route('/admin/ewsn2018_dl/<scenario>')
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


@ewsn2018.route('/admin/honorable')
@ewsn2018.route('/admin/honorable/')
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


@ewsn2018.route('/admin/finals/')
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
