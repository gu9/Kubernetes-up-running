from src.utils import connect_to_api, find_vm_by_id, \
    find_object_by_name, find_datacenter_by_name, compile_folder_path_for_object, get_all_objs, \
    find_vm_by_name, find_cluster_by_name, _get_vm_prop, list_snapshots, get_vnc_extraconfig, \
    find_hostsystem_by_name, find_datastore_by_name, find_folder_by_fqpn, find_folder_by_name, wait_for_task

from pyVmomi import vim, vmodl, VmomiSupport
import os
import re
import json
from distutils.version import StrictVersion


def gather_vm_facts(content, vm):
    """ Gather facts from vim.VirtualMachine object. """
    facts = {
        'module_hw': True,
        'hw_name': vm.config.name,
        'hw_power_status': vm.summary.runtime.powerState,
        'hw_guest_full_name': vm.summary.guest.guestFullName,
        'hw_guest_id': vm.summary.guest.guestId,
        'hw_product_uuid': vm.config.uuid,
        'hw_processor_count': vm.config.hardware.numCPU,
        'hw_cores_per_socket': vm.config.hardware.numCoresPerSocket,
        'hw_memtotal_mb': vm.config.hardware.memoryMB,
        'hw_interfaces': [],
        'hw_datastores': [],
        'hw_files': [],
        'hw_esxi_host': None,
        'hw_guest_ha_state': None,
        'hw_is_template': vm.config.template,
        'hw_folder': None,
        'hw_version': vm.config.version,
        'instance_uuid': vm.config.instanceUuid,
        'guest_tools_status': _get_vm_prop(vm, ('guest', 'toolsRunningStatus')),
        'guest_tools_version': _get_vm_prop(vm, ('guest', 'toolsVersion')),
        'guest_question': json.loads(json.dumps(vm.summary.runtime.question, cls=VmomiSupport.VmomiJSONEncoder,
                                                sort_keys=True, strip_dynamic=True)),
        'guest_consolidation_needed': vm.summary.runtime.consolidationNeeded,
        'ipv4': None,
        'ipv6': None,
        'annotation': vm.config.annotation,
        'customvalues': {},
        'snapshots': [],
        'current_snapshot': None,
        'vnc': {},
        'moid': vm._moId,
        'vimref': "vim.VirtualMachine:%s" % vm._moId,
        'advanced_settings': {},
    }

    # facts that may or may not exist
    if vm.summary.runtime.host:
        try:
            host = vm.summary.runtime.host
            facts['hw_esxi_host'] = host.summary.config.name
            facts['hw_cluster'] = host.parent.name if host.parent and isinstance(host.parent,
                                                                                 vim.ClusterComputeResource) else None

        except vim.fault.NoPermission:
            # User does not have read permission for the host system,
            # proceed without this value. This value does not contribute or hamper
            # provisioning or power management operations.
            pass
    if vm.summary.runtime.dasVmProtection:
        facts['hw_guest_ha_state'] = vm.summary.runtime.dasVmProtection.dasProtected

    datastores = vm.datastore
    for ds in datastores:
        facts['hw_datastores'].append(ds.info.name)

    try:
        files = vm.config.files
        layout = vm.layout
        if files:
            facts['hw_files'] = [files.vmPathName]
            for item in layout.snapshot:
                for snap in item.snapshotFile:
                    if 'vmsn' in snap:
                        facts['hw_files'].append(snap)
            for item in layout.configFile:
                facts['hw_files'].append(os.path.join(os.path.dirname(files.vmPathName), item))
            for item in vm.layout.logFile:
                facts['hw_files'].append(os.path.join(files.logDirectory, item))
            for item in vm.layout.disk:
                for disk in item.diskFile:
                    facts['hw_files'].append(disk)
    except Exception:
        pass

    facts['hw_folder'] = PyVmomi.get_vm_path(content, vm)

    cfm = content.customFieldsManager
    # Resolve custom values
    for value_obj in vm.summary.customValue:
        kn = value_obj.key
        if cfm is not None and cfm.field:
            for f in cfm.field:
                if f.key == value_obj.key:
                    kn = f.name
                    # Exit the loop immediately, we found it
                    break

        facts['customvalues'][kn] = value_obj.value

    # Resolve advanced settings
    for advanced_setting in vm.config.extraConfig:
        facts['advanced_settings'][advanced_setting.key] = advanced_setting.value

    net_dict = {}
    vmnet = _get_vm_prop(vm, ('guest', 'net'))
    if vmnet:
        for device in vmnet:
            if device.deviceConfigId > 0:
                net_dict[device.macAddress] = list(device.ipAddress)

    if vm.guest.ipAddress:
        if ':' in vm.guest.ipAddress:
            facts['ipv6'] = vm.guest.ipAddress
        else:
            facts['ipv4'] = vm.guest.ipAddress

    ethernet_idx = 0
    for entry in vm.config.hardware.device:
        if not hasattr(entry, 'macAddress'):
            continue

        if entry.macAddress:
            mac_addr = entry.macAddress
            mac_addr_dash = mac_addr.replace(':', '-')
        else:
            mac_addr = mac_addr_dash = None

        if (
                hasattr(entry, "backing")
                and hasattr(entry.backing, "port")
                and hasattr(entry.backing.port, "portKey")
                and hasattr(entry.backing.port, "portgroupKey")
        ):
            port_group_key = entry.backing.port.portgroupKey
            port_key = entry.backing.port.portKey
        else:
            port_group_key = None
            port_key = None

        factname = 'hw_eth' + str(ethernet_idx)
        facts[factname] = {
            'addresstype': entry.addressType,
            'label': entry.deviceInfo.label,
            'macaddress': mac_addr,
            'ipaddresses': net_dict.get(entry.macAddress, None),
            'macaddress_dash': mac_addr_dash,
            'summary': entry.deviceInfo.summary,
            'portgroup_portkey': port_key,
            'portgroup_key': port_group_key,
        }
        facts['hw_interfaces'].append('eth' + str(ethernet_idx))
        ethernet_idx += 1

    snapshot_facts = list_snapshots(vm)
    if 'snapshots' in snapshot_facts:
        facts['snapshots'] = snapshot_facts['snapshots']
        facts['current_snapshot'] = snapshot_facts['current_snapshot']

    facts['vnc'] = get_vnc_extraconfig(vm)

    # Gather vTPM information
    facts['tpm_info'] = {
        'tpm_present': vm.summary.config.tpmPresent if hasattr(vm.summary.config, 'tpmPresent') else None,
        'provider_id': vm.config.keyId.providerId.id if vm.config.keyId else None
    }
    return facts


class PyVmomi(object):
    def __init__(self, module):
        """
        Constructor
        """

        self.module = module
        self.params = module.params
        self.current_vm_obj = None
        self.si, self.content = connect_to_api(self.module, return_si=True)
        self.custom_field_mgr = []
        if self.content.customFieldsManager:  # not an ESXi
            self.custom_field_mgr = self.content.customFieldsManager.field

    def is_vcenter(self):
        """
        Check if given hostname is vCenter or ESXi host
        Returns: True if given connection is with vCenter server
                 False if given connection is with ESXi server
        """
        api_type = None
        try:
            api_type = self.content.about.apiType
        except (vmodl.RuntimeFault, vim.fault.VimFault) as exc:
            self.module.fail_json(msg="Failed to get status of vCenter server : %s" % exc.msg)

        if api_type == 'VirtualCenter':
            return True
        elif api_type == 'HostAgent':
            return False

    def get_managed_objects_properties(self, vim_type, properties=None):
        """
        Look up a Managed Object Reference in vCenter / ESXi Environment
        :param vim_type: Type of vim object e.g, for datacenter - vim.Datacenter
        :param properties: List of properties related to vim object e.g. Name
        :return: local content object
        """
        # Get Root Folder
        root_folder = self.content.rootFolder

        if properties is None:
            properties = ['name']

        # Create Container View with default root folder
        mor = self.content.viewManager.CreateContainerView(root_folder, [vim_type], True)

        # Create Traversal spec
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name="traversal_spec",
            path='view',
            skip=False,
            type=vim.view.ContainerView
        )

        # Create Property Spec
        property_spec = vmodl.query.PropertyCollector.PropertySpec(
            type=vim_type,  # Type of object to retrieved
            all=False,
            pathSet=properties
        )

        # Create Object Spec
        object_spec = vmodl.query.PropertyCollector.ObjectSpec(
            obj=mor,
            skip=True,
            selectSet=[traversal_spec]
        )

        # Create Filter Spec
        filter_spec = vmodl.query.PropertyCollector.FilterSpec(
            objectSet=[object_spec],
            propSet=[property_spec],
            reportMissingObjectsInResults=False
        )

        return self.content.propertyCollector.RetrieveContents([filter_spec])

    # Virtual Machine related functions
    def get_vm(self):
        """
        Find unique virtual machine either by UUID, MoID or Name.
        Returns: virtual machine object if found, else None.
        """
        vm_obj = None
        user_desired_path = None
        use_instance_uuid = self.params.get('use_instance_uuid') or False
        if 'uuid' in self.params and self.params['uuid']:
            if not use_instance_uuid:
                vm_obj = find_vm_by_id(self.content, vm_id=self.params['uuid'], vm_id_type="uuid")
            elif use_instance_uuid:
                vm_obj = find_vm_by_id(self.content,
                                       vm_id=self.params['uuid'],
                                       vm_id_type="instance_uuid")
        elif 'name' in self.params and self.params['name']:
            objects = self.get_managed_objects_properties(vim_type=vim.VirtualMachine, properties=['name'])
            vms = []

            for temp_vm_object in objects:
                if (
                        len(temp_vm_object.propSet) == 1
                        and unquote(temp_vm_object.propSet[0].val) == self.params["name"]
                ):
                    vms.append(temp_vm_object.obj)

            # get_managed_objects_properties may return multiple virtual machine,
            # following code tries to find user desired one depending upon the folder specified.
            if len(vms) > 1:
                # We have found multiple virtual machines, decide depending upon folder value
                if self.params['folder'] is None:
                    self.module.fail_json(msg="Multiple virtual machines with same name [%s] found, "
                                              "Folder value is a required parameter to find uniqueness "
                                              "of the virtual machine" % self.params['name'],
                                          details="Please see documentation of the vmware_guest module "
                                                  "for folder parameter.")

                # Get folder path where virtual machine is located
                # User provided folder where user thinks virtual machine is present
                user_folder = self.params['folder']
                # User defined datacenter
                user_defined_dc = self.params['datacenter']
                # User defined datacenter's object
                datacenter_obj = find_datacenter_by_name(self.content, self.params['datacenter'])
                # Get Path for Datacenter
                dcpath = compile_folder_path_for_object(vobj=datacenter_obj)

                # Nested folder does not return trailing /
                if not dcpath.endswith('/'):
                    dcpath += '/'

                if user_folder in [None, '', '/']:
                    # User provided blank value or
                    # User provided only root value, we fail
                    self.module.fail_json(msg="vmware_guest found multiple virtual machines with same "
                                              "name [%s], please specify folder path other than blank "
                                              "or '/'" % self.params['name'])
                elif user_folder.startswith('/vm/'):
                    # User provided nested folder under VMware default vm folder i.e. folder = /vm/india/finance
                    user_desired_path = "%s%s%s" % (dcpath, user_defined_dc, user_folder)
                else:
                    # User defined datacenter is not nested i.e. dcpath = '/' , or
                    # User defined datacenter is nested i.e. dcpath = '/F0/DC0' or
                    # User provided folder starts with / and datacenter i.e. folder = /ha-datacenter/ or
                    # User defined folder starts with datacenter without '/' i.e.
                    # folder = DC0/vm/india/finance or
                    # folder = DC0/vm
                    user_desired_path = user_folder

                for vm in vms:
                    # Check if user has provided same path as virtual machine
                    actual_vm_folder_path = self.get_vm_path(content=self.content, vm_name=vm)
                    if not actual_vm_folder_path.startswith("%s%s" % (dcpath, user_defined_dc)):
                        continue
                    if user_desired_path in actual_vm_folder_path:
                        vm_obj = vm
                        break
            elif vms:
                # Unique virtual machine found.
                actual_vm_folder_path = self.get_vm_path(content=self.content, vm_name=vms[0])
                if self.params.get('folder') is None:
                    vm_obj = vms[0]
                elif self.params['folder'] in actual_vm_folder_path:
                    vm_obj = vms[0]
        elif 'moid' in self.params and self.params['moid']:
            vm_obj = VmomiSupport.templateOf('VirtualMachine')(self.params['moid'], self.si._stub)
            try:
                getattr(vm_obj, 'name')
            except vmodl.fault.ManagedObjectNotFound:
                vm_obj = None

        if vm_obj:
            self.current_vm_obj = vm_obj

        return vm_obj

    def gather_facts(self, vm):
        """
        Gather facts of virtual machine.
        Args:
            vm: Name of virtual machine.
        Returns: Facts dictionary of the given virtual machine.
        """
        return gather_vm_facts(self.content, vm)

    @staticmethod
    def get_vm_path(content, vm_name):
        """
        Find the path of virtual machine.
        Args:
            content: VMware content object
            vm_name: virtual machine managed object
        Returns: Folder of virtual machine if exists, else None
        """
        folder_name = None
        folder = vm_name.parent
        if folder:
            folder_name = folder.name
            fp = folder.parent
            # climb back up the tree to find our path, stop before the root folder
            while fp is not None and fp.name is not None and fp != content.rootFolder:
                folder_name = fp.name + '/' + folder_name
                try:
                    fp = fp.parent
                except Exception:
                    break
            folder_name = '/' + folder_name
        return folder_name

    def get_vm_or_template(self, template_name=None):
        """
        Find the virtual machine or virtual machine template using name
        used for cloning purpose.
        Args:
            template_name: Name of virtual machine or virtual machine template
        Returns: virtual machine or virtual machine template object
        """
        template_obj = None
        if not template_name:
            return template_obj

        if "/" in template_name:
            vm_obj_path = os.path.dirname(template_name)
            vm_obj_name = os.path.basename(template_name)
            template_obj = find_vm_by_id(self.content, vm_obj_name, vm_id_type="inventory_path", folder=vm_obj_path)
            if template_obj:
                return template_obj
        else:
            template_obj = find_vm_by_id(self.content, vm_id=template_name, vm_id_type="uuid")
            if template_obj:
                return template_obj

            objects = self.get_managed_objects_properties(vim_type=vim.VirtualMachine, properties=['name'])
            templates = []

            for temp_vm_object in objects:
                if len(temp_vm_object.propSet) != 1:
                    continue
                for temp_vm_object_property in temp_vm_object.propSet:
                    if temp_vm_object_property.val == template_name:
                        templates.append(temp_vm_object.obj)
                        break

            if len(templates) > 1:
                # We have found multiple virtual machine templates
                self.module.fail_json(
                    msg="Multiple virtual machines or templates with same name [%s] found." % template_name)
            elif templates:
                template_obj = templates[0]

        return template_obj

    # Cluster related functions
    def find_cluster_by_name(self, cluster_name, datacenter_name=None):
        """
        Find Cluster by name in given datacenter
        Args:
            cluster_name: Name of cluster name to find
            datacenter_name: (optional) Name of datacenter
        Returns: True if found
        """
        return find_cluster_by_name(self.content, cluster_name, datacenter=datacenter_name)

    def get_all_hosts_by_cluster(self, cluster_name):
        """
        Get all hosts from cluster by cluster name
        Args:
            cluster_name: Name of cluster
        Returns: List of hosts
        """
        cluster_obj = self.find_cluster_by_name(cluster_name=cluster_name)
        if cluster_obj:
            return list(cluster_obj.host)
        else:
            return []

    # Hosts related functions
    def find_hostsystem_by_name(self, host_name, datacenter=None):
        """
        Find Host by name
        Args:
            host_name: Name of ESXi host
            datacenter: (optional) Datacenter of ESXi resides
        Returns: True if found
        """
        return find_hostsystem_by_name(self.content, hostname=host_name, datacenter=datacenter)

    def get_all_host_objs(self, cluster_name=None, esxi_host_name=None):
        """
        Get all host system managed object
        Args:
            cluster_name: Name of Cluster
            esxi_host_name: Name of ESXi server
        Returns: A list of all host system managed objects, else empty list
        """
        host_obj_list = []
        if not self.is_vcenter():
            hosts = get_all_objs(self.content, [vim.HostSystem]).keys()
            if hosts:
                host_obj_list.append(list(hosts)[0])
        else:
            if cluster_name:
                cluster_obj = self.find_cluster_by_name(cluster_name=cluster_name)
                if cluster_obj:
                    host_obj_list = list(cluster_obj.host)
                else:
                    self.module.fail_json(changed=False, msg="Cluster '%s' not found" % cluster_name)
            elif esxi_host_name:
                if isinstance(esxi_host_name, str):
                    esxi_host_name = [esxi_host_name]

                for host in esxi_host_name:
                    esxi_host_obj = self.find_hostsystem_by_name(host_name=host)
                    if esxi_host_obj:
                        host_obj_list.append(esxi_host_obj)
                    else:
                        self.module.fail_json(changed=False, msg="ESXi '%s' not found" % host)

        return host_obj_list

    def host_version_at_least(self, version=None, vm_obj=None, host_name=None):
        """
        Check that the ESXi Host is at least a specific version number
        Args:
            vm_obj: virtual machine object, required one of vm_obj, host_name
            host_name (string): ESXi host name
            version (tuple): a version tuple, for example (6, 7, 0)
        Returns: bool
        """
        if vm_obj:
            host_system = vm_obj.summary.runtime.host
        elif host_name:
            host_system = self.find_hostsystem_by_name(host_name=host_name)
        else:
            self.module.fail_json(msg='VM object or ESXi host name must be set one.')
        if host_system and version:
            host_version = host_system.summary.config.product.version
            return StrictVersion(host_version) >= StrictVersion('.'.join(map(str, version)))
        else:
            self.module.fail_json(msg='Unable to get the ESXi host from vm: %s, or hostname %s,'
                                      'or the passed ESXi version: %s is None.' % (vm_obj, host_name, version))

    # Network related functions
    @staticmethod
    def find_host_portgroup_by_name(host, portgroup_name):
        """
        Find Portgroup on given host
        Args:
            host: Host config object
            portgroup_name: Name of portgroup
        Returns: True if found else False
        """
        for portgroup in host.config.network.portgroup:
            if portgroup.spec.name == portgroup_name:
                return portgroup
        return False

    def get_all_port_groups_by_host(self, host_system):
        """
        Get all Port Group by host
        Args:
            host_system: Name of Host System
        Returns: List of Port Group Spec
        """
        pgs_list = []
        for pg in host_system.config.network.portgroup:
            pgs_list.append(pg)
        return pgs_list

    def find_network_by_name(self, network_name=None):
        """
        Get network specified by name
        Args:
            network_name: Name of network
        Returns: List of network managed objects
        """
        networks = []

        if not network_name:
            return networks

        objects = self.get_managed_objects_properties(vim_type=vim.Network, properties=['name'])

        for temp_vm_object in objects:
            if len(temp_vm_object.propSet) != 1:
                continue
            for temp_vm_object_property in temp_vm_object.propSet:
                if temp_vm_object_property.val == network_name:
                    networks.append(temp_vm_object.obj)
                    break
        return networks

    def network_exists_by_name(self, network_name=None):
        """
        Check if network with a specified name exists or not
        Args:
            network_name: Name of network
        Returns: True if network exists else False
        """
        ret = False
        if not network_name:
            return ret
        ret = True if self.find_network_by_name(network_name=network_name) else False
        return ret

    # Datacenter
    def find_datacenter_by_name(self, datacenter_name):
        """
        Get datacenter managed object by name
        Args:
            datacenter_name: Name of datacenter
        Returns: datacenter managed object if found else None
        """
        return find_datacenter_by_name(self.content, datacenter_name=datacenter_name)

    def is_datastore_valid(self, datastore_obj=None):
        """
        Check if datastore selected is valid or not
        Args:
            datastore_obj: datastore managed object
        Returns: True if datastore is valid, False if not
        """
        if not datastore_obj \
                or datastore_obj.summary.maintenanceMode != 'normal' \
                or not datastore_obj.summary.accessible:
            return False
        return True

    def find_datastore_by_name(self, datastore_name, datacenter_name=None):
        """
        Get datastore managed object by name
        Args:
            datastore_name: Name of datastore
            datacenter_name: Name of datacenter where the datastore resides.  This is needed because Datastores can be
            shared across Datacenters, so we need to specify the datacenter to assure we get the correct Managed Object Reference
        Returns: datastore managed object if found else None
        """
        return find_datastore_by_name(self.content, datastore_name=datastore_name, datacenter_name=datacenter_name)

    def find_folder_by_name(self, folder_name):
        """
        Get vm folder managed object by name
        Args:
            folder_name: Name of the vm folder
        Returns: vm folder managed object if found else None
        """
        return find_folder_by_name(self.content, folder_name=folder_name)

    def find_folder_by_fqpn(self, folder_name, datacenter_name=None, folder_type=None):
        """
        Get a unique folder managed object by specifying its Fully Qualified Path Name
        as datacenter/folder_type/sub1/sub2
        Args:
            folder_name: Fully Qualified Path Name folder name
            datacenter_name: Name of the datacenter, taken from Fully Qualified Path Name if not defined
            folder_type: Type of folder, vm, host, datastore or network,
                         taken from Fully Qualified Path Name if not defined
        Returns: folder managed object if found, else None
        """
        return find_folder_by_fqpn(self.content, folder_name=folder_name, datacenter_name=datacenter_name,
                                   folder_type=folder_type)

    # Datastore cluster
    def find_datastore_cluster_by_name(self, datastore_cluster_name, datacenter=None, folder=None):
        """
        Get datastore cluster managed object by name
        Args:
            datastore_cluster_name: Name of datastore cluster
            datacenter: Managed object of the datacenter
            folder: Managed object of the folder which holds datastore
        Returns: Datastore cluster managed object if found else None
        """
        if datacenter and hasattr(datacenter, 'datastoreFolder'):
            folder = datacenter.datastoreFolder
        if not folder:
            folder = self.content.rootFolder

        data_store_clusters = get_all_objs(self.content, [vim.StoragePod], folder=folder)
        for dsc in data_store_clusters:
            if dsc.name == datastore_cluster_name:
                return dsc
        return None

    def get_recommended_datastore(self, datastore_cluster_obj=None):
        """
        Return Storage DRS recommended datastore from datastore cluster
        Args:
            datastore_cluster_obj: datastore cluster managed object
        Returns: Name of recommended datastore from the given datastore cluster
        """
        if datastore_cluster_obj is None:
            return None
        # Check if Datastore Cluster provided by user is SDRS ready
        sdrs_status = datastore_cluster_obj.podStorageDrsEntry.storageDrsConfig.podConfig.enabled
        if sdrs_status:
            # We can get storage recommendation only if SDRS is enabled on given datastorage cluster
            pod_sel_spec = vim.storageDrs.PodSelectionSpec()
            pod_sel_spec.storagePod = datastore_cluster_obj
            storage_spec = vim.storageDrs.StoragePlacementSpec()
            storage_spec.podSelectionSpec = pod_sel_spec
            storage_spec.type = 'create'

            try:
                rec = self.content.storageResourceManager.RecommendDatastores(storageSpec=storage_spec)
                rec_action = rec.recommendations[0].action[0]
                return rec_action.destination.name
            except Exception:
                # There is some error so we fall back to general workflow
                pass
        datastore = None
        datastore_freespace = 0
        for ds in datastore_cluster_obj.childEntity:
            if isinstance(ds, vim.Datastore) and ds.summary.freeSpace > datastore_freespace:
                # If datastore field is provided, filter destination datastores
                if not self.is_datastore_valid(datastore_obj=ds):
                    continue

                datastore = ds
                datastore_freespace = ds.summary.freeSpace
        if datastore:
            return datastore.name
        return None

    # Resource pool
    def find_resource_pool_by_name(self, resource_pool_name='Resources', folder=None):
        """
        Get resource pool managed object by name
        Args:
            resource_pool_name: Name of resource pool
        Returns: Resource pool managed object if found else None
        """
        if not folder:
            folder = self.content.rootFolder

        resource_pools = get_all_objs(self.content, [vim.ResourcePool], folder=folder)
        for rp in resource_pools:
            if rp.name == resource_pool_name:
                return rp
        return None

    def find_resource_pool_by_cluster(self, resource_pool_name='Resources', cluster=None):
        """
        Get resource pool managed object by cluster object
        Args:
            resource_pool_name: Name of resource pool
            cluster: Managed object of cluster
        Returns: Resource pool managed object if found else None
        """
        desired_rp = None
        if not cluster:
            return desired_rp

        if resource_pool_name != 'Resources':
            # Resource pool name is different than default 'Resources'
            resource_pools = cluster.resourcePool.resourcePool
            if resource_pools:
                for rp in resource_pools:
                    if rp.name == resource_pool_name:
                        desired_rp = rp
                        break
        else:
            desired_rp = cluster.resourcePool

        return desired_rp

    # VMDK stuff
    def vmdk_disk_path_split(self, vmdk_path):
        """
        Takes a string in the format
            [datastore_name] path/to/vm_name.vmdk
        Returns a tuple with multiple strings:
        1. datastore_name: The name of the datastore (without brackets)
        2. vmdk_fullpath: The "path/to/vm_name.vmdk" portion
        3. vmdk_filename: The "vm_name.vmdk" portion of the string (os.path.basename equivalent)
        4. vmdk_folder: The "path/to/" portion of the string (os.path.dirname equivalent)
        """
        try:
            datastore_name = re.match(r'^\[(.*?)\]', vmdk_path, re.DOTALL).groups()[0]
            vmdk_fullpath = re.match(r'\[.*?\] (.*)$', vmdk_path).groups()[0]
            vmdk_filename = os.path.basename(vmdk_fullpath)
            vmdk_folder = os.path.dirname(vmdk_fullpath)
            return datastore_name, vmdk_fullpath, vmdk_filename, vmdk_folder
        except (IndexError, AttributeError) as e:
            self.module.fail_json(msg="Bad path '%s' for filename disk vmdk" % (vmdk_path))

    def find_vmdk_file(self, datastore_obj, vmdk_fullpath, vmdk_filename, vmdk_folder):
        """
        Return vSphere file object or fail_json
        Args:
            datastore_obj: Managed object of datastore
            vmdk_fullpath: Path of VMDK file e.g., path/to/vm/vmdk_filename.vmdk
            vmdk_filename: Name of vmdk e.g., VM0001_1.vmdk
            vmdk_folder: Base dir of VMDK e.g, path/to/vm
        """

        browser = datastore_obj.browser
        datastore_name = datastore_obj.name
        datastore_name_sq = "[" + datastore_name + "]"
        if browser is None:
            self.module.fail_json(msg="Unable to access browser for datastore %s" % datastore_name)

        detail_query = vim.host.DatastoreBrowser.FileInfo.Details(
            fileOwner=True,
            fileSize=True,
            fileType=True,
            modification=True
        )
        search_spec = vim.host.DatastoreBrowser.SearchSpec(
            details=detail_query,
            matchPattern=[vmdk_filename],
            searchCaseInsensitive=True,
        )
        search_res = browser.SearchSubFolders(
            datastorePath=datastore_name_sq,
            searchSpec=search_spec
        )

        changed = False
        vmdk_path = datastore_name_sq + " " + vmdk_fullpath
        try:
            changed, result = wait_for_task(search_res)
        except Exception as task_e:
            pass
            # self.module.fail_json(msg=task_e)

        if not changed:
            self.module.fail_json(msg="No valid disk vmdk image found for path %s" % vmdk_path)

        target_folder_paths = [
            datastore_name_sq + " " + vmdk_folder + '/',
            datastore_name_sq + " " + vmdk_folder,
        ]

        for file_result in search_res.info.result:
            for f in getattr(file_result, 'file'):
                if f.path == vmdk_filename and file_result.folderPath in target_folder_paths:
                    return f

        self.module.fail_json(msg="No vmdk file found for path specified [%s]" % vmdk_path)

    def find_first_class_disk_by_name(self, disk_name, datastore_obj):
        """
        Get first-class disk managed object by name
        Args:
            disk_name: Name of the first-class disk
            datastore_obj: Managed object of datastore
        Returns: First-class disk managed object if found else None
        """

        if self.is_vcenter():
            for id in self.content.vStorageObjectManager.ListVStorageObject(datastore_obj):
                disk = self.content.vStorageObjectManager.RetrieveVStorageObject(id, datastore_obj)
                if disk.config.name == disk_name:
                    return disk
        else:
            for id in self.content.vStorageObjectManager.HostListVStorageObject(datastore_obj):
                disk = self.content.vStorageObjectManager.HostRetrieveVStorageObject(id, datastore_obj)
                if disk.config.name == disk_name:
                    return disk

        return None

    def _extract(self, data, remainder):
        """
        This is used to break down dotted properties for extraction.
        Args:
          - data (dict): result of _jsonify on a property
          - remainder: the remainder of the dotted property to select
        Return:
          dict
        """
        result = dict()
        if '.' not in remainder:
            result[remainder] = data[remainder]
            return result
        key, remainder = remainder.split('.', 1)
        if isinstance(data, list):
            temp_ds = []
            for i in range(len(data)):
                temp_ds.append(self._extract(data[i][key], remainder))
            result[key] = temp_ds
        else:
            result[key] = self._extract(data[key], remainder)
        return result

    def get_folder_path(self, cur):
        full_path = '/' + cur.name
        while hasattr(cur, 'parent') and cur.parent:
            if cur.parent == self.content.rootFolder:
                break
            cur = cur.parent
            full_path = '/' + cur.name + full_path
        return full_path

    def find_obj_by_moid(self, object_type, moid):
        """
        Get Managed Object based on an object type and moid.
        If you'd like to search for a virtual machine, recommended you use get_vm method.
        Args:
          - object_type: Managed Object type
                It is possible to specify types the following.
                ["Datacenter", "ClusterComputeResource", "ResourcePool", "Folder", "HostSystem",
                 "VirtualMachine", "DistributedVirtualSwitch", "DistributedVirtualPortgroup", "Datastore"]
          - moid: moid of Managed Object
        :return: Managed Object if it exists else None
        """

        obj = VmomiSupport.templateOf(object_type)(moid, self.si._stub)
        try:
            getattr(obj, 'name')
        except vmodl.fault.ManagedObjectNotFound:
            obj = None

        return obj
