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
from .command import CommandType,CommandState,CommandReturn,CommandExe
from .patch import BinaryPatcher
from .nodes.node import NodeFactory
from .experiment import Experiment
from .rest import RESTClient
import subprocess
import shlex
import pika
import time
import json
import logging
import base64
import os

class Server:

################################################################################
# Generic commands
################################################################################
    
    def cmd_ping(self,request,response):
        response["message"]="pong"
        return CommandReturn.SUCCESS

    def cmd_timestamp(self,request,response):
        ts=self.timestamp()
        response["message"]="%.9f" %ts
        response["timestamp"]=ts
        return CommandReturn.SUCCESS

    def timestamp(self):
        return time.time()

################################################################################
# Command stubs usually overwritten by the server implementation
################################################################################

    def cmd_motelist(self,request,response):
        ml=self.motelist()
        motes=json.dumps([m.toJSON() for m in ml])
        response["message"]=motes
        return CommandReturn.SUCCESS

    def motelist(self):
        motes=[]
        return motes

    def cmd_power(self,request,response):
        return CommandReturn.FAILED

    def cmd_reset(self,request,response):
        return CommandReturn.FAILED
        
    def cmd_measurement(self,request,response):
        return CommandReturn.FAILED

    def cmd_select_node(self,request,response):
        return CommandReturn.FAILED

################################################################################
# Commands calling node functions
################################################################################

    def get_current_mote(self,request):
        motes=self.motelist()
        target=None

        #TODO decide if multi mote support is even usefull
        if "mote" in request:
            for mote in motes:
                if request["mote"]==mote["name"]:
                    target=mote
        else:
            if len(motes)>0:
                target=motes[0]
        return target

    def cmd_trace(self,request,response):
        target=self.get_current_mote(request)
        ret=None
        if not target==None:
            self.logger.debug("Target: %s"%target)

            if "state" in  request:
                if request["state"]==CommandState.ON:
                    self.logger.debug("Starting trace collection...")
                    ret=target.start_traces()
                if request["state"]==CommandState.OFF:
                    self.logger.debug("Stopping trace collection...")
                    response["logs"]=target.collect_traces()
                    ret=target.stop_traces()
            else:
                self.logger.error("No state given for trace collection!")
                ret=CommandReturn.FAILED
        else:
            ret=CommandReturn.MISSING
        self.logger.debug("Done: %s"%ret)
        return ret

    def cmd_program(self,request,response):
        self.logger.debug("Programming node...")
        tempfile=os.path.join(self.tempdir,"temp.hex")
        if "hexfile" in request:
            hexfile=base64.b64decode(request["hexfile"])
            with open(tempfile,"wb") as f:
                f.write(hexfile)
        elif not self.experiment==None:
            job_id=self.experiment.get_job_id()
            job=self.rest.get_job(job_id)
            if job==None:
                response["message"]="Job does not exist"
                return CommandReturn.FAILED

            hexfile=self.rest.get_firmware(job_id)
            with open(tempfile,"wb") as f:
                f.write(hexfile)

            if ("patch" in job and job["patch"]) or ("cpatch" in job and job["cpatch"]):
                if job["node"]=="Sky-All":
                    arch="msp430"
                elif job["node"]=="Nordic-All":
                    arch="arm32l"
                else: 
                    response["message"]="Architecture not supported yet!"
                    self.logger.error(response["message"])
                    return CommandReturn.FAILED
                bp=BinaryPatcher(tempfile,arch,tempdir=self.tempdir)

            if "patch" in job and job["patch"]:
                testbed_xml=os.path.join(self.tempdir,"testbed.xml")
                self.logger.debug("patching firmware for testbed")
                p=self.rest.get_patch(job_id,self.hostname)
                with open(testbed_xml,"wb") as f:
                    f.write(p["xml"]) #TODO pass as string
                try:
                    bp.patch(testbed_xml,p["json"])
                except Exception:
                    response["message"] = "Binary patching failed"
                    self.logger.error(response["message"])
                    return CommandReturn.FORMAT

            if "cpatch" in job and job["cpatch"]:
                custom_xml=os.path.join(self.tempdir,"custom.xml")
                self.logger.debug("patching firmware with custom patch")

                try:
                    cp=self.rest.get_custom_patch(job_id,self.hostname)
                except Exception:
                    response["message"] = "Custom binary patching failed"
                    self.logger.error(response["message"])
                    return CommandReturn.FORMAT

                with open(custom_xml,"wb") as f:
                    f.write(cp["xml"]) #TODO pass as strimg

                try:
                    bp.patch(custom_xml,cp["json"],zero=False)
                except Exception:
                    response["message"] = "Custom binary patching failed"
                    self.logger.error(response["message"])
                    return CommandReturn.FORMAT

        else:
            response["message"] = "Unable to determine hexfile"
            self.logger.error(response["message"])
            return CommandReturn.FAILED

        target=self.get_current_mote(request)

        ret=None
        if not target==None:
            self.logger.debug("Target: %s"%target)
            ret=target.program(tempfile,self.connection)
            if ret==CommandReturn.FORMAT:
                response["message"] = "Invalid hex file"
        else:
            ret=CommandReturn.MISSING
        self.logger.debug("Done: %s"%ret)
        return ret

################################################################################
# Command to create a experiment context used by other commands
################################################################################

    def cmd_experiment(self,request,response):
        if "state" in request:
            if request["state"] == CommandState.ON:
                if not "id" in request:
                    response["message"]="Job ID is required to start an experiment"
                    self.logger.error(response["message"])
                    return CommandReturn.FAILED

                elif not self.experiment==None:
                    response["message"]="Experiment already in progress"
                    self.logger.error(response["message"])
                    return CommandReturn.FAILED

                else:
                    self.experiment=Experiment(request["id"],self.connection)
                    return CommandReturn.SUCCESS

            elif request["state"] == CommandState.OFF:
                if self.experiment==None:
                    response["message"]="No experiment in progress"
                    self.logger.error(response["message"])
                    return CommandReturn.FAILED
                else:
                    job_id=self.experiment.get_job_id()
                    self.logger.debug("stopping experiment %s"%job_id)
                    response["message"]=job_id
                    self.experiment.stop(request,response)
                    self.experiment=None
                    return CommandReturn.SUCCESS

            else:
                response["message"]="Invalid control command"
                self.logger.error(response["message"])
                return CommandReturn.FAILED

        if not self.experiment==None:
            response["message"]=self.experiment.get_job_id()
        else:
            response["message"]="No experiment in progress"
        return CommandReturn.SUCCESS

################################################################################
# Command to create a experiment context used by other commands
################################################################################

    def cmd_process(self,request,response):
        if "class" in request:
            if request["class"]==CommandExe.CUSTOM:
                if "cmd" in request:
                    cwd=None
                    if "cwd" in request:
                        cwd=request["cwd"]

                    cmd=shlex.split(request["cmd"])
                
                    try:
                        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=cwd,close_fds=True)
                    except FileNotFoundError as e:
                        response["message"]="File does not exist!"
                        self.logger.error(response["message"])
                        return CommandReturn.FAILED

                    self.connection.sleep(1)
                    p.poll()
                    if not p.returncode==None:
                        outs, errs = p.communicate()
                        self.logger.debug("STDOUT:")
                        self.logger.debug(outs)
                        self.logger.debug("STDERR:")
                        self.logger.debug(errs)
                        response["message"]="Process terminated with return code %d"%p.returncode
                        if p.returncode==0:
                            return CommandReturn.SUCCESS

                        return CommandReturn.FAILED
                    self.experiment.processes[p.pid]=p
                    self.logger.debug("Created new process with pid %d"%p.pid)
                    return CommandReturn.SUCCESS
                else:
                    response["message"]="A class must be specified"
                    self.logger.error(response["message"])
                    return CommandReturn.FAILED
                
            elif request["class"]==CommandExe.JAMMING:
                if self.experiment==None:
                    response["message"]="No experiment in progress"
                    self.logger.error(response["message"])
                    return CommandReturn.FAILED
                d=self.rest.get_jamming(self.experiment.get_job_id(),self.hostname)
                if not (("options" in d) and ("csv" in d)):
                   self.logger.error("REST api did not return a valid jamming conifg")
                   return CommandReturn.FAILED

                tempfile=os.path.join(self.tempdir,"jamming.csv")
                with open(tempfile,"w") as f:
                    f.write(d["csv"].decode())

                c=d["options"].decode()
                args=shlex.split(c)
                cmd=[self.JAMMING_CMD]
                cmd.extend(args)
                cmd.append(tempfile)
                
                self.logger.debug(cmd)
                try:
                    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=self.JAMMING_PWD,close_fds=True)
                except FileNotFoundError as e:
                   response["message"]="File does not exist!"
                   self.logger.error(response["message"])
                   return CommandReturn.FAILED

                self.experiment.processes[p.pid]=p
                return CommandReturn.SUCCESS

            elif request["class"]==CommandExe.BLINKER:
                if self.experiment==None:
                    response["message"]="No experiment in progress"
                    self.logger.error(response["message"])
                    return CommandReturn.FAILED
                d=self.rest.get_blinker(self.experiment.get_job_id(),self.hostname)
                if not "cmd" in d:
                   self.logger.error("REST api did not return a cmd")
                   return CommandReturn.FAILED

                c=d["cmd"].decode()
                cmd=shlex.split(c)
                
                self.logger.debug(cmd)
                try:
                    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
                except FileNotFoundError as e:
                   response["message"]="File does not exist!"
                   self.logger.error(response["message"])
                   return CommandReturn.FAILED

                self.experiment.processes[p.pid]=p
                return CommandReturn.SUCCESS
        else:
            response["message"]="A class must be specified"
            self.logger.error(response["message"])
            return CommandReturn.FAILED

        return CommandReturn.FAILED

################################################################################
# Command to indicate the server to reboot
################################################################################

    def cmd_reboot(self,request,response):
        self.do_reboot=True
        return CommandReturn.SUCCESS

    #called if do_reboot is true
    def reboot(self,request):
        self.do_reboot=False

################################################################################
# Command dispatcher
################################################################################

    #message dispatcher
    def dispatch(self,request):
        response = {}
        response["name"]=self.hostname

        if request["type"]==CommandType.PING:
            response["return"]=self.cmd_ping(request,response)
        elif request["type"]==CommandType.TIMESTAMP:
            response["return"]=self.cmd_timestamp(request,response)
        elif request["type"]==CommandType.MOTELIST:
            response["return"]=self.cmd_motelist(request,response)
        elif request["type"]==CommandType.POWER:
            response["return"]=self.cmd_power(request,response)
        elif request["type"]==CommandType.RESET:
            response["message"]=self.cmd_reset(request,response)
            response["return"]=CommandReturn.SUCCESS
        elif request["type"]==CommandType.PROGRAM:
            response["return"]=self.cmd_program(request,response)
        elif request["type"]==CommandType.MOTE:
            response["return"]=self.cmd_select_node(request,response)
        elif request["type"]==CommandType.MEASUREMENT:
            response["return"]=self.cmd_measurement(request,response)
        elif request["type"]==CommandType.TRACE:
            response["return"]=self.cmd_trace(request,response)
        elif request["type"]==CommandType.REBOOT:
            response["return"]=self.cmd_reboot(request,response)
        elif request["type"]==CommandType.EXPERIMENT:
            response["return"]=self.cmd_experiment(request,response)
        elif request["type"]==CommandType.PROCESS:
            response["return"]=self.cmd_process(request,response)
        else:
            response["message"]="unknown type"
            response["return"]=CommandReturn.FAILED

        return json.dumps(response)

################################################################################
# Command dispatcher
################################################################################
    
    #message recieved callback
    def on_request(self, ch, method, props, body):
        self.logger.debug("Request: (%s)" % body)
        n = json.loads(body)
    
        self.logger.debug("JSON: (%s)" % n)
        if self.hostname in n["servers"]:
            response=self.dispatch(n)
            self.logger.debug("Response: (%s)" % response)
    
            ch.basic_publish(exchange='',
                             routing_key=props.reply_to,
                             properties=pika.BasicProperties(correlation_id = \
                                                                 props.correlation_id),
                             body=str(response))
            ch.basic_ack(delivery_tag=method.delivery_tag)
            if self.do_reboot==True:
                self.logger.info("Going to reboot")
                self.reboot()
        else:
            self.logger.debug("Hostname not in servers list, ignoring")
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
################################################################################
# Blocking call to process commands
################################################################################

    def run(self):
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.on_request)
        
        self.logger.info("Awaiting RPC requests")
        self.channel.start_consuming()
        self.logger.info("Stopped")

################################################################################
# Constructor
################################################################################

    def __init__(self, host, hostname, user_name, user_pass,nodes=[],tempdir="/tmp",resturl="http://dcube-web"):
        self.JAMMING_PWD="/home/pi/testbed/"
        self.JAMMING_CMD="./jammer"

        self.logger=logging.getLogger("D-Cube Server")
        self.logger.info("D-Cube Server:")
        self.tempdir=tempdir
        self.hostname=hostname
        self.logger.debug("\tTempdir is %s"%self.tempdir)
        self.logger.info("\tHostname %r"%self.hostname)
        self.rest=RESTClient(resturl)

        self.do_reboot=False
        self.experiment=None

        #connect to broker and setup queue/exchange
        credentials = pika.PlainCredentials(user_name, user_pass)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host,credentials=credentials,heartbeat=30))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='dcube', exchange_type='fanout')
        result=self.channel.queue_declare(queue='',exclusive=True)
        self.queue_name = result.method.queue
        self.channel.queue_bind(exchange='dcube', queue=self.queue_name)
        self.logger.info("\tWorking on queue %r"%self.queue_name)

        self.nodes=[]

        #register all attached nodes from json
        nodefactory=NodeFactory()
        for node in nodes:
            self.nodes.append(nodefactory.create_node(node["name"],node["mayor"],node["minor"],tempdir=tempdir))
