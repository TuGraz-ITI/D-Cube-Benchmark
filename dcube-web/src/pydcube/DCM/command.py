from enum import Enum

class CommandType(str,Enum):
    UNKNOWN = "unknown"
    PING = "ping"
    TIMESTAMP = "timestamp"
    MOTELIST = "motelist"
    RESET = "reset"
    POWER = "power"
    PROGRAM = "program"
    MOTE = "mote"
    MEASUREMENT = "measurement"
    TRACE = "treace"
    REBOOT = "reboot"
    EXPERIMENT = "experiment"
    PROCESS = "process"

class CommandState(str,Enum):
    ON="on"
    OFF="off"

class CommandReturn(str,Enum):
    SUCCESS="success"
    FAILED="failed"
    FORMAT="format"
    MISSING="missing"
    STOPPED="stopped"
    RUNNING="running"

class CommandExe(str,Enum):
    CUSTOM="custom"
    JAMMING="jamming"
    BLINKER="blinker"
