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
from time import sleep

from flask import current_app

from datetime import datetime
from sqlalchemy.orm.exc import StaleDataError,ObjectDeletedError
from backend.database import db
from backend.stats import StatsFactory 

from models.job import Job
from models.evaluation import Evaluation
from models.scenario import Scenario
from models.metric import Metric
from models.log import Log

from models.layout_pi import LayoutPi
from models.layout_composition import LayoutComposition

from io import StringIO

import calendar
import csv
import subprocess
import pickle

import traceback

import numpy as np
import json

from datetime import timedelta

K_SUP=2.0
K_CAUS=2.0


def next_job():
    return Job.query.filter_by(evaluated=False).filter_by(finished=True).filter_by(failed=False).order_by(Job.scheduled.desc()).first()
    #return Job.query.filter_by(evaluated=False).filter_by(finished=True).filter_by(failed=False).order_by(Job.scheduled.asc()).first()

class Evaluator:

    def run(self):

        USER = current_app.config["INFLUX_USER"]
        PASSWORD = current_app.config["INFLUX_PASSWORD"]
        DBNAME = current_app.config["INFLUX_DBNAME"]
        HOST= current_app.config["INFLUX_HOST"]
        PORT= current_app.config["INFLUX_PORT"]
        sf=StatsFactory()

        while(True):
            db.session.commit()
            job=next_job()
            if job==None:
                sleep(1)
                continue
            else:
                print("Next job: %s" % (job.id))
                if(job.protocol == None):
                    print("job has no protocol")
                    job.evaluated=True
                    db.session.commit()
                    continue
                if(job.result == None):
                    print("job has no results")
                    job.failed=True
                    continue
                    db.session.commit()
                print("Gathering statistics of %s for team %s" % (job.name, job.group.name))

                if(job.protocol.benchmark_suite.id==1 or job.protocol.benchmark_suite.id==2 or job.protocol.benchmark_suite_id==6):
                    s=sf.create("EWSN2019",HOST, PORT, USER, PASSWORD, DBNAME)
                elif(job.protocol.benchmark_suite.id==3 or job.protocol.benchmark_suite_id==4 or job.protocol.benchmark_suite_id==5):
                    s=sf.create("EWSN2020",HOST, PORT, USER, PASSWORD, DBNAME)

                    cfgs=job.protocol.benchmark_suite.configs
                    for cfg in cfgs:
                        if cfg.key=="delta":
                            s.delta=timedelta(milliseconds=int(cfg.value))

                    try:
                        co=json.loads(job.config_overrides)
                        if "delta" in co:
                            s.delta=timedelta(milliseconds=int(co["delta"]))
                    except Exception as e:
                        print(e)
                        pass

                    #s.delta=timedelta(microseconds=60000)
                else:
                    print("Unsupported benchmark suite")
                    job.evaluated=True
                    db.session.commit()
                    continue

                #TODO: malli hack
                if(job.group.id==20 or job.group.id==1):
                    s.split_mp2p=True
                
                try:
                    evs=s.do_evaluate(job.id)
                except Exception as e:
                    print("evaluation failed %s"%e)
                    job.evaluated=True
                    db.session.commit()
                    continue

                energies=[]
                setup_energies=[]
                latencies=[]
                reliabilities=[]

                for ev in evs:
                    pair=ev["pair"]
                    evaluation=ev["evaluation"]

                    if(len(pair["source"]) == 0 or len(pair["destination"]) == 0  or evaluation.count_source == 0):
                        print("No sources/destinations/events")
                        job.evaluated=True
                        db.session.commit()
                        continue

                    if len(pair["source"])>1:
                        source=(str(pair['source']).replace(", ","+").replace("'",""))
                    else:
                        source=str(pair["source"][0])

                    if len(pair["destination"])>1:
                        destination=(str(pair['destination']).replace(", ","*").replace("'",""))
                    else:
                        destination=pair["destination"][0]

                    pin=ev["pair"]["pin"]
                    scenario=Scenario(source,destination,pin,job.id)
                    db.session.add(scenario)
                    db.session.flush()

                    energies.append(ev["energy_total"])
                    setup_energies.append(ev["energy_setup"])

                    if(not (s.split_mp2p and evaluation.count_source==None)):
                        esrc=evaluation.count_source
                        esnk=evaluation.count_destination
                        ecor=evaluation.source_destination
                        elate=evaluation.source_destination_late
                        emis=evaluation.source_source
                        esup=evaluation.destination_destination
                        ecaus=evaluation.destination_source
                        ebad=evaluation.no_idea
                        elast=evaluation.last_event
    
                        try:
                            event_metric=(float(ecor)/float(esrc))*(1-(K_SUP*(float(esup)/float(esrc))))*(1-(K_CAUS*(float(ecaus)/float(esrc))))
                        except ZeroDivisionError:
                            event_metric=None

                        if not (event_metric>=0 and event_metric<=1):
                            event_metric=0

                        reliabilities.append(float(event_metric))

                        er=Evaluation("Reliability [%]",str(round(event_metric*100,2)),True,scenario.id)
                        db.session.add(er)
    
                        eee=Evaluation("Messages sent to source node",esrc,True,scenario.id)
                        db.session.add(eee)
    
                        eee=Evaluation("Messages received on sink node",esnk,True,scenario.id)
                        db.session.add(eee)
    
                        eee=Evaluation("Correct messages",ecor,True,scenario.id)
                        db.session.add(eee)
    
                        if(job.protocol.benchmark_suite.id==3):
                            eee=Evaluation("Late (but correct) messages",elate,False,scenario.id)
                            db.session.add(eee)
    
                        eee=Evaluation("Missed messages",emis+elate,True,scenario.id)
                        db.session.add(eee)
    
                        eee=Evaluation("Superflous messages",esup,True,scenario.id)
                        db.session.add(eee)
    
                        eee=Evaluation("Messages with causality error",ecaus,True,scenario.id)
                        db.session.add(eee)
    
                        eee=Evaluation("Bad messages",ebad,False,scenario.id)
                        db.session.add(eee)
    
                        eee=Evaluation("Missed at the end",elast,False,scenario.id)
                        db.session.add(eee)
    
                    if len(evaluation.deltas)>1:
                        latency_sum = float(sum(evaluation.deltas))
                        latency_max = float(max(evaluation.deltas))
                        latency_min = float(min(evaluation.deltas))
                        latency_mean = float(np.mean(evaluation.deltas))
                        latency_median = float(np.median(evaluation.deltas))
                        latency_90 = float(np.percentile(evaluation.deltas,90))
                        latency_95 = float(np.percentile(evaluation.deltas,95))
                        latency_99 = float(np.percentile(evaluation.deltas,99))
                        if(not (s.split_mp2p and evaluation.count_source==None)):
                            latencies.append(float((latency_mean+latency_median)/2.0))
                    else:
                        latency_sum = None 
                        latency_max = None  
                        latency_min = None 
                        latency_mean = None 
                        latency_median = None 
                        latency_90 = None 
                        latency_95 = None 
                        latency_99 = None 
                        if(not (s.split_mp2p and evaluation.count_source==None)):
                            latencies.append(None)


                    if(latency_mean==None or latency_median==None):
                        el=Evaluation("Latency combined [us]","None",True,scenario.id)
                    else:
                        el=Evaluation("Latency combined [us]",str(round(((latency_mean+latency_median)/2),2)),True,scenario.id)
                    db.session.add(el)

                    evaluation=Evaluation("Latency sum [us]",latency_sum,False,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Latency max [us]",latency_max,False,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Latency min [us]",latency_min,False,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Latency mean [us]",latency_mean,True,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Latency median [us]",latency_median,True,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Latency 90 Percentile [us]",latency_90,True,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Latency 95 Percentile [us]",latency_95,True,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Latency 99 Percentile [us]",latency_99,True,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Total Energy [J]",ev["energy_total"],True,scenario.id)
                    db.session.add(evaluation)

                    evaluation=Evaluation("Energy during setup time [J]",ev["energy_setup"],True,scenario.id)
                    db.session.add(evaluation)

                #except TypeError as e:
                #    #job.failed=True
                #    job.evaluated=True
                #    db.session.commit()
                #    traceback.print_exc()
                #    print(e)
                #    print("Job is broken")
                #    continue

                try:
                    rel=0
                    for r in reliabilities:
                        rel+=r
                    reliability=rel/len(reliabilities)
                    #reliability=(float(evt_sink)/float(evt_source))
                except (ZeroDivisionError, TypeError):
                    reliability=None

                try:
                    lat=0
                    for l in latencies:
                        lat+=l
                    latency=lat/len(latencies)
                    #latency=latency/count
                except (ZeroDivisionError, TypeError):
                    latency=None

                try:
                    eng=0
                    su=0
                    for e in energies:
                        eng+=e
                    for s in setup_energies:
                        su+=s

                    energy=eng/len(energies)
                    setup_energy=su/len(setup_energies)
                    #energy=energy/count
                    menergy=energy-setup_energy
                except (ZeroDivisionError, TypeError):
                    energy=None
                    setup_energy=None
                    menergy=None

                metric=Metric(menergy,reliability,latency,job.id)
                db.session.add(metric)
                job.evaluated=True
                db.session.commit()
                print("Job evaluated")
