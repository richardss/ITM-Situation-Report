#!/usr/bin/env python
# coding=utf-8
__author__ = 'ibm_linh'

#######################################################
# 2014-07-09
# enrich situation level (2,3) and notification method(mail,sms)
# 2014-07-15
# add type for situation in sitdesc
# 2019-10-09
# translate chinese terms for european users
#######################################################

from bccomm import itmcomm
import re
import sys
import os
import logging
import logging.handlers
from xlrd import open_workbook

#import pydevd
#pydevd.settrace('182.248.6.42', port=4567, stdoutToServer=True, stderrToServer=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%m-%d %H:%M',
    filename='genlist.log',
    filemode='w')

console = logging.StreamHandler()
console.setLevel(logging.INFO)
#console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

log = logging.getLogger('main')

pcl = ['UX', 'UL', 'PX', 'UD', 'MQ', 'LZ']
ual = ['C' + str(i) for i in range(1, 10)]
del(ual[6])   #UA C7 is not used current
pcl.extend(ual)
#pcl = ('UX',)

with open('hosts', 'r') as hosts:
    hostlist = [x.strip() for x in hosts.readlines()]


## Generating data structures outdict ,keyforhostname
## hostA: {UX:[{sitdict1},{sitdict2}], UL:[{sitdict1},{sitdict2}] }
## hostB: {LZ:[{sitdict1},{sitdict2}], UD:[{sitdict1},{sitdict2}] }
## hostC: {UX:[{sitdict1},{sitdict2}], UL:[{sitdict1},{sitdict2}] }
##UD and MQ contain multiple instances ，Add the key of the instance name (instname) for sitdict
itmcomm.login('182.248.56.60', 'sysadmin', 'bcdctiv1')
#itmcomm.login('182.248.6.217', 'sysadmin', 'tivoli')
itmcomm.getipfile()
outdict = {}
#hosts_in_old_tems = []
for host in hostlist:
    log.info('=' * 40)
    log.info("Process Host: " + host)
    log.info("\nTacmd viewnode return as below:\n")
    viewnode_ret = itmcomm.viewnode(host, pcfilter=pcl)
    log.debug("tacmd viewnode return is " + str(viewnode_ret))
    if viewnode_ret is None:
        log.info(host + " is not in this HUB env")
        #hosts_in_old_tems.append(host)
        continue
    else:
        outdict[host] = {}
        msl = viewnode_ret.keys()  #Get the child nodes under the OS node
        for ms in msl:
            pc = viewnode_ret.get(ms)  # Get the child node's PC
            log.info("TEMA: " + pc)
            listsit_ret = itmcomm.listsit(ms, pc, host)
            if listsit_ret is None:
                continue
            else:
                if outdict[host].has_key(pc):
                    outdict[host][pc].extend(listsit_ret)
                else:
                    outdict[host][pc] = listsit_ret
                log.debug(outdict[host][pc])
    log.info('=' * 40)



if len(outdict) == 0:
    log.info("not found situatoins for those hosts in the HUB TEMS!")
    sys.exit(0)

log.debug(outdict)

### Generate a head dictionary from the outdict dictionary. As the column header of the table,
### key is pc, value is set(situation), covering all the same PC types returned by ITM from the host list.
### UX: set(sit1,sit2...)
### UD: set(sit1,sit2...)
### Rule 1: The PC type is traversed by the pcfilter list. As long as there is a host with a PC type sit, the set(sit) of this type is not empty.
### Rule 2: If all hosts do not have a certain type of sit in the pcfilter list, the head dictionary will not contain the key of the class pc, value

newhostlist = outdict.keys()  # Newhostlist contains only the hosts that exist in this TEMS environment, a subset of the hosts file
newpcl = set()                # Newpcl contains a subset of pc, pcfilter lists present in outdict
for host in newhostlist:
    newpcl.update(outdict[host].keys())

log.debug(newhostlist)
log.debug(newpcl)

head = {}
tmpd ={}
for host in newhostlist:
    head.update(tmpd.fromkeys(outdict[host].keys()))
for pc in head.keys():
    head[pc] = set()
for host in newhostlist:
    for pc in outdict[host].keys():
        #head[pc] = set()
        sitlist = outdict[host][pc]
        if sitlist is None:
            continue
        else:
            host_sitfn = set([x['FullName'] or x['Name'] for x in sitlist])
            head[pc].update(host_sitfn)

log.debug(head)


### Generate a seq_head dictionary from the head dictionary,
### key is pc, value is list(situation), the sit in the sitdesc file is the first priority into the list, and the remaining part sort()
### UX: [(sit1,sit1chn,sit1type,sit1level,sit1notification), (sit2,sit2chn,sit2type,sit2level,sit2notification)...]
### UD: [(sit1,sit1chn,sit1type,sit1level,sit1notification), (sit2,sit2chn,sit2type,sit2level,sit2notification)...]
### As the sitdesc file Chinese is empty, the default value is set to 'Non'

seq_sitdesc = []
with open('sitdesc', 'r') as sitfile:
    for x in sitfile.readlines():
        dscli = re.split(r'\s+', x.strip())
        if len(dscli) > 1:
            seq_sitdesc.append((dscli[0], dscli[1], dscli[2]))
        else:
            seq_sitdesc.append(('Non', 'Non', 'Non'))

log.debug(seq_sitdesc)

seq_head = {}
for pc in newpcl:
    seq_head[pc] = []
    for (type, sit, desc) in seq_sitdesc:
        if sit in head[pc]:
            seq_head[pc].append([sit, desc, type]) # Sort the order of the sit lines in the sitdesc file
    ##Remaining part sorting (Chinese definition is not defined in sitdesc)
    if len(seq_head[pc]) > 0:
        left = list(head[pc] - set([x[0] for x in seq_head[pc]]))
        left.sort()
        seq_head[pc].extend([[x, 'Non', 'Non'] for x in left])  #Some Chinese explanations and types are not found
    else:
        seq_head[pc].extend([[x, 'Non', 'Non'] for x in head[pc]])

enrich_itm_sit = open_workbook('enrich_itm_sitdesc.xls')
sitws = enrich_itm_sit.sheet_by_index(0)

for pc in seq_head.keys():
    for sit_list in seq_head[pc]:
        sit = sit_list[0]
        level = ''
        noti = ''
        for row_i in range(sitws.nrows):
            if sit == sitws.cell(row_i, 0).value:
                level = sitws.cell(row_i, 4).value.encode('utf-8')
                noti = sitws.cell(row_i, 5).value.encode('utf-8')
                break
        sit_list.extend([level, noti])


###Generate out dictionary according to seq_head and outdict
###key is host, value is the order state list (according to the order in seq_head)
## hostA: {UX:[sit1_status,sit2_status], UL:[sit1_status,sit2_status]}
## hostB: {UX:[sit1_status,sit2_status], UL:[sit1_status,sit2_status]}
## hostC: {UX:[sit1_status,sit2_status], UL:[sit1_status,sit2_status]}
### In the order of pcl list, query seq_head to get the order of sit, query outdict to get the state of sit
###sit_status is a dictionary, the key is instname, and the value is the corresponding state.

out = {}
for host in newhostlist:
    out[host] = {}
    for pc in pcl:
        if pc in seq_head.keys():
            out[host][pc] = []
            pc_sit_seq = [x[0] for x in seq_head[pc]]
            if outdict[host].get(pc):
                for sit in pc_sit_seq:
                    #sit_status = 'Non'
                    num_of_match = 0
                    sit_status_dict = {}
                    for sitd in outdict[host][pc]:
                        if (
                            sit == sitd.get('FullName')
                            or
                            sit == sitd.get('Name')
                        ):
                            num_of_match += 1
                            sit_status = sitd.get('Status')
                            sit_inst = sitd.get('InstName')
                            #sit_status_dict.update(dict(sit_inst=sit_status))
                            sit_status_dict.update({sit_inst: sit_status})
                    if num_of_match == 0:
                        #out[host][pc].append(dict(host='Non'))
                        out[host][pc].append({host: 'Non'})
                    else:
                        out[host][pc].append(sit_status_dict)

            else:
                out[host][pc] = [{host: 'Non'} for x in range(len(pc_sit_seq))]




###Write to csv file based on seq_head and out
###Write seq_head first in order of pcl, then write out in the order of hosts
hostname = os.uname()[1]
outf = hostname + '.csv'

with open(outf, 'w') as output:
    Hl_sit = 'situation'
    Hl_pc = 'Classification'
    Hl_type = 'alarm type'
    Hl_level = 'alarm level'
    Hl_noti = 'Notification method'
    Hl_sitdsc = 'Chinese explanation'


    for pc in pcl:
        if pc in seq_head.keys():
            hl_sit += ',' + ','.join([x[0] for x in seq_head[pc]])
            hl_sitdsc += ',' + ','.join([x[1] for x in seq_head[pc]])
            hl_type += ',' + ','.join([x[2] for x in seq_head[pc]])
            hl_level += ',' + ','.join([x[3] for x in seq_head[pc]])
            hl_noti += ',' + ','.join([x[4] for x in seq_head[pc]])
            hl_pc += ',' + ','.join([pc for i in range(len(seq_head[pc]))])

    hl_sit += ',' + 'SIT_XT_UA_C8_Ping'
    Hl_sitdsc += ',' + 'Ping host is not responding within 3 minutes'
    Hl_type += ',' + 'Ping'
    Hl_level += ',' + '3'
    Hl_noti += ',' + 'Mail and SMS notifications
    hl_pc += ',' + 'C8'

    for i in (hl_sit, hl_level, hl_noti, hl_type, hl_pc, hl_sitdsc):
        output.write(i)
        output.write("\n")

    #output.write(hl_sit)
    #output.write("\n")
    #output.write(hl_pc)
    #output.write("\n")
    #output.write(hl_sitdsc)
    #output.write("\n")

    pingdict = {}
    with open('ipfile', 'r') as ipf:
        for l in ipf.readlines():
            ip, pinghost = re.split(r'\s+', l.strip())
            pingdict[pinghost] = ip

    for host in hostlist:
        if host in newhostlist:
            sit_status_row = host
            for pc in pcl:
                if pc in seq_head.keys():
                    if pc in ['UD', 'MQ', 'LO']:
                        if outdict[host].get(pc):
                            kvl = ['|'.join([k + '->' + v for (k, v) in sitdict.items()]) for sitdict in out[host][pc]]
                        else:
                            kvl = [sitdict.values()[0] for sitdict in out[host][pc]]
                    else:
                        #kvl = [','.join([v for (k, v) in sitdict.items()]) for sitdict in out[host][pc]]
                        kvl = [sitdict.values()[0] for sitdict in out[host][pc]]
                    log.debug(kvl)
                    sit_status_row += ',' + ','.join(kvl)
            log.debug(sit_status_row)

            pingstatus = 'Non'
            if host in pingdict.keys():
                pingstatus = "Started"
            else:
                pingstatus = "Stopped"
            sit_status_row += ',' + pingstatus
            output.write(sit_status_row)
            output.write("\n")
