from .server import Server
from .command import CommandState,CommandReturn

from .nodes.node import NodeFactory
from .nodes.sky import Sky
from .nodes.nrf52840dk import NRFNative,NRFJLink

import subprocess

import pysystemd
import usb.core
import pigpio

POWER_PIN=21
RESET_PIN=20
MAYOR_PIN=6
MINOR_PIN=5

class Raspberry(Server):
    
################################################################################
# Select node using the mux
################################################################################

    def cmd_select_node(self,request,response):
        ret=CommandReturn.FAILED
        if "mote" in request:
            for node in self.nodes:
                if node.name==request["mote"]:
                    return self.set_mux(node.mayor, node.minor)
            else:
                response["message"]="Invalid mux state requested!"
                self.logger.error(response["message"])
            
        else:
            response["message"]="Mayor and Minor Pin must be specified!"
            self.logger.error(response["message"])
        return ret

    def set_mux(self,mayor,minor):
        ret=CommandReturn.FAILED
        if ( ( mayor==1 or mayor==0) and
            (minor==1 or minor==0) ):
                self.pi.write(MAYOR_PIN,mayor)
                self.pi.write(MINOR_PIN,minor)
                ret=CommandReturn.SUCCESS
        else:
            self.logger.error("Invalid mux state requested!")
            
        return ret

################################################################################
# Reboot Raspberry Pi via systemd
################################################################################

    def reboot(self):
        power=pysystemd.power()
        power.reboot()

################################################################################
# Commands for the measurement service
################################################################################

    def cmd_measurement(self,request,response):
        if "state" in request:
            if request["state"]==CommandState.ON:
                self.start_measurement()
            elif request["state"]==CommandState.OFF:
                self.stop_measurement()

        response["message"]=self.get_measurement()
        return CommandReturn.SUCCESS

    def get_measurement(self):
        status=pysystemd.status("d-cube-influx.service")
        if status.is_run():
            return CommandReturn.STOPPED
        else:
            return CommandReturn.RUNNING

    def start_measurement(self):
        service=pysystemd.services("d-cube-influx.service")
        service.start() #TODO handle return codes

        i2c_service=pysystemd.services("d-cube-i2c-influx.service")
        i2c_service.start() #TODO handle return codes


    def stop_measurement(self):
        service=pysystemd.services("d-cube-influx.service")
        service.stop()  #TODO handle return codes

        i2c_service=pysystemd.services("d-cube-i2c-influx.service")
        i2c_service.stop()  #TODO handle return codes


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
            self.pi.write(POWER_PIN,1)
        elif value==CommandState.OFF:
            self.logger.debug("Turing node power OFF")
            self.pi.write(POWER_PIN,0)
        else:
            self.logger.error("Invalid power state requested!")
    
    def get_power(self):
        if self.pi.read(POWER_PIN)==1:
            return CommandState.ON
        else:
            return CommandState.OFF

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
            self.pi.write(RESET_PIN,1)
        elif value==CommandState.OFF:
            self.logger.debug("Turing node reset OFF")
            self.pi.write(RESET_PIN,0)
        else:
            self.logger.error("Invalid power state requested!")
    
    def get_reset(self):
        if self.pi.read(RESET_PIN)==1:
            return CommandState.ON
        else:
            return CommandState.OFF

################################################################################
# Command list currnt nodes
################################################################################

    def motelist(self):
        motes=[]
        for node in self.nodes:
            dev=usb.core.find(idProduct=node.product_id,idVendor=node.vendor_id)
            if not dev==None:
                motes.append(node)
        return motes

    def __init__(self, host, hostname, user_name, user_pass, nodes=[],tempdir="/scratch"):
        n=NodeFactory()
        n.register_node("sky",Sky)
        n.register_node("nrf52840dk-jlink",NRFJLink)
        n.register_node("nrf52840dk-native",NRFNative)

        super().__init__(host,hostname,user_name,user_pass, nodes,tempdir)
        self.pi=pigpio.pi()
