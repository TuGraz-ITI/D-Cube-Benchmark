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
import pandas as pd

import time
import datetime
import json
import pika
import multiprocessing
import logging
import atexit

class Templab:

    def __init__(self, host, user_name, user_pass, nodelist, max_temperature=75,room_temperature=32):
        self.MAX_TEMPERATURE=max_temperature
        self.ROOM_TEMPERATURE=room_temperature
        self.logger=logging.getLogger("D-Cube Templab")
        self.logger.debug("D-Cube Templab:")
        self.logger.debug("\tMax Temperature is %s"%self.MAX_TEMPERATURE)
        self.logger.debug("\tRoot Temperature is %s"%self.ROOM_TEMPERATURE)

        self.df=None
        self.nodelist=nodelist
        self.csv_worker = None
        self.manager=multiprocessing.Manager()
        self.sensor_values=self.manager.dict()

        #connect to broker and setup queue/exchange
        self.credentials = pika.PlainCredentials(user_name, user_pass)
        self.host=host

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host,credentials=self.credentials,heartbeat=30))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='templab', exchange_type='fanout', durable=True)

        #for hostname in self.nodelist:
        #    fan_message=json.dumps({"hostname":hostname,"value":0})
        #    self.channel.basic_publish(exchange='templab', routing_key="fan", body=fan_message)

        #self.channel.confirm_delivery()

        self.sensor_worker=multiprocessing.Process(target=self.sensor_runner)
        self.sensor_worker.start()
        atexit.register(self.stop)

    def check_room_temperature(self):
        for host in self.sensor_values:
            s=self.sensor_values[host]
            if (datetime.datetime.now()-s["timestamp"]).total_seconds()>5:
                self.logger.error("Stale sensor! %s"%s)
            if s["temperature"]>self.ROOM_TEMPERATURE:
                self.logger.debug("Host: %s Hot sensor! %s"%(host,s))
                return {"hostname":host,"sensor":s}
        return None

    def sensor_runner(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host,credentials=self.credentials,heartbeat=30))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='templab', exchange_type='fanout', durable=True)
        result=self.channel.queue_declare(queue='',exclusive=True)
        self.queue_name = result.method.queue
        self.channel.queue_bind(exchange='templab', queue=self.queue_name)
        self.logger.debug("\tWorking on queue %r"%self.queue_name)

        try:
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.on_request)
        
            self.logger.debug("Awaiting Temperature Updates")
            self.channel.start_consuming()
            self.logger.debug("Stopped")
        except KeyboardInterrupt:        
            #self.logger.info("Aborted")
            #return
            pass

    def on_request(self, ch, method, props, body):
        if method.routing_key == "temp":
        #self.logger.debug("Sensor update: (%s)")
            n = json.loads(body)
            #self.logger.debug("JSON: (%s)" % n)
            update={"sensor_id":n["sensor"],"temperature":n["temperature"],"timestamp":datetime.datetime.now()}
            self.sensor_values[n["hostname"]]=update
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def finish(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host,credentials=self.credentials,heartbeat=30))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='templab', exchange_type='fanout', durable=True)

        self.logger.debug("Finishing experiment, all PID to 0")
        self.connection.sleep(1)
        for hostname in self.nodelist:
            message=json.dumps({"hostname":hostname,"setpoint":0})
            self.channel.basic_publish(exchange='templab', routing_key="setpoint", body=message)
            #fan_message=json.dumps({"hostname":hostname,"value":100})
            #self.channel.basic_publish(exchange='templab', routing_key="fan", body=fan_message)

    def prepare(self,csv_file):
        self.df=pd.read_csv(csv_file,index_col=0)

    def csv_runner(self):
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host,credentials=self.credentials,heartbeat=30))
            self.channel = self.connection.channel()
            self.channel.exchange_declare(exchange='templab', exchange_type='fanout', durable=True)
    
            t_accumulator = self.t_start
            self.logger.debug("Starting at %s"%self.t_start)
            for idx,row in self.df.iterrows():
                self.logger.debug("Next timestamp %s ns"%idx)
                delta=pd.Timedelta(idx, unit='ns')
                duration=(self.t_start+delta-datetime.datetime.now()).total_seconds()
                self.logger.debug("Going to sleep for %s"%duration)
                self.connection.sleep(max(duration,0))
                self.logger.debug("Step finished at %s"%datetime.datetime.now())
                for hostname in row.keys():
                    if hostname in self.nodelist:
                        temp = min(float(row[hostname]),self.MAX_TEMPERATURE)
                        self.logger.debug("Updating node %s: %f"%(hostname,temp))
                        message=json.dumps({"hostname":hostname,"setpoint":temp})
                        #self.channel.basic_publish(exchange='templab', routing_key="setpoint", body=message)
                        self.channel.basic_publish(exchange='templab', routing_key="setpoint", body=message)
                    else:
                        self.logger.error("Trying to control invalid node %s"%hostname)
        except KeyboardInterrupt:
            pass
        #self.finish()

    def start(self):
        self.t_start = datetime.datetime.now()
        if not self.csv_worker == None:
            self.logger.error("Experiment already started!")
        self.csv_worker = multiprocessing.Process(target=self.csv_runner)
        self.csv_worker.start()

    def stop(self):
        if not self.csv_worker == None:
            try:
                self.logger.debug("Terminating CSV worker")
                self.csv_worker.terminate()
                #self.csv_worker.join()
                self.logger.debug("CSV worker is finished")
            except AttributeError: 
                pass
            except AssertionError: 
                pass
        if not self.sensor_worker == None:
            try:
                self.logger.debug("Terminating Sensor worker")
                self.sensor_worker.terminate()
                #self.sensor_worker.join()
                self.logger.debug("Sensor worker is finished")
            except AttributeError: 
                pass
            except AssertionError: 
                pass
        self.finish()
