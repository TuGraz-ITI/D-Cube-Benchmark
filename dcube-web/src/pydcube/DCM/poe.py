import paramiko
import time
import logging
import enum
import re

class PoEClient:
    def __init__(self,topology):
        self.logger=logging.getLogger("PoE Client")
        self.switches={}
        self.topology=topology
    
        for t in self.topology:
            if t["type"]=="Cisco":
                self.switches[t["switch"]]=CiscoSwitch(t["switch"])
            if t["type"]=="HP":
                self.switches[t["switch"]]=HPSwitch(t["switch"])
            if t["type"]=="Mikrotik":
                self.switches[t["switch"]]=MikrotikSwitch(t["switch"])

    
    def set_node(self,node,state):
        n=self.get_node(node)
        switch=self.switches[n["switch"]]
        port=n["port"]
        switch.set_port(port,state)

    def get_node(self,node):
        for c in self.topology:
            for n in c["nodes"]:
                if n["hostname"]==node:
                    self.logger.debug("%s is attached to %s on %s"%(n["hostname"],c["switch"],n["port"]))
                    d={"switch":c["switch"],"port":n["port"],"hostname":n["hostname"],"ip":n["ip"]}
                    return d
    
    def print_topology(self):
        for c in self.topology:
            try:
                print("%s Switch: %s"%(c["type"],c["switch"]))
                for node in c["nodes"]:
                    n=self.switches[c["switch"]].get_port(node["port"])
                    print("\t%s on port %s is %s(%s) @ %s"%(node["hostname"],node["port"],n["power"],n["policy"],n["consumption"]))
            except KeyError:
                pass

class PoEStatus(enum.Enum):
    ON=1
    OFF=0

class PoEPolicy(enum.Enum):
    ON=1
    OFF=0

class PoE:
    def __init__(self,hostname,username,password,port=22):
        self.hostname=hostname
        self.logger=logging.getLogger("PoE Client")
        logging.getLogger("paramiko").setLevel(logging.WARNING)
        self.username=username
        self.password=password
        self.port=port
        self.status=None

        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def expect(self,connection,string):
        buf=""
        while not string in buf:
            time.sleep(0.1)
            buf+=connection.recv(65535).decode()
        return buf

    def update_status(self):
        pass

    def set_port(self,port,state):
        pass

    def get_port(self,port):
        if self.status==None:
            self.update_status()
        return self.status[port]


class HPSwitch(PoE):
    def __init__(self,hostname,username="admin",password="hpititisu",port=22):
        super().__init__(hostname,username,password,port)

    def set_port(self,port,state):
        self.client.connect(self.hostname, self.port, self.username, self.password)
        c = self.client.invoke_shell(term='vt100', width=250, height=100)
        self.expect(c,">")
        c.send("_cmdline-mode on\r")
        self.expect(c,"]")
        c.send("Y\r")
        self.expect(c,"Please input password:")
        c.send("Jinhua1920unauthorized\r")
        self.expect(c,">")
        c.send("screen-length disable\r")
        self.expect(c,">")
        
        c.send("super\r")
        self.expect(c,">")
        c.send("system-view\r")
        self.expect(c,"]")
        c.send("interface %s\r"%port)
        self.expect(c,"]")

        s="undo poe enable" if (state==PoEPolicy.OFF) else "poe enable"
        c.send("%s\r"%s)
        self.expect(c,"]")

        self.client.close()

    def update_status(self):
        self.client.connect(self.hostname, self.port, self.username, self.password)
        c = self.client.invoke_shell(term='vt100', width=250, height=100)
        self.expect(c,">")
        c.send("_cmdline-mode on\r")
        self.expect(c,"]")
        c.send("Y\r")
        self.expect(c,"Please input password:")
        c.send("Jinhua1920unauthorized\r")
        self.expect(c,">")
        c.send("screen-length disable\r")
        self.expect(c,">")
        c.send("display poe interface\r")
        buf=self.expect(c,">")
        status={}
        for line in buf.splitlines():
            line=line.strip()
            if line.startswith("GE"):
                token=[x.strip() for x in line.split()]
                policy=PoEPolicy.ON if token[6]=="delivering-power" else PoEPolicy.OFF
                power=PoEStatus.ON if token[4]=="on" else PoEStatus.OFF
                port=token[0].replace("GE","GigabitEthernet ")
                status[port]={"policy":policy,"power":power,"consumption":token[3]}
        self.status=status
        self.client.close()

class CiscoSwitch(PoE):
    def __init__(self,hostname,username="admin",password="iti-lab17.",port=22):
        super().__init__(hostname,username,password,port)

    def set_port(self,port,state):
        self.client.connect(self.hostname, self.port, self.username, self.password)
        c = self.client.invoke_shell(term='vt100', width=250, height=100)
        self.expect(c,">")
        c.send("en\r")
        self.expect(c,"Password:")
        c.send("%s\r"%self.password)
        self.expect(c,"#")
        c.send("configure terminal\r")
        self.expect(c,"(config)#")
        c.send("interface %s\r"%port)
        self.expect(c,"(config-if)#")
        s="never" if (state==PoEPolicy.OFF) else "auto"
        c.send("power inline %s\r"%s)
        self.expect(c,"(config-if)#")
        self.client.close()

    def update_status(self):
        self.client.connect(self.hostname, self.port, self.username, self.password)
        c = self.client.invoke_shell(term='vt100', width=250, height=100)
        self.expect(c,">")
        c.send("en\r")
        self.expect(c,"Password:")
        c.send("%s\r"%self.password)
        self.expect(c,"#")
        c.send("show power inline\r")
        buf=self.expect(c,"#")
        status={}
        for line in buf.splitlines():
            if line.startswith("Fa"):
                token=[x.strip() for x in line.split()]
                policy = PoEPolicy.ON if (token[1]=="auto") else PoEPolicy.OFF
                power = PoEStatus.ON if (token[2]=="on") else PoEStatus.OFF
                status[token[0]]={"policy":policy,"power":power,"consumption":token[3]}
        self.status=status
        self.client.close()

class MikrotikSwitch(PoE):

    def __init__(self,hostname,username="admin",password="",port=22):
        super().__init__(hostname,username,password,port)
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def set_port(self,port,state):
        self.client.connect(self.hostname, self.port, self.username, self.password)
        c = self.client.invoke_shell(term='vt100', width=250, height=200)
        self.expect(c,">")
        s="off" if (state==PoEPolicy.OFF) else "auto-on"
        c.send("interface ethernet poe set poe-out=%s %s\r"%(s,port))
        self.expect(c,">")
        self.client.close()

    def update_status(self):
        self.client.connect(self.hostname, self.port, self.username, self.password)
        c = self.client.invoke_shell(term='vt100', width=250, height=200)
        self.expect(c,">")
        c.send("interface ethernet poe print without-paging\r")
        buf=self.expect(c,">")
        status={}
        buf=self.ansi_escape.sub('',buf)
        for line in buf.splitlines():
            if "ether" in line:
                token=[x.strip() for x in line.split()]
                policy = PoEPolicy.ON if (token[2]=="auto-on") else PoEPolicy.OFF
                #TODO use monitor to get power status
                status[token[1]]={"policy":policy,"power":None,"consumption":None}
        for portname in status.keys():
            c.send("interface ethernet poe monitor numbers=%s once\r"%portname)
            buf=self.expect(c,">")
            buf=self.ansi_escape.sub('',buf)
            power=None
            consumption=None
            for line in buf.splitlines():
                if "poe-out-status" in line:
                    token=[x.strip() for x in line.split(":")]
                    power = PoEStatus.ON if (token[1]=="powered-on") else PoEStatus.OFF
                elif "poe-out-power" in line:
                    token=[x.strip() for x in line.split(":")]
                    consumption = token[1]
            status[portname]={"policy":status[portname]["policy"],"power":power,"consumption":consumption}
        self.status=status
        self.client.close()

