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
from subprocess import PIPE, Popen,call,check_call,CalledProcessError
from time import sleep
from datetime import datetime
from sqlalchemy.orm.exc import StaleDataError,ObjectDeletedError

from flask import current_app

from threading  import Thread
from queue import Queue, Empty

from backend.database import db
from models.job import Job
from models.group import Group
from models.result import Result
from models.log import Log
from models.config import Config

from models.benchmark_suite import BenchmarkSuite
from models.layout_composition import LayoutComposition
from models.node import Node

import holidays
import os
import pytz

import smtplib
import ssl


EMAIL_PORT = 465
EMAIL_TEXT = "Subject: [ITI-Testbed] Testbed failure\n\nDear testbed technician,\n\nthe testbed has failed and ended execution of experiments to prevent further damage.\n\nBest Regards,\nMarkus Schuss"
EMAIL_FROM = "D-Cube Testbed <dcube@iti.tugraz.at>"
EMAIL_TO = "D-Cube Testbed <dcube@iti.tugraz.at>"
#EMAIL_TO = "Markus Schuss <markus.schuss@tugraz.at>"
#EMAIL_TO = "markus.schuss@tugraz.at,cboano@tugraz.at"

def send_panic_mail():
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("mrelay.tugraz.at",EMAIL_PORT,context=context) as server:
        server.sendmail(EMAIL_FROM,EMAIL_TO,EMAIL_TEXT)

current_group=None
current_benchmark_suite=None

def next_job(with_jam=False,with_bs=False):
    global current_group
    global current_benchmark_suite
    
    prio=Job.query.filter_by(finished=False).filter_by(priority=True).order_by(Job.scheduled.asc()).first()
    if not prio==None:
        print("HIGH PRIORITY!")
        return prio
    groups=Group.query
    ng=groups.first()

    if with_bs:
        benchmark_suites=BenchmarkSuite.query
        nc=benchmark_suites.first()
        armed=False
        has_next=False

        for benchmark_suite in benchmark_suites:
            if(current_benchmark_suite==None):
                current_benchmark_suite=nc.id
                break
            else:
                if(current_benchmark_suite==benchmark_suite.id):
                    armed=True
                elif(armed==True):
                    nc=benchmark_suite
                    has_next=True
                    armed=False
                    break
    
        #no benchmark_suites exist, nothing to do
        if current_benchmark_suite==None:
            return None
    
        current_benchmark_suite=nc.id
        
        if not (armed==True):
            candidate_q=Job.query.filter_by(finished=False).filter_by(group_id=current_group)
            if(with_jam==False):
                candidate_q=candidate_q.filter_by(jamming_composition_id=1)
            candidate=candidate_q.join(LayoutComposition).join(BenchmarkSuite).filter(BenchmarkSuite.id==nc.id).order_by(Job.scheduled.asc()).first()
            if not (candidate==None):
                return candidate
    
    armed=False
    for group in groups:
        if(current_group==None):
            current_group=ng.id
            break
        else:
            if(current_group==group.id):
                armed=True
            elif(armed==True):
                ng=group
                break
    current_group=ng.id

    job_q=Job.query.filter_by(finished=False).filter_by(group_id=current_group)
    
    if(with_jam==False):
        job_q=job_q.filter_by(jamming_composition_id=1)

    #job_q=job_q.order_by(Job.scheduled.asc(),BenchmarkSuite.id.asc(),Job.scheduled.asc())
    job_q=job_q.join(LayoutComposition).join(BenchmarkSuite).order_by(BenchmarkSuite.id.asc(),Job.scheduled.asc())
    #job_q=job_q.filter(BenchmarkSuite.node.has(Node.name!="Sky-All"))

    job=job_q.first()
    if job==None:
        current_benchmark_suite=None
    else:
        current_benchmark_suite=job.protocol.benchmark_suite.id
    return job

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

def check_kill():
    global last_check
    db.session.commit()
    panic=Config.query.filter_by(key="scheduler_stop").first()
    if not panic==None:
        if panic.value=="on":
            return True
    return False

def check_time():
    if (check_holiday()==True):
        return True

    if (check_weekend()==True):
        return True

    db.session.commit()
    start=Config.query.filter_by(key="scheduler_time_start").first()
    stop=Config.query.filter_by(key="scheduler_time_stop").first()
    if not start==None and not stop==None:
        tz=pytz.timezone("Europe/Vienna") #TODO: Take string from config!
        now=datetime.now(tz)
        seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        
        start_tokens = start.value.split(":")
        stop_tokens = stop.value.split(":")
        seconds_start = (int(start_tokens[2]))+(int(start_tokens[1])*60)+(int(start_tokens[0])*3600)
        seconds_stop = (int(stop_tokens[2]))+(int(stop_tokens[1])*60)+(int(stop_tokens[0])*3600)
        if(seconds_stop>seconds_start):
            if(seconds_since_midnight>seconds_start and seconds_since_midnight<seconds_stop):
                return True
            else:
                return False

        if(seconds_stop<seconds_start):
            if(seconds_since_midnight<seconds_start and seconds_since_midnight>seconds_stop):
                return False
            else:
                return True
        
        if(seconds_stop==seconds_start):
            return False
    
    return True #assuming we can run if no timelimit is set

def check_jamming():
    if (check_holiday()==True):
        return True

    if (check_weekend()==True):
        return True

    db.session.commit()
    start=Config.query.filter_by(key="jamming_time_start").first()
    stop=Config.query.filter_by(key="jamming_time_stop").first()
    if not start==None and not stop==None:
        tz=pytz.timezone("Europe/Vienna") #TODO: Take string from config!
        now=datetime.now(tz)
        seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        
        start_tokens = start.value.split(":")
        stop_tokens = stop.value.split(":")
        seconds_start = (int(start_tokens[2]))+(int(start_tokens[1])*60)+(int(start_tokens[0])*3600)
        seconds_stop = (int(stop_tokens[2]))+(int(stop_tokens[1])*60)+(int(stop_tokens[0])*3600)
        if(seconds_stop>seconds_start):
            if(seconds_since_midnight>seconds_start and seconds_since_midnight<seconds_stop):
                return True
            else:
                return False

        if(seconds_stop<seconds_start):
            if(seconds_since_midnight<seconds_start and seconds_since_midnight>seconds_stop):
                return False
            else:
                return True
        
        if(seconds_stop==seconds_start):
            return False
    
    return True #assuming we can run if no timelimit is set



def check_holiday():
    h=holidays.Austria(prov='ST')
    h.append(["2020-12-24","2020-12-31"])
    if (datetime.today() in h):
        return True
    else:
        return False

def check_weekend():
    wd=datetime.today().weekday()
    if (wd==5 or wd==6):
        return True
    else:
        return False

def check_fulltime(job):
    if job==None:
        return False
    group=job.group
    if group==None:
        return False
    for user in group.users:
        if user.has_role("fulltime"):
            return True
    return False

class Scheduler:

    current_task=None

    def run(self):

        while(True):
            try:
                db.session.commit()
                next=next_job(check_jamming())
                fulltime=check_fulltime(next)
                if next==None or check_kill()==True:
                    sleep(1)
                    continue
                if not (next.priority or fulltime or check_time()):
                    sleep(1)
                    continue
                else:
                    if(next.firmware == None):
                        print("no firmware found yet")
                        continue
                    print("running %s for group %s" % (next.firmware.filename,next.group.name))
                    next.running=True
                    oldres=next.result
                    if not oldres == None:
                        db.session.delete(oldres)
                    log=Log(next.id)
                    db.session.add(log)
                    db.session.commit()
                    name=next.firmware.filename
                    start_time=datetime.utcnow()
    
                    if ((next.protocol.benchmark_suite.node.name=="Sky-All") or (next.protocol.benchmark_suite.node.name=="Nordic-All")) :
                        py_path = current_app.config['PYTHON_PATH']
                        dcm_path = current_app.config['DCM_PATH']
                        dcm_bin = current_app.config['DCM_BINARY']
                        dcm_broker = current_app.config['DCM_BROKER']
                        if next.temp_profile:
                            switch_config = current_app.config['TEMPLAB_SWITCH_CONFIG']
                        else:
                            switch_config = current_app.config['SWITCH_CONFIG']
                        #current_task=Popen(['/usr/bin/python3',"/testbed/pydcube/rpc_testbed.py", "--job_id", str(next.id),"--topology", "switch.json"], stderr=PIPE, stdin=PIPE, stdout=PIPE,cwd="/testbed/pydcube")
                        print([py_path,dcm_bin, "--job_id", str(next.id),"--topology", switch_config, "--broker", dcm_broker])
                        current_task=Popen([py_path,dcm_bin, "--job_id", str(next.id),"--topology", switch_config, "--broker", dcm_broker], stderr=PIPE, stdin=PIPE, stdout=PIPE,cwd=dcm_path)
    
                    elif (next.node.name=="Anchor-North"):
                        current_task=Popen(['./program_anchors.sh', name, str(next.id)], stderr=PIPE, stdin=PIPE, stdout=PIPE,cwd="/testbed/script")
                    else:
                        next.failed=True
                        next.finished=True
                        next.running=False
                        panic=Config.query.filter_by(key="scheduler_stop").first()
                        if not panic==None:
                            if not panic.value=="on":
                                panic.value="on"
                        else:
                            panic=Config("scheduler_stop","on")
                            db.session.add(panic)
                        db.session.commit()
                        continue
    
    
                    #current_task=Popen(['notepad', name], stdin=PIPE, stderr=PIPE, stdin=PIPE, stdout=PIPE)
                    q = Queue()
                    q2 = Queue()
                    t = Thread(target=enqueue_output, args=(current_task.stdout, q))
                    t2 = Thread(target=enqueue_output, args=(current_task.stderr, q2))
                    t.daemon = True # thread dies with the program
                    t2.daemon = True # thread dies with the program
                    t.start()
                    t2.start()  
                    last_run=False
       
                    while(True):
                        sleep(0.1)
                        if check_kill()==True:
                            print("aborting")
                            current_task.terminate()
                            break
                        try:
                            while(True):
                                nextline = q.get(True,1)
                                log.text+=nextline.decode()
                                db.session.commit()
                        except Empty:
                            pass
                        try:
                            while(True):
                                nexterr = q2.get(True,1)
                                log.text+=nexterr.decode()
                                db.session.commit()
                        except Empty:
                            pass
    
                        if last_run:
                            break
                        if current_task.poll() is not None:
                            last_run=True
    
                    #t.exit()
                    try:
                        current_task.communicate()
                        current_task.stdin.close()
                        current_task.stderr.close()
                        current_task.stdout.close()
                    except ValueError:
                        pass
                    except IOError:
                        pass
                    return_code = current_task.wait()
                    if(return_code):
                        next.failed=True
                        if not return_code==253: #-3 is file format error and ok
                            panic=Config.query.filter_by(key="scheduler_stop").first()
                            if not panic==None:
                                if not panic.value=="on":
                                    panic.value="on"
                                    try:
                                        send_panic_mail()
                                    except Exception:
                                        pass
                            else:
                                panic=Config("scheduler_stop","on")
                                db.session.add(panic)
                            db.session.commit()
    
                    else:
                        next.failed=False
                    next.finished=True
                    next.running=False
                    end_time=datetime.utcnow()
                    try:
                            result=Result(start_time,end_time,next.id)
                            db.session.add(result)
                            db.session.commit()
                            print("Job finished with return_code " + str(return_code))
                    except (ObjectDeletedError,StaleDataError):
                            print("Job no longer exists")
                            db.session.rollback()
                    current_task=None
            except (ObjectDeletedError,StaleDataError):
                print("Job no longer exists")

