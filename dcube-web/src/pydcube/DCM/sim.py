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
from .server import Server
from .command import CommandState,CommandReturn

from .nodes.node import NodeFactory
from .nodes.dummy import DummyNode

import subprocess

class Simulation(Server):

################################################################################
# Select node using the mux
################################################################################

    def cmd_select_node(self,request,response):
        ret=CommandReturn.FAILED
        if "mote" in request:
            for node in self.nodes:
                if node.name==request["mote"]:
                    return self.set_mux(node.name)
            else:
                response["message"]="Invalid mux state requested!"
                self.logger.error(response["message"])
            
        else:
            response["message"]="Mote must be specified!"
            self.logger.error(response["message"])
        return ret

    def set_mux(self,node_name):
        self.node_name=node_name
        ret=CommandReturn.SUCCESS
        return ret

    
################################################################################
# Command to control node power
################################################################################

    def cmd_power(self,request,response):
        if "state" in request:
            self.set_power(request["state"])
        response["message"]=self.get_power()
        return CommandReturn.SUCCESS

    def set_power(self,value):
        if value==CommandState.ON:
            self.logger.debug("Turing node power ON")
            self.power_state=value
        elif value==CommandState.OFF:
            self.logger.debug("Turing node power OFF")
            self.power_state=value
        else:
            self.logger.error("Invalid power state requested!")
    
    def get_power(self):
        return self.power_state

################################################################################
# Command to control node reset
################################################################################

    def cmd_reset(self,request,response):
        if "state" in request:
            self.set_reset(request["state"])
        response["message"]=self.get_reset()
        return CommandReturn.SUCCESS

    def set_reset(self,value):
        if value==CommandState.ON:
            self.logger.debug("Turing node reset ON")
            self.reset_state=value
        elif value==CommandState.OFF:
            self.logger.debug("Turing node reset OFF")
            self.reset_state=value
        else:
            self.logger.error("Invalid power state requested!")
    
    def get_reset(self):
        return self.reset_state

################################################################################
# Commands for the measurement service
################################################################################

    def cmd_measurement(self,request,response):
        if "state" in request:
            if request["state"]==CommandState.ON:
                self.measurement_started=True
            elif request["state"]==CommandState.OFF:
                self.measurement_started=False

        response["message"]=self.get_measurement()
        return CommandReturn.SUCCESS

    def get_measurement(self):
        if self.measurement_started:
            return CommandReturn.STOPPED
        else:
            return CommandReturn.RUNNING

################################################################################
# Command list currnt nodes
################################################################################

    def motelist(self):
        motes=[]
        for node in self.nodes:
            if self.node_name == node.name:
                motes.append(node)
        return motes

################################################################################
# Command to indicate the server to reboot
################################################################################

    def cmd_reboot(self,request,response):
        return CommandReturn.SUCCESS

################################################################################
# Command dispatcher
################################################################################

    def cmd_process(self,request,response):
        return CommandReturn.SUCCESS

    def __init__(self, host, hostname, user_name, user_pass, nodes=[], tempdir="/tmp", resturl="http://dcube-web"):
        n=NodeFactory()
        n.register_node("sky",DummyNode)
        n.register_node("nrf52840dk-jlink",DummyNode)
        n.register_node("nrf52840dk-native",DummyNode)

        super().__init__(host, hostname, user_name, user_pass, nodes, tempdir)
        self.reset_state=CommandState.ON
        self.power_state=CommandState.ON
        self.measurement_started=False
        self.node_name=self.nodes[0]
 
