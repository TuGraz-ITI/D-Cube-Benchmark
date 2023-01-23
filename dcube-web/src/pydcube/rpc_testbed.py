#!/usr/bin/env python
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
import DCM
from DCM.poe import PoEClient,PoEPolicy
from DCM.templab import Templab

#timezone format
import pytz
import datetime

#sleep
import time

#signal handler
import signal

#cli arguments
import argparse

#file operations
import os

#helper
from itertools import chain
import json
import logging

#used for logfile
import base64
import sys
from zipfile import ZipFile,ZIP_DEFLATED

#used for templab
from io import StringIO

MASTER_PID=os.getpid()

def signalhandler(signum, frame):
    if(os.getpid()==MASTER_PID):
        logger.error("Signal %s caught, terminating experiment!"%signum)
        stop=datetime.datetime.now()
        stop=stop.replace(tzinfo=pytz.utc)
        stop=stop.astimezone(tz)
        try:
            if(start):
                runtime=stop-start
                logger.info("Experiment terminated on %s after %s seconds."%(stop.strftime(DATEFORMAT),int(runtime.total_seconds())))
        except NameError:
            logger.info("Experiment terminated on %s."%stop.strftime(DATEFORMAT))
            pass
        dcube.terminate()
        exit(-2)
    
    try:
        if(templab):
            templab.stop()
            exit(0)
    except NameError:
        pass
    
    exit(0)

#Program loop parameters
PING_MAX=40
PING_DELAY=10
PROGRAM_RETRY_MAX=10

#POE loop parameters
POE_RETRY_MAX=5

#List of all servers
#SERVERS=["rpi%d"%x for x in chain(range(100,120),range(200,228))]

#SERVERS=["rpi%d"%x for x in chain(range(100,102))]

#Local time format
DATEFORMAT="%a %b %d %H:%M:%S %Z %Y"
tz=pytz.timezone("CET")

#Where to put the logfiles for the webserver
LOGFILEPATH="/storage/logfiles"

#CLI arguments
parser=argparse.ArgumentParser(description="D-Cube RPC Client.")
parser.add_argument("--job_id",type=int,required=True,dest="job_id",help="Job ID to be run")
parser.add_argument("--topology",type=str,required=True,dest="topology_json",help="JSON formatted switch topology")
parser.add_argument("--debug",action="store_true",help="Enable debug")
parser.add_argument("--broker",type=str,required=True,dest="broker",help="Broker IP")

args=parser.parse_args()

#Pretty print functions
def print_job(job):
    logger.info("Experiment ID: %d"%job["id"])
    logger.info("Competing team number: %s"%job["group"])
    logger.info("Experiment duration: %d"%job["duration"])
    logger.info("Serial log: %s"%("enabled" if job["logs"] else "disabled"))
    logger.info("Jamming: %s"%job["jamming_short"])
    if(job["templab"]==True):
        logger.info("Templab extension: %s"%("enabled" if job["templab"] else "disabled"))

def print_motes(motes):
    for k in motes.keys():
        mote=motes[k]
        logger.info("%s:\t%s"%(k,mote))

JOB=args.job_id

level=logging.INFO
if args.debug:
    level=logging.DEBUG
    FORMAT = "[%(name)16s - %(funcName)12s() ] %(message)s"
else:
    FORMAT = "%(message)s"

logger=logging.getLogger(__name__)

logging.basicConfig(stream=sys.stdout,level=level,format=FORMAT)
logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

################################################################################
# TODO implment PoE reboot logic
################################################################################
if args.topology_json:
    with open(args.topology_json,"r") as f:
        topology=json.load(f)
else:
    topology={}

SERVERS=[]
for switch in topology:
    for node in switch["nodes"]:
        SERVERS.append(node["hostname"])

#templab_nodes=["rpi%d"%x for x in range(120,128)]+ ["rpi129"]
templab_nodes=["rpi%d"%x for x in range(120,128)]#+ ["rpi129"]

BROKER=args.broker

#clients
poe=PoEClient(topology)
#TODO use credentials file!
dcube=DCM.Client(BROKER,"master","dcube","GWcq43x2",servers=SERVERS)
rest=DCM.RESTClient("http://dcube-web")

#print startup banner
startup=datetime.datetime.now()
startup=startup.replace(tzinfo=pytz.utc)
startup=startup.astimezone(tz)
banner="Programming script started! (%s)"%startup.strftime(DATEFORMAT)
logger.info(banner)
logger.info("="*len(banner))
job=rest.get_job(JOB)
print_job(job)
logger.info("="*len(banner))

signal.signal(signal.SIGINT,signalhandler)
signal.signal(signal.SIGTERM,signalhandler)

if job["templab"]:
    #TODO use credentials file!
    templab=Templab(BROKER,"dcube","GWcq43x2",templab_nodes)
    temp_profile=rest.get_temp_profile(job["id"])
    templab.prepare(StringIO(temp_profile["csv"].decode()))

def power_cycle(servers):
    global poe
    global dcube
    for s in servers:
        poe.set_node(s,PoEPolicy.OFF)
    dcube.sleep(10)
    for s in servers:
        poe.set_node(s,PoEPolicy.ON)
    dcube.sleep(10)


#ping all servers
logger.info("Checking if all %d Raspberry Pi nodes are pingable..."%len(SERVERS))
count=0
while count < POE_RETRY_MAX:
    try:
        dcube.ping()
        logger.info("[OK] All nodes could be pinged correctly!")
        break
    except DCM.ServersUnresponseException as e:
        logger.error("[ERROR] Following nodes are not pingable:")
        for s in e.servers:
            logger.error("\t%s"%s)
        logger.info("Errors have occured, recovery required (this may take a while)...")
        #TODO check if there is a pi on the port!
        power_cycle(e.servers)
        #for s in e.servers:
        #    poe.set_node(s,PoEPolicy.OFF)
        #dcube.sleep(10)
        #for s in e.servers:
        #    poe.set_node(s,PoEPolicy.ON)
        #dcube.sleep(10)

        ping_counter=0

        #loop until all nodes are pingable, up to PING_MAX times with PING_DELAY interval
        loopy=True
        while(loopy):
            if ping_counter>=PING_MAX:
                logger.error("Reboot of servers %s failed"%dcube.get_unresponsive())
                exit(-1)

            ping_counter += 1
            dcube.sleep(PING_DELAY)
            try:
                dcube.ping()
                loopy=False
                break
            except DCM.ServersUnresponseException as e:
                if ping_counter==round(PING_MAX/2):
                    power_cycle(e.servers)
                loopy=True
        if loopy==False:
            break
        else:
            count+=1

if count==POE_RETRY_MAX:
    logger.error("Fatal error, recovery has failed!")
    exit(-1)

#Stop any orphaned experiments still in progress, ignore lack of experiments
try:
    dcube.experiment(state=DCM.CommandState.OFF)
except DCM.CommandFailedException as e:
    pass

logger.info("Programming all nodes...")

#program target loop with recovery
count=0
COPY=list(SERVERS) #start with all servers, will be failed+missing on next loop
log_stage=False

dcube.experiment(state=DCM.CommandState.ON,job_id=JOB,servers=COPY)

#redo PROGRAM_RETRY_MAX times or until no more failed or missing nodes are found
while((not len(COPY)==0) and count < PROGRAM_RETRY_MAX):
    logger.debug("\t%s"%COPY)

    #start a new experiment, if programming failes nodes will already have one (ignore)
    try:
        dcube.experiment(state=DCM.CommandState.ON,job_id=JOB,servers=COPY)
    except DCM.CommandFailedException as e:
        pass

    #power off all nodes before selecting 
    dcube.mote_power(state=DCM.CommandState.OFF,servers=COPY)
    dcube.sleep(5)
    
    logger.debug("Selecting and power cycling target nodes...")

    #TODO put correct names in webinterface
    #select target node via mux
    if job["node"]=="Sky-All":
        mote="sky"
    elif job["node"]=="Nordic-All":
        mote="nrf52840dk-jlink"
    else:
        logger.error("Node type %s not supported!"%job["node"])
        exit(-1)
    
    dcube.mote_select(mote,servers=COPY)
    dcube.sleep(1)

    dcube.write_eeprom(servers=COPY)
    dcube.sleep(3)
    dcube.read_eeprom(servers=COPY)
    dcube.sleep(10)
    
    #power on the with newly selected nodes 
    dcube.mote_power(state=DCM.CommandState.ON,servers=COPY)
    dcube.sleep(3)

    #list all nodes which will be programmed
    #motes=dcube.motelist()
    #print_motes(motes)

    #release nodes from reset before programming
    dcube.mote_reset(state=DCM.CommandState.OFF,servers=COPY)
    dcube.sleep(5)

    #program nodes with the firmware for the current experiment/job
    logger.debug("Programming all nodes...")
    r=dcube.program(servers=COPY)
    count=count+1

    if not r["recovery"]:
        logger.info(r["message"])
        exit(-3)

    #recovery loop, if nodes are missing perform reboot
    if not len(r["missing"])==0:
        logger.info("Errors have occured, recovery required (this may take a while)...")
        logger.debug("\tAffected servers: %s"%r["missing"])

        #reboot all missing nodes
        dcube.reboot(r["missing"])
        ping_counter=0

        #loop until all nodes are pingable, up to PING_MAX times with PING_DELAY interval
        loopy=True
        while(loopy):
            if ping_counter>=PING_MAX:
                logger.error("Reboot of servers %s failed"%dcube.get_unresponsive())
                exit(-1)
   
            ping_counter += 1
            dcube.sleep(PING_DELAY)
            try:
                dcube.ping(r["missing"])
                loopy=False
                break
            except DCM.ServersUnresponseException as e:
                if ping_counter==round(PING_MAX/2):
                    power_cycle(e.servers)

                loopy=True
    
        #TODO check chrony status
        #sleep until clock should be in sync again after reboot
        dcube.sleep(60)

    if ( (not len(r["missing"])==0) or (not len(r["failed"])==0) ):
        logger.debug("Some nodes have failed programming, retrying...")
    
    #in the next iteration, only the failed and newly rebooted missing nodes will be used
    COPY=[]
    COPY.extend(r["missing"])
    COPY.extend(r["failed"])

    if len(COPY)>0:
        continue

    if not log_stage:
        COPY=list(SERVERS) #restartstart with all servers again
    else:
        COPY=list(problems)


    #with all nodes programmed, setup experiment stimuli and measurement
    logger.info("Turning off and back on all target nodes...")
    
    #power off all nodes
    dcube.mote_power(state=DCM.CommandState.OFF,servers=COPY)
    dcube.sleep(5)
    
    #keep nodes in reset
    dcube.mote_reset(state=DCM.CommandState.ON,servers=COPY)
    dcube.sleep(1)
    
    #power on the node under reset (SB44 and SB45 need to be closed!)
    dcube.mote_power(state=DCM.CommandState.ON,servers=COPY)
    dcube.sleep(10)
    
    #start jamming
    dcube.jamming(servers=COPY)

    if job["node"]=="Nordic-All":
        brs=rest.get_border_routers(JOB)

        if(len(brs)):
            LIST_BRS=list()
            for br in brs:
                LIST_BRS.append("rpi%s"%br)

            dcube.mote_power(state=DCM.CommandState.OFF,servers=LIST_BRS)
            dcube.sleep(1)
            dcube.mote_select(mote="nrf52840dk-native",servers=LIST_BRS)
            dcube.sleep(1)
            dcube.mote_power(state=DCM.CommandState.ON,servers=LIST_BRS)
            dcube.sleep(10)
            dcube.mote_reset(state=DCM.CommandState.OFF,servers=LIST_BRS)
            dcube.sleep(10)

    
    #start blinkers
    dcube.blinker(servers=COPY)
    
    #if logs are enabled, start traces
    if(job["logs"]==True):
        
        LOG_COPY=list(COPY)
        brs=rest.get_border_routers(JOB)
        if(len(brs)):
            for br in brs:
                if br in LOG_COPY:
                    LOG_COPY.remove(br)
                    logger.info("Excluding border router %s from logs ..."%br)
                elif "rpi%s"%br in LOG_COPY:
                    LOG_COPY.remove("rpi%s"%br)
                    logger.info("Excluding border router %s from logs ..."%br)


        try:
            dcube.trace(state=DCM.CommandState.ON,servers=LOG_COPY)
        except DCM.CommandFailedException as e:
            r=dcube.check_responses(servers=LOG_COPY)

            #recovery loop, if nodes are missing perform reboot
            if (("missing" in r) and (not len(r["missing"])==0)) or \
               (("failed" in r) and (not len(r["failed"])==0)):
                problems=[]
                problems.extend(r["missing"])
                problems.extend(r["failed"])

                logger.info("Errors have occured, recovery required (this may take a while)...")
                logger.debug("\tAffected servers: %s"%problems)
        
                #reboot all missing nodes
                dcube.reboot(problems)
                ping_counter=0
        
                #loop until all nodes are pingable, up to PING_MAX times with PING_DELAY interval
                loopy=True
                while(loopy):
                    if ping_counter>=PING_MAX:
                        logger.error("Reboot of servers %s failed"%problems)
                        exit(-1)
    
                    ping_counter += 1
                    dcube.sleep(PING_DELAY)
                    try:
                        dcube.ping(problems)
                        loopy=False
                        break
                    except DCM.ServersUnresponseException as e:
                        if ping_counter==round(PING_MAX/2):
                            power_cycle(e.servers)

                        loopy=True
            
                #TODO check chrony status
                #sleep until clock should be in sync again after reboot
                dcube.sleep(60)

                COPY=[]
                COPY.extend(problems)
                log_stage=True
                continue

        dcube.sleep(3)
    
    #if the nordic node not using logs, switch to native port
    elif job["node"]=="Nordic-All":
        dcube.mote_power(state=DCM.CommandState.OFF,servers=COPY)
        dcube.sleep(1)
        dcube.mote_select(mote="nrf52840dk-native")
        dcube.sleep(1)
        dcube.mote_power(state=DCM.CommandState.ON,servers=COPY)
        dcube.sleep(1)

    COPY=[]
    
logger.info("Starting measurements...")

#start measurments
dcube.measurement(state=DCM.CommandState.ON)
dcube.sleep(3)

#exit if recovery was not possible
if not len(COPY)==0:
    logger.error("Fatal error, recovery has failed!")

    if not len(r["missing"])==0:
        logger.error("Server with missing nodes")
        for s in r["missing"]:
            logger.error("\t%s"%s)

    if not len(r["failed"])==0:
        logger.error("Server which failed programming")
    for s in r["failed"]:
        logger.error("\t%s"%s)
    exit(-1)


#print experiment start time and release motes from reset


if job["templab"]:
    templab.start()

start=datetime.datetime.now()
start=start.replace(tzinfo=pytz.utc)
start=start.astimezone(tz)

dcube.mote_reset(state=DCM.CommandState.OFF)
logger.info("Experiment started on %s. Duration: %s seconds..."%(start.strftime(DATEFORMAT),job["duration"]))

#wait for job duration
dcube.sleep(job["duration"])

#reset all nodes again and print experiment stop time
dcube.mote_reset(state=DCM.CommandState.ON)

stop=datetime.datetime.now()
stop=stop.replace(tzinfo=pytz.utc)
stop=stop.astimezone(tz)

logger.info("Experiment terminated on %s."%stop.strftime(DATEFORMAT))
dcube.sleep(5)
dcube.measurement(state=DCM.CommandState.OFF)

if job["templab"]:
    templab.stop()


#stopping the traces will automatically also collect the logs
if(job["logs"]==True):

    LOG_COPY=list(SERVERS)
    brs=rest.get_border_routers(JOB)
    if(len(brs)):
        for br in brs:
            if br in LOG_COPY:
                LOG_COPY.remove(br)
            elif "rpi%s"%br in LOG_COPY:
                LOG_COPY.remove("rpi%s"%br)

    logger.info("Collecting Logfiles ...")
    r=dcube.trace(state=DCM.CommandState.OFF,servers=LOG_COPY)

    if not os.path.exists(LOGFILEPATH):
        os.mkdir(LOGFILEPATH)

    #write base64 encoded replies into a single log zip
    basepath=os.path.join(LOGFILEPATH,str(JOB))
    path=os.path.join(basepath,"logs.zip")

    if not os.path.exists(basepath):
        os.mkdir(basepath)

    if os.path.exists(path):
        os.remove(path)
    with ZipFile(path, 'w',ZIP_DEFLATED) as zf:
        for k in r.keys():
            response=r[k]
            log=base64.b64decode(response["logs"])
            zf.writestr("log_%s.txt"%k[3:6],log)

#stopping the experiment will also stop all spawend processes (including jamming and blinker)
dcube.experiment(state=DCM.CommandState.OFF)
logger.info("Programming script terminated!")

dcube.close()
