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
import pika
import uuid
import json
import logging
from .command import CommandType,CommandState,CommandReturn,CommandExe

class CommandFailedException(Exception):
    def __init__(self,servers):
        self.servers=servers
        message = "%d servers have failed: %s" %(len(servers),servers)
        super().__init__(message)

class CommandArgumentException(Exception):
    def __init__(self):
        message = "Invalid argument for command!"
        super().__init__(message)

class ServersUnresponseException(Exception):
    def __init__(self,servers):
        self.servers=servers
        message = "%d servers unresponsive: %s" %(len(servers),servers)
        super().__init__(message)

class InvalidResponseException(Exception):
    def __init__(self,server,response):
        self.server=server
        message = "response (%s) from server %s not understood"%(response,server)
        super().__init__(message)

class Client:

################################################################################
# Constructor
################################################################################

    def __init__(self, host, hostname, user_name, user_pass, servers=[]):
        self.logger=logging.getLogger("D-Cube Client")

        self.hostname=hostname
        self.servers=servers

        #basic connection on localhost
        credentials=pika.PlainCredentials(user_name, user_pass)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=host,credentials=credentials))
        self.channel = self.connection.channel()
        
        #declare fanout exchange
        self.channel.exchange_declare(exchange='dcube', exchange_type='fanout')

################################################################################
# Close Connection
################################################################################

    def close(self):
        self.connection.close()

################################################################################
# Connection Callback
################################################################################

    def on_response(self,ch, method, props, body):
        if self.corr_id == props.correlation_id:
            response = json.loads(body.decode())
            self.responses[response['name']]=response
            self.logger.debug("Response received: %r" % response)
            if response["name"] in self.destinations:
                self.logger.debug("%r has responded!"%response["name"])
                self.destinations.remove(response["name"])
                if len(self.destinations)==0:
                    self.channel.stop_consuming()

################################################################################
# Timeout Callback
################################################################################

    def on_timeout(self):
        self.logger.debug("A timeout has occured, stopping to listen!")
        self.channel.stop_consuming()

################################################################################
# Sleep wrapper
################################################################################

    def sleep(self,time):
        self.connection.sleep(time)
    
################################################################################
# Send raw command
################################################################################

    def send(self,command,servers,timeout=45,listen=True):
        self.responses={}
        self.destinations=list(servers)

        #callback queue
        result = self.channel.queue_declare(queue='', exclusive=True)
        callback_queue = result.method.queue
        self.channel.basic_consume(queue=callback_queue, on_message_callback=self.on_response, auto_ack=True)
   
        #create corrleation id and publish a message with timestamp requiest
        self.corr_id = str(uuid.uuid4())
        self.logger.debug("Command %s send"%command)
        self.channel.basic_publish(
            exchange='dcube',
            routing_key='',
            properties=pika.BasicProperties(
                reply_to=callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(command))
        
        if(listen):
            to=self.connection.call_later(timeout,self.on_timeout)
            self.channel.start_consuming()
            self.connection.remove_timeout(to)
            return self.responses
        else:
            return None

################################################################################
# Check Functions 
################################################################################

    def get_unresponsive(self,responses=None,servers=None):
        servers = self.servers if servers==None else servers
        responses = self.responses if responses==None else responses
        unresponsive=[]

        for server in servers:
            if not server in responses.keys():
                unresponsive.append(server)
        return unresponsive

    def check_programmed(self,responses=None,servers=None):
        servers = self.servers if servers==None else servers
        responses = self.responses if responses==None else responses
        failed=[]
        ok=[]
        missing=[]
        unresponsive=self.get_unresponsive(responses,servers)
        recovery=True
        message=None

        for k in responses.keys():
            if (responses[k]["return"]==CommandReturn.SUCCESS):
                self.logger.debug("Server %s OK"%k)
                ok.append(k)
            elif (responses[k]["return"]==CommandReturn.MISSING):
                self.logger.debug("Server %s MISSING"%k)
                missing.append(k)
            elif (responses[k]["return"]==CommandReturn.FAILED):
                self.logger.debug("Server %s FAILED"%k)
                failed.append(k)
            elif (responses[k]["return"]==CommandReturn.FORMAT):
                self.logger.debug("Server %s FORMAT"%k)
                failed.append(k)
                recovery=False
                if(message==None):
                    message=responses[k]["message"]
            else:
                raise InvalidResponseException(k,responses[k])
        return {"ok":ok,"failed":failed,"missing":missing,"unresponsive":unresponsive,"recovery":recovery,"message":message}
    
    def check_responses(self,responses=None,servers=None):
        servers = self.servers if servers==None else servers
        responses = self.responses if responses==None else responses
        failed=[]
        ok=[]
        missing=[]
        unresponsive=self.get_unresponsive(responses,servers)

        for k in responses.keys():
            if responses[k]["return"]==CommandReturn.MISSING:
                missing.append(k)
            elif responses[k]["return"]==CommandReturn.SUCCESS:
                ok.append(k)
            elif responses[k]["return"]==CommandReturn.FAILED:
                failed.append(k)
            else: #no idea what it is, but it most likely is not good
                failed.append(k)
                
        return {"ok":ok,"missing":missing,"failed":failed,"unresponsive":unresponsive}


################################################################################
# Command wrappers
################################################################################

    def __raise(self,r):
        if len(r["unresponsive"]) > 0:
            raise ServersUnresponseException(r["unresponsive"])

        if len(r["failed"]) > 0:
            raise CommandFailedException(r["failed"])

        if len(r["missing"]) > 0:
            raise CommandFailedException(r["missing"])

    #ping servers
    def ping(self,servers=None,listen=True,timeout=5):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.PING
        
        self.send(command,servers,listen=listen,timeout=timeout)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #create experiment
    def experiment(self,state=None,job_id=None,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        if not ( (state==CommandState.ON) or (state==CommandState.OFF) or (state==None)):
            raise CommandArgumentException()

        command={}
        command["servers"]=servers
        command["type"]=CommandType.EXPERIMENT
        if not state==None:
            command["state"]=state
        if state==CommandState.ON:
            if job_id==None:
                raise CommandArgumentException()
            command["id"]=job_id

        self.send(command,servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #control power to a mote
    def mote_power(self,state,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        if not ( (state==CommandState.ON) or (state==CommandState.OFF) ):
            raise CommandArgumentException()

        command={}
        command["servers"]=servers
        command["type"]=CommandType.POWER
        command["state"]=state
        
        self.send(command,servers=servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #get selected node
    def motelist(self,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.MOTELIST
        
        self.send(command,servers=servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)
            motes={}
            for k in self.responses.keys():
                motes[k]=json.loads(self.responses[k]["message"])
            return motes
        return None

    #select target node via mux
    def mote_select(self,mote,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.MOTE
        command["mote"]=mote

        self.send(command,servers=servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #control reset of a mote
    def mote_reset(self,state,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.RESET
        command["state"]=state
        
        self.send(command,servers=servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #reboot target node
    def reboot(self,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.REBOOT

        self.send(command,servers=servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    def program(self,hexfile=None,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.PROGRAM

        self.send(command,servers,timeout=180,listen=listen)
        if listen:
            r=self.check_programmed(servers=servers)
            return r
        return None

    #write eeprom
    def write_eeprom(self,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.PROCESS
        command["class"]=CommandExe.CUSTOM
        command["cmd"]="/home/pi/tests/i2c-bash/write.sh"

        self.send(command,servers=servers,listen=listen,timeout=30)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #read eeprom
    def read_eeprom(self,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.PROCESS
        command["class"]=CommandExe.CUSTOM
        command["cmd"]="/home/pi/tests/i2c-bash/read.sh 27"

        self.send(command,servers=servers,listen=listen,timeout=60)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #start jamming process
    def jamming(self,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.PROCESS
        command["class"]=CommandExe.JAMMING
        
        self.send(command,servers=servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #start blinker process
    def blinker(self,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        command={}
        command["servers"]=servers
        command["type"]=CommandType.PROCESS
        command["class"]=CommandExe.BLINKER

        self.send(command,servers=servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    #control serialdump
    def trace(self,state,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        if not ( (state==CommandState.ON) or (state==CommandState.OFF) ):
            raise CommandArgumentException()

        command={}
        command["servers"]=servers
        command["type"]=CommandType.TRACE
        command["state"]=state
        
        self.send(command,servers=servers,timeout=600,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)
            return self.responses
        return None

    #control measurement
    def measurement(self,state,servers=None,listen=True):
        servers = self.servers if servers==None else servers
        if not ( (state==CommandState.ON) or (state==CommandState.OFF) ):
            raise CommandArgumentException()

        command={}
        command["servers"]=servers
        command["type"]=CommandType.MEASUREMENT
        command["state"]=state
        
        self.send(command,servers=servers,listen=listen)
        if listen:
            r=self.check_responses(servers=servers)
            self.__raise(r)

    def terminate(self,servers=None):
        servers = self.servers if servers==None else servers
        self.experiment(state=CommandState.OFF,listen=False)
        self.measurement(state=CommandState.OFF,listen=False)
        self.trace(state=CommandState.OFF,listen=False)
        self.mote_reset(state=CommandState.ON,listen=False)

