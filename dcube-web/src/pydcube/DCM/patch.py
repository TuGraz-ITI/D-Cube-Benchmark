import argparse
import logging
import json

import subprocess
import struct
import os

import xml.etree.ElementTree as ET
from elftools.elf.elffile import ELFFile

class BinaryPatcher:

    def patch_value(self,address,offset,bits,value,endianness,print_only=False):
        global args
        line=""
        with open(self.elffile, 'rb') as f:
            elf = ELFFile(f)
            s=None
            for section in elf.iter_sections():
                if ( address >= section['sh_addr']) and ( address <= (section['sh_addr']+section['sh_size']) ):
                    s = section
                    delta = address-section['sh_addr']
                    break
            if(s is None):
                self.logger.error("Section not found in fimrware")
                raise TypeError("Section not found in firmware")
                return None
            #self.logger.debug("Addr %s"%section['sh_addr'])
            #self.logger.debug("Size %s"%section['sh_size'])
            #self.logger.debug("ELF %s"%section['sh_offset'])
            #self.logger.debug("Delta %s"%delta)

            elfoffset=s['sh_offset']+delta
            #self.logger.debug("ELFOffset %s"%elfoffset)
            with open(self.elffile, 'rb') as m:
                m.seek(elfoffset+offset)
                if(bits==8):
                    line+=("value 0x%02x" % struct.unpack("<B",m.read(1)))
                elif(bits==16):
                    line+=("value 0x%04x" % struct.unpack("<H",m.read(2)))
                elif(bits==32):
                    line+=("value 0x%08x" % struct.unpack("<I",m.read(4)))
                else:
                    self.logger.error("Not supported")
                    return None
            if print_only:
                line+=" NOT PATCHED"
                return line

            line+=(" -> %s"%value)
            if (bits==8 and endianness=="little"):
                value=struct.pack("<B",value)
            elif (bits==16 and endianness=="little"):
                value=struct.pack("<H",value)
            elif (bits==32 and endianness=="little"):
                value=struct.pack("<I",value)
    
            else:
                self.logger.error("Not supported yet")
                return None
    
            with open(self.elffile, 'r+b') as m:
                m.seek(elfoffset+offset)
                m.write(value)
            return line
    
    def patch_element(self,var,offset=-1,count=-1,suffix="",prefix="",address=0,endianness=None,zero=True,config={}):
        global args
        if var.tag=="array":
            l=("###### array: name=" + var.get("name") + " count=" + var.get("count") +" ######")
            self.logger.debug(prefix+l)
            self.logger.debug(prefix+"="*len(l))
        if var.tag=="int":
            bits=int(var.get("bits"))
            if(offset>0):
                off=offset+int(var.get("offset",0),0)
            else:
               off=int(var.get("offset",0),0)
            txt=var.text+suffix
            if(count>-1):
                txt=txt+"["+str(count)+"]"
            if (txt in config):
                px=prefix.replace(" ",">")
            else:
                px=prefix
            line=(px+"%d bit (%s) variable %s at offset %06x "% (bits,var.tag,txt,off))
            value=0
            if(txt in config):
                value=config[txt]
            elif(zero==False):
                p=self.patch_value(address,off,bits,value,endianness=endianness,print_only=True)
                self.logger.debug("%s%s"%(line,p))
                return

            p=self.patch_value(address,off,bits,value,endianness=endianness)
            self.logger.debug("%s%s"%(line,p))
    
    def patch_recursive(self,section,offset=-1,count=-1,suffix="",prefix="",address=0,endianness=None,zero=True,config={}):
        if not (section.get("count") is None):
            self.patch_element(section,offset,count,suffix,prefix,address=address,endianness=endianness,zero=zero,config=config)
    
            o=int(section.get("offset",0),0)
            s=int(section.get("size",0),0)
            if(offset>0):
                o=o+offset
            else:
                o=o
            for i in range(0,int(section.get("count"))):
                for var in section:
                    if(count>=0):
                        sfx=suffix+"["+str(count)+"]"
                    else:
                        sfx=suffix
                    self.patch_recursive(var,o+(s*(i)),i,sfx,prefix+"  ",address=address,endianness=endianness,zero=zero,config=config)
        else:
            self.patch_element(section,offset,count,suffix,prefix,address=address,endianness=endianness,zero=zero,config=config)
            for var in section:
                self.patch_recursive(var,offset,-1,prefix,address=address,endianness=endianness,zero=zero,config=config)

    def convert_hex_elf(self):
        if self.arch=="msp430":
            subprocess.call(["msp430-objcopy", "-I" ,"ihex", "--output-target=elf32-msp430", self.hexfile, self.elffile])
        elif self.arch=="arm32l":
            subprocess.call(["arm-none-eabi-objcopy", "-I" ,"ihex", "--output-target=elf32-littlearm", self.hexfile, self.elffile])
        else:
            self.logger.error("Architecture not supported yet!")
            raise NotImplementedError()

    def convert_elf_hex(self):
        if self.arch=="msp430":
            subprocess.call(["msp430-objcopy", self.elffile, "-O", "ihex", self.hexfile])
        elif self.arch=="arm32l":
            subprocess.call(["arm-none-eabi-objcopy", self.elffile, "-O", "ihex", self.hexfile])
        else:
            self.logger.error("Architecture not supported yet!")
            raise NotImplementedError()

    def patch(self,layout,config,zero=True):
        self.convert_hex_elf() 

        tree = ET.parse(layout)
        root = tree.getroot()
        for section in root.iter('section'):
            address=int(section.get("address"),0)
            elfbits=int(section.get("bits"))
            endianness=section.get("endianness")
            l=("######### configuration section at address %06x in file %s #########" % (address,self.elffile))
            self.logger.debug(l)
            self.logger.debug("=" *len(l))
            self.patch_recursive(section,config=config,address=address,endianness=endianness,zero=zero)

        self.convert_elf_hex()
        os.remove(self.elffile)
    
    def __init__(self,hexfile,arch,tempdir="/tmp"):
        self.logger=logging.getLogger(__name__)
        self.hexfile=hexfile
        self.arch=arch

        filename=os.path.basename(self.hexfile)
        basename=os.path.splitext(filename)[0]
        self.elffile=os.path.join(tempdir,"%s.elf"%basename)
        self.logger.debug("Hexfile: %s"%self.hexfile)
        self.logger.debug("Elffile: %s"%self.elffile)



if __name__ == '__main__':
    FORMAT = "[%(name)16s - %(funcName)12s() ] %(message)s"
    logging.basicConfig(level=logging.DEBUG,format=FORMAT)

    parser = argparse.ArgumentParser(description="D-Cube Binary Patching")
    parser.add_argument("--patch",dest="patch_json",required=True, type=str,help="Overrides in JSON format")
    parser.add_argument("--xml",dest="layout_xml",required=True, type=str,help="Memory Layout in XML format")
    parser.add_argument("--hex",dest="hexfile",required=True,type=str,help="Firmware file")
    parser.add_argument("--arch",dest="arch",required=True,type=str,help="Target Architecture")

    args = parser.parse_args()
    firmware=args.hexfile

    bp=BinaryPatcher(args.hexfile,args.arch)

    with open(args.patch_json) as json_file:
        config=json.load(json_file)

    bp.patch(args.layout_xml,config)

    exit(0)
