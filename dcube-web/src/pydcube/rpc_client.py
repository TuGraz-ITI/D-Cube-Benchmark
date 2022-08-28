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
from DCM.poe import PoEClient

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
from zipfile import ZipFile,ZIP_DEFLATED

def signalhandler(signum, frame):
    logger.error("Signal %s caught, terminating experiment!"%signum)
    stop=tz.localize(datetime.datetime.now())
    try:
        if(start):
            runtime=stop-start
            logger.info("Experiment terminated on %s after %s seconds."%(stop.strftime(DATEFORMAT),int(runtime.total_seconds())))
    except NameError:
        logger.info("Experiment terminated on %s."%stop.strftime(DATEFORMAT))
        pass
    dcube.terminate()
    exit(-2)

#Program loop parameters
PING_MAX=20
PING_DELAY=10
PROGRAM_RETRY_MAX=5

#List of all servers
SERVERS=["rpi%d"%x for x in chain(range(100,120),range(200,228))]

#Local time format
DATEFORMAT="%a %b %d %H:%M:%S %Z %Y"
tz=pytz.timezone("CET")

#CLI arguments
parser=argparse.ArgumentParser(description="D-Cube RPC Client.")
parser.add_argument("--job_id",type=int,required=True,dest="job_id",help="Job ID to be run")
parser.add_argument("--topology",type=str,dest="topology_json",help="JSON formatted switch topology")
parser.add_argument("--debug",action="store_true",help="Enable debug")

args=parser.parse_args()

#Pretty print functions
def print_job(job):
    logger.info("Experiment ID: %d"%job["id"])
    logger.info("Competing team number: %s"%job["group"])
    logger.info("Experiment duration: %d"%job["duration"])
    logger.info("Serial log: %s"%("enabled" if job["logs"] else "disabled"))
    logger.info("Jamming: %s"%job["jamming_short"])

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

logging.basicConfig(level=level,format=FORMAT)
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

#clients
poe=PoEClient(topology)
dcube=DCM.Client("localhost","master","guest","guest",servers=SERVERS)
rest=DCM.RESTClient("http://192.168.100.16")

#print startup banner
startup=datetime.datetime.now()
startup=tz.localize(startup)
banner="Programming script started! (%s)"%startup.strftime(DATEFORMAT)
logger.info(banner)
logger.info("="*len(banner))
job=rest.get_job(JOB)
print_job(job)
logger.info("="*len(banner))

signal.signal(signal.SIGINT,signalhandler)
signal.signal(signal.SIGTERM,signalhandler)

#ping all servers
logger.info("Checking if all %d Raspberry Pi nodes are pingable..."%len(SERVERS))
try:
    dcube.ping()
    logger.info("[OK] All nodes could be pinged correctly!")
except DCM.ServersUnresponseException as e:
    logger.error("[ERROR] Following nodes are not pingable:")
    for s in e.servers:
        logger.error("\t%s"%s)
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

#redo PROGRAM_RETRY_MAX times or until no more failed or missing nodes are found
while((not len(COPY)==0) and count < PROGRAM_RETRY_MAX):

    #start a new experiment, if programming failes nodes will already have one (ignore)
    try:
        dcube.experiment(state=DCM.CommandState.ON,job_id=JOB,servers=COPY)
    except DCM.CommandFailedException as e:
        pass

    #power off all nodes before selecting 
    dcube.mote_power(state=DCM.CommandState.OFF,servers=COPY)
    dcube.sleep(1)
    
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

    
    #power on the with newly selected nodes 
    dcube.mote_power(state=DCM.CommandState.ON,servers=COPY)
    dcube.sleep(3)

    #list all nodes which will be programmed
    #motes=dcube.motelist()
    #print_motes(motes)

    #release nodes from reset before programming
    dcube.mote_reset(state=DCM.CommandState.OFF,servers=COPY)
    dcube.sleep(1)

    #program nodes with the firmware for the current experiment/job
    logger.debug("Programming all nodes...")
    r=dcube.program(servers=COPY)
    count=count+1

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
            except DCM.ServersUnresponseException:
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

#with all nodes programmed, setup experiment stimuli and measurement

logger.info("Turning off and back on all target nodes...")

#power off all nodes
dcube.mote_power(state=DCM.CommandState.OFF)
dcube.sleep(1)

#keep nodes in reset
dcube.mote_reset(state=DCM.CommandState.ON)
dcube.sleep(1)

#power on the node under reset (SB44 and SB45 need to be closed!)
dcube.mote_power(state=DCM.CommandState.ON)
dcube.sleep(3)

#start jamming
dcube.jamming()

#start blinkers
dcube.blinker()

#if logs are enabled, start traces
if(job["logs"]==True):
    dcube.trace(state=DCM.CommandState.ON)
    dcube.sleep(3)

#if the nordic node not using logs, switch to native port
elif job["node"]=="Nordic-All":
    dcube.mote_power(state=DCM.CommandState.OFF)
    dcube.sleep(1)
    dcube.mote_select(mote="nrf52840dk-native")
    dcube.sleep(1)
    dcube.mote_power(state=DCM.CommandState.ON)
    dcube.sleep(1)

logger.info("Startging measurements...")

#start measurments
dcube.measurement(state=DCM.CommandState.ON)
dcube.sleep(3)

#print experiment start time and release motes from reset
start=tz.localize(datetime.datetime.now())
dcube.mote_reset(state=DCM.CommandState.OFF)
logger.info("Experiment startet on %s. Duration: %s seconds..."%(start.strftime(DATEFORMAT),job["duration"]))

#wait for job duration
dcube.sleep(job["duration"])

#reset all nodes again and print experiment stop time
dcube.mote_reset(state=DCM.CommandState.ON)
stop=tz.localize(datetime.datetime.now())
logger.info("Experiment terminated on %s."%stop.strftime(DATEFORMAT))
dcube.sleep(5)
dcube.measurement(state=DCM.CommandState.OFF)

#stopping the traces will automatically also collect the logs
if(job["logs"]==True):
    r=dcube.trace(state=DCM.CommandState.OFF)

    #write base64 encoded replies into a single log zip
    logs={}
    if os.path.exists("logs.zip"):
        os.remove("logs.zip")
    with ZipFile("logs.zip", 'w',ZIP_DEFLATED) as zf:
        for k in r.keys():
            response=r[k]
            log=base64.b64decode(response["logs"]).decode()
            logs[k]=log
            zf.writestr("log_%s.txt"%k[3:6],log)

#stopping the experiment will also stop all spawend processes (including jamming and blinker)
dcube.experiment(state=DCM.CommandState.OFF)

