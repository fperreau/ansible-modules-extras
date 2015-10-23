#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2015, Frederic PERREAU <fperreau@fr.ibm.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
author: Frederic PERREAU
module: sl_hardware
short_description: Manage vHardware machine supported by IBM SoftLayer cloud.
description:
  - This module helps you to create, destroy, .. the public or private hardware machines (vguest) hosted in IBM SoftLayer cloud.
    It is now a pleasure to deploy, configure and manage the SoftLayer hardware with the best configuration manager ANSIBLE. 
    This module requires the SofLayer python library with username and api_key configured.
version_added: "0.1"
options:
  name:
    description:
      - Name of the hardware machine managed. It is a full qualified domain name.
        Name is required for to create server with flavor resources need
    required: false
    default: no
  state:
    description:
      - I(running) - start or create hardware machine.
      - I(destroy) - delete hardware machine.
      - I(list) - show hardware machines.
      - I(facts) - extract the description of hardware machine.
      - I(info) - show configuration of hardware machine.
    required: true
    choice: [ "running", "destroy", "list", "info", "facts" ]
    default: no
  hostname:
    description:
      - select hardware machine by short name
    required: false
    default: no
  domain:
    description:
      - select hardware machine by domain name
    required: false
    default: no
  datacenter:
    description:
      - select hardware machine by datacenter name
    required: false
    default: no
  tags:
    description:
      - select hardware machine by tags name
    required: false
    default: no
  flavor:
    description:
      - define the flavor when create the hardware machine
    required: false
    default: see example
  sshkey:
    description:
      - define the label of sshkey use to connect in hardware machine with root account 
    required: false
    default: Frederic PERREAU
  wait:
    description:
      - Waits on a hardware machine transaction for the specified amount of time 
    required: false
    default: no
  hourly:
    description:
      - choose hourly hardware machine (default)
    required: false
    default: no
  monthly:
    description:
      - choose monthly hardware machine     
    required: false
    default: no
requirements: [ "softlayer-python" ]
author: Frederic PERREAU
notes: draft
'''

EXAMPLES = '''
---
# a playbook task line
sl_hardware name={{iventory_hostname}} state=running flavor={{lookup('template','template/sl_server.json.j2)}}

# /usr/bin/ansible invocations
ansible host -m sl_hardware -i inventory -a "state=list datacenter=par01"
ansible host -m sl_hardware -i inventory -a "state=facts domain=domain.local"
ansible host -m sl_hardware -i inventory -a "state=destroy name=server.domain.local"

# a playbook example of defining and launching an SolftLayer hardware machine
tasks:
  name: define hardware
  sl_hardware: name=server.domain.local command=running
              flavor="{{lookup('template', 'template/sl_server.json.j2')}}"

# default flavor file example
  {
   'hourly'     : True, 
   'no_public'  : True,
   'location'   : 'par01',
   'size'       : 'S1270_8GB_2X1TBSATA_NORAID',
   'os'         : 'UBUNTU_14_64',
   'port_speed' : 100,
  }
'''

import sys
import string

try:
    import SoftLayer
    from SoftLayer.managers.hardware import HardwareManager
    from SoftLayer.managers.sshkey import SshKeyManager
    from SoftLayer import utils
except ImportError:
    print "failed=True msg='softlayer python library unavailable'"
    sys.exit(1)

ALL_STATES        = ['list','info','facts','running','halted','paused','destroy']
ALL_POWER_STATES  = ['Running','Halted','Paused','Undefined']
ALL_STATUS        = ['Active']

MASK_LIST    = "fullyQualifiedDomainName,id,datacenter.name,primaryBackendIpAddress,hardwareStatusId"
MASK_FACTS   = "id"

BMS_DEFAULT = {
               'hourly'     : True, 
               'no_public'  : True,
               'location'   : 'par01',
               'size'       : 'S1270_8GB_2X1TBSATA_NORAID',
               'os'         : 'UBUNTU_14_64',
               'port_speed' : 100,
               'tags'       : 'mytag',
               }

SSHKEY_LABEL = 'Frederic PERREAU'

class vHardware(object):
    
    __slots__ = ['module','client','hw','vdi','sshkey']
    
    def __init__(self,module):
        self.module = module
        self.client = None
        self.hw     = None
        self.vdi    = None
        self.sshkey = None

    ###    
    def state(self,name,id,results):
        list_hardware = []
        items = self.hw.list_hardware(
            hostname   = name.split('.',1)[0] if name is not None else self.module.params.get('hostname'),
            domain     = name.split('.',1)[1] if name is not None else self.module.params.get('domain'),
            datacenter = self.module.params.get('datacenter'),
            #mask = MASK_LIST,
            )
        for item in items:
            list_hardware.append(self.get_instance(item))
        #results['debug']=items
        return list_hardware

    ###    
    def list(self,name,id,results):
        list_hardware = self.state(name,id,results)
        if not len(list_hardware):
            results['msg'] = "vHardware not found"
        results['instances'] = list_hardware

    ###
    def facts(self,name,id,results):
        ansible_facts = {}
        list_facts = []
        del results['instances']
        
        items = self.hw.list_hardware( \
            hostname   = name.split('.',1)[0] if name is not None else self.module.params.get('hostname'),
            domain     = name.split('.',1)[1] if name is not None else self.module.params.get('domain'),
            datacenter = self.module.params.get('datacenter'),
            tags       = self.module.params.get('tags'),
            mask       = MASK_FACTS )
        for item in items:
            list_facts.append(self.get_fact(self.hw.get_hardware(item['id'])))
        
        if len(list_facts):
            for fact in list_facts:
                name = fact['name']
                if name not in ansible_facts.keys():
                    ansible_facts[name] = fact
                else:
                    self.module.fail_json(msg="duplicated vHardware name")
            results['ansible_facts'] = ansible_facts
            #results['_ansible_verbose_override'] = True
        else:
            results['msg'] = "vHardware not found"

    ###
    def info(self,name,id,results):
        list_instances = []

        items = self.state(name,id,results)
        for item in items:
            list_instances.append(self.hw.get_hardware(item['id']))

        if len(list_instances) == 0:
            results['msg'] = "vHardware not found"
        results['instances'] = list_instances
    
    ###
    def create(self,name,id,results):
        if name is None:
            self.module.fail_json(msg="vguest name need to be defined.")

        bms     = self.module.params.get('flavor')
        wait    = self.module.params.get('wait')
        hourly  = self.module.boolean(self.module.params.get('hourly'))  
        monthly = self.module.boolean(self.module.params.get('monthly'))

        if monthly is True: bms['hourly'] = False
        if hourly is True:  bms['hourly'] = True
        
        # must set tags after place_order
        bms_tags = None
        if 'tags' in bms.get_keys():
            bms_tags = bms['tags']
            del(bms['tags'])
        
        bms['hostname'] = name.split('.',1)[0]
        bms['domain']   = name.split('.',1)[1]
        bms['ssh_keys'] = self.sshkey
        
        order = self.hw.verify_order(**bms)
        inst  = self.hw.place_order(**bms)
        results['debug_inst'] = inst
        
        state_inst = self.state(name,id,results)

        if bms_tags:
            self.hw.edit(hardware_id=state_inst['id'], tags=bms_tags)

        results['changed'] = True
        results['instances'] = state_inst

    ###
    def destroy(self,name,id,results):
        if self.hw.cancel_hardware(id,immediate=True):
            results['changed'] = True

        for item in self.state(name,id,results):
            results['instances'].append(item)
        
    ###
    def start(self,name,id,results): self.nop(name,id,results)
     
    ###
    def stop(self,name,id,results): self.nop(name,id,results)
     
    ###
    def suspend(self,name,id,results): self.nop(name,id,results)
        
    ###
    def resume(self,name,id,results): self.nop(name,id,results)

    ###
    def nop(self,name,id,results):
        for item in self.state(name,id,results):
            results['instances'].append(item)
     
    ###
    def main(self):
        FINITE_STATE = {
                        'Undefined':{ 'running':self.create, },
                        'Running'  :{ 'paused':self.suspend, 'halted':self.stop, 'destroy':self.destroy, 'running':self.nop, },
                        'Halted'   :{ 'running':self.start, 'destroy':self.destroy, 'halted':self.nop, },
                        'Paused'   :{ 'running':self.resume, 'destroy':self.destroy, 'paused':self.nop, },
                        '_NONE_'   :{ 'list':self.list, 'info':self.info, 'facts':self.facts, },
                        }

        state  = self.module.params.get('state')
        name   = self.module.params.get('name')
        sshkey = self.module.params.get('sshkey')

        results = { 'changed':False, 'state':state, 'instances':[] }        

        try:
            self.client = SoftLayer.create_client_from_env()
            self.hw     = HardwareManager(self.client)
            self.vdi    = self.client['Virtual_Disk_Image']
            self.sshkey = SshKeyManager(self.client)._get_ids_from_label(sshkey)

            if state in FINITE_STATE['_NONE_'].keys():                
                FINITE_STATE['_NONE_'][state](name,0,results)
            else:
                items = self.state(name,0,results)
                if not len(items):
                    items = [{ 'state':'Undefined', 'name':name, 'id':0 }] ## to create hardware with a state Undefined

                for item in items:
                    FINITE_STATE[item['state']][state](item['name'],item['id'],results)
                    
        except SoftLayer.SoftLayerAPIError as e:
            self.module.fail_json(msg="exception SoftLayer API faultCode=%s, faultString=%s" % (e.faultCode, e.faultString))
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback,limit=1)
            trace = traceback.format_exc(limit=0)
            self.module.fail_json(msg="exception faultCode:%s, faultString=%s, traceBack=%s" % (type(e),e.args,trace))

        self.module.exit_json(**results)

#
# TOOLS
#
    ### 
    def get_instance(self,inst):
        info = {
            'id'          : inst['id'],
            'name'        : inst['fullyQualifiedDomainName'],
            'datacenter'  : inst['datacenter']['name'],
            'state'       : "Running",
            'status'      : "Active",
            'stHardware'  : inst['hardwareStatusId'],
            'address'     : 'undefined',
            }

        if 'primaryBackendIpAddress' in inst.keys():
            info['address'] = inst['primaryBackendIpAddress']
        elif 'primaryIpAddress' in inst.keys():
            info['address'] = inst['primaryIpAddress']

        if 'activeTransaction' in inst.keys():
            info['stTransaction'] = inst['activeTransaction']['transactionStatus']['friendlyName']
        return info
    
    ###    
    def get_fact(self,inst):
        info = {
            'id'          : inst['id'],
            'name'        : inst['fullyQualifiedDomainName'],
            'hostname'    : inst['hostname'],
            'domain'      : inst['domain'],
            'datacenter'  : inst['datacenter']['name'],
            'state'       : "Running",
            'status'      : "Active",
            'cpus'        : inst['processorPhysicalCoreAmount'],
            'memory'      : inst['memoryCapacity'],
            'os_code'     : inst['operatingSystem']['softwareLicense']['softwareDescription']['referenceCode'],
            'hourly'      : inst['hourlyBillingFlag'],
            'private'     : inst['privateNetworkOnlyFlag'],
            'tags'        : [i['tag']['name'] for i in inst['tagReferences']],
            'address'     : 'undefined',
            }

        # Address value if defined
        if 'primaryBackendIpAddress' in inst.keys():
            info['address'] = inst['primaryBackendIpAddress']
        elif 'primaryIpAddress' in inst.keys():
            info['address'] = inst['primaryIpAddress']
        
        # privateAddress value if defined
        if 'networkManagementIpAddress' in inst.keys():
            info['managementAddress'] = inst['networkManagementIpAddress']
        if 'primaryBackendIpAddress' in inst.keys():
            info['privateAddress'] = inst['primaryBackendIpAddress']
        if 'primaryIpAddress' in inst.keys():
            info['publicAddress'] = inst['primaryIpAddress']

        # vlan
        if len(inst['networkVlans']):
            for vlan in inst['networkVlans']:
                networkSpace = vlan['networkSpace']
                if networkSpace == 'PRIVATE': info['private_vlan']=vlan['vlanNumber']
                if networkSpace == 'PUBLIC':  info['public_vlan']=vlan['vlanNumber']
        
        # Network Speed
        nic_speed = 0
        if len(inst['networkComponents']):
            for networkComponent in inst['networkComponents']:
                if networkComponent.get('primarySubnet'):
                    if 'ACTIVE' in networkComponent['status']:
                        if nic_speed < networkComponent['maxSpeed']:
                            nic_speed = networkComponent['maxSpeed']
                    info['nic_speed'] = nic_speed
            
        # User Data
        if len(inst['userData']):
            info['userData'] = inst['userData'][0]

        # Post Install Script URI
        if inst.get('postInstallScriptUri') is not None:
            info['post_uri'] = inst['postInstallScriptUri']
                    
        return info
    
#
# MAIN
#
def main():    
    module = AnsibleModule(
        argument_spec = dict(
            state        = dict(required=True, choices=ALL_STATES),
            name         = dict(type='str'),
            hostname     = dict(type='str'),
            domain       = dict(type='str'),
            datacenter   = dict(type='str'),
            tags         = dict(type='str'),
            wait         = dict(type='int',  default=600),
            flavor       = dict(type='dict', default=BMS_DEFAULT),
            sshkey       = dict(type='str',  default=SSHKEY_LABEL),
            hourly       = dict(choices=BOOLEANS, default='yes'),
            monthly      = dict(choices=BOOLEANS, default='no' ),
            ),
        required_one_of = [['state']],
        mutually_exclusive = [['hourly','monthly']]
        ) 
    vHardware(module).main()

###                              
from ansible.module_utils.facts import *
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()

