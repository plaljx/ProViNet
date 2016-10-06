# -*- coding: utf-8 -*-
# ToMaTo (Topology management software) 
# Copyright (C) 2010 Dennis Schwerdel, University of Kaiserslautern
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import os, sys, json, shutil, re
from django.db import models
from .. import connections, elements, resources, fault, config
from ..resources import template
from ..lib.attributes import Attr #@UnresolvedImport
from ..lib import decorators, util, cmd #@UnresolvedImport
from ..lib.cmd import fileserver, process, net, path #@UnresolvedImport
from ..lib.util import joinDicts #@UnresolvedImport

DOC="""
Element type: ``kvmqm``

Description:
	This element type provides full virtualization by using the KVM 
	virtualization technology. The proxmox frontend qm is used to control KVM,
	thus the name kvmqm.

Possible parents: None

Possible children:
	``kvmqm_interface`` (can be added in states *created* and *prepared*)

Default state: *created*

Removable in states: *created*

Connection concepts: None

States:
	*created*: In this state the VM is known of but qm does not know about it.
		No state is stored and no resources are consumed in this state.
	*prepared*: In this state the VM is present in the qm configuration and the
		disk image exists but the VM is not running. The disk image stores some
		state information. The VM is not consuming any resources except for the
		disk image.
	*started*: In this state the VM is running and can be accessed by the user.
		The VM holds a disk state and a memory state. It consumes disk storage
		memory, cpu power, io and networking resources.
		
Attributes:
	*cpus*: int, changeable in states *created* and *prepared*, default: ``1``
		The number of virtual processors that the VM should have. Each virtual
		processor can take the resources of one physical processor.
	*ram*: int, changeable in states *created* and *prepared*, default: ``256``
		The amount of memory the VM should have in megabytes. The virtual
		machine will only be able to access this much virtual memory. RAM that
		has been allocated once will stay allocated as long as the VM is
		running, so in the long run VMs tend to use the maximum amount of RAM.
	*kblang*: str, changeable in states *created* and *prepared*, default: ``de``
		The language of the emulated keyboard. This attribute defines how
		keyboard input is translated in keycodes that are handed over to the
		VM. This setting should correspond to the keyboard setting inside of 
		the VM. 
	*usbtablet*: bool, changeable in states *created* and *prepared*, default: ``True``
		Whether to emulate an USB tablet input device or a normal PS/2 mouse.
		A USB tablet input has the advantage that it uses absolute positions
		to position the mouse pointer instead of relative movements like PS/2
		does. That means that it is easier for viewers to track the mouse 
		position and to avoid offsets. On operating systems that do not support
		USB tablet devices this setting must be disabled, otherwise no mouse 
		will be available. 
	*template*: str, changeable in states *created* and *prepared*
		The name of a template of matching virtualization technology to be used
		for this VM. A copy of this template will be used as an initial disk 
		image when the device is being prepared. When this attribute is changed
		in the state prepared, the disk image will be reset to the template.
		If no template with the given name exists (esp. for template=None),
		a default template is chosen instead.
		WARNING: Setting this attribute for a prepared VM will cause the loss
		of the disk image.   
	*vncport*: int, read-only
		The port on this host on which the VM can be accessed via VNC when it
		is running. 
	*vncpassword*: int, read-only
		The random password that has to be used to connect to this VM using 
		VNC. This password should be kept secret.

Actions:
	*prepare*, callable in state *created*, next state: *prepared*
		Creates a qm configuration entry for this VM and uses a copy of the
		template as disk image.
	*destroy*, callable in state *prepared*, next state: *created*
	 	Removes the qm configuration entry and deletes the disk image.
	*start*, callable in state *prepared*, next state: *started*
	 	Starts the VM and initiates a boot of the contained OS. This action
	 	also starts a VNC server for the VM and connects all the interfaces
	 	of the device.
	*stop*, callable in state *started*, next state: *prepared*
	 	Stops the VNC server, disconnects all the interfaces of the VM and
	 	then initiates an OS shutdown using an ACPI shutdown request. The
	 	contained OS then has 10 seconds to shut down by itself. After this
	 	time, the VM is just stopped.
	 	Note: Users should make sure their VMs shut down properly to decrease
	 	stop time and to avoid data loss or damages in the virtual machine.
	*upload_grant*, callable in state *prepared*
	 	Create/update a grant to upload an image for the VM. The created grant
	 	will be available as an attribute called upload_grant. The grant allows
	 	the user to upload a file for a certain time. The url where the file 
	 	must be uploaded has the form http://server:port/grant/upload where
	 	server is the address of this host, port is the fileserver port of this
	 	server (can be requested via host_info) and grant is the grant.
	 	The uploaded file can be used as the VM image with the upload_use 
	 	action. 
	*rextfv_upload_grant*, callable in state *prepared* 
		same as upload_grant, but for use with rextfv_upload_use.
	*upload_use*, callable in state *prepared*
		Uses a previously uploaded file as the image of the VM. 
	*rextfv_upload_use*, callable in state *prepared*
		Uses a previously uploaded archive to insert into the VM's nlXTP directory.
		Deletes old content from this directory.
	*download_grant*, callable in state *prepared*
	 	Create/update a grant to download the image for the VM. The created 
	 	grant will be available as an attribute called download_grant. The
	 	grant allows the user to download the VM image once for a certain time.
	 	The url where the file can be downloaded from has the form 
	 	http://server:port/grant/download where server is the address of this
	 	host, port is the fileserver port of this server (can be requested via
	 	host_info) and grant is the grant.
	*rextfv_download_grant*, callable in state *prepared* or *started*
		same as download_grant, but only for the nlXTP folder
"""

ST_CREATED = "created"
ST_PREPARED = "prepared"
ST_STARTED = "started"

class KVMQM(elements.RexTFVElement,elements.Element):
	vmid_attr = Attr("vmid", type="int")
	vmid = vmid_attr.attribute()
	websocket_port_attr = Attr("websocket_port", type="int")
	websocket_port = websocket_port_attr.attribute()
	websocket_pid_attr = Attr("websocket_pid", type="int")
	websocket_pid = websocket_pid_attr.attribute()
	vncport_attr = Attr("vncport", type="int")
	vncport = vncport_attr.attribute()
	vncpid_attr = Attr("vncpid", type="int")
	vncpid = vncpid_attr.attribute()
	vncpassword_attr = Attr("vncpassword", type="str")
	vncpassword = vncpassword_attr.attribute()
	cpus_attr = Attr("cpus", desc="Number of CPUs", states=[ST_CREATED, ST_PREPARED], type="int", minValue=1, maxValue=4, faultType=fault.new_user, default=1)
	cpus = cpus_attr.attribute()
	ram_attr = Attr("ram", desc="RAM", unit="MB", states=[ST_CREATED, ST_PREPARED], type="int", minValue=64, maxValue=4096, faultType=fault.new_user, default=256)
	ram = ram_attr.attribute()
	kblang_attr = Attr("kblang", desc="Keyboard language", states=[ST_CREATED, ST_PREPARED], type="str", options={"en-us": "English (US)", "en-gb": "English (GB)", "de": "German", "fr": "French", "ja": "Japanese"}, faultType=fault.new_user, default="en-us")
	#["pt", "tr", "ja", "es", "no", "is", "fr-ca", "fr", "pt-br", "da", "fr-ch", "sl", "de-ch", "en-gb", "it", "en-us", "fr-be", "hu", "pl", "nl", "mk", "fi", "lt", "sv", "de"]
	kblang = kblang_attr.attribute()
	usbtablet_attr = Attr("usbtablet", desc="USB tablet mouse mode", states=[ST_CREATED, ST_PREPARED], type="bool", default=True)
	usbtablet = usbtablet_attr.attribute()
	template_attr = Attr("template", desc="Template", states=[ST_CREATED, ST_PREPARED], type="str", null=True)
	template = models.ForeignKey(template.Template, null=True)
	
	rextfv_max_size = 512000 # depends on _nlxtp_create_device_and_mountpoint.

	TYPE = "kvmqm"
	CAP_ACTIONS = {
		"prepare": [ST_CREATED],
		"destroy": [ST_PREPARED],
		"start": [ST_PREPARED],
		"stop": [ST_STARTED],
		"upload_grant": [ST_PREPARED],
		"rextfv_upload_grant": [ST_PREPARED],
		"upload_use": [ST_PREPARED],
		"rextfv_upload_use": [ST_PREPARED],
		"download_grant": [ST_PREPARED],
		"rextfv_download_grant": [ST_PREPARED,ST_STARTED],
		elements.REMOVE_ACTION: [ST_CREATED],
	}
	CAP_NEXT_STATE = {
		"prepare": ST_PREPARED,
		"destroy": ST_CREATED,
		"start": ST_STARTED,
		"stop": ST_PREPARED,
	}
	CAP_ATTRS = {
		"cpus": cpus_attr,
		"ram": ram_attr,
		"kblang": kblang_attr,
		"usbtablet": usbtablet_attr,
		"template": template_attr,
		"timeout": elements.Element.timeout_attr
	}
	CAP_CHILDREN = {
		"kvmqm_interface": [ST_CREATED, ST_PREPARED],
	}
	CAP_PARENT = [None]
	DEFAULT_ATTRS = {"cpus": 1, "ram": 256, "kblang": "de", "usbtablet": True}
	__doc__ = DOC #@ReservedAssignment
	DOC = DOC
	
	class Meta:
		db_table = "tomato_kvmqm"
		app_label = 'tomato'
	
	def init(self, *args, **kwargs):
		self.type = self.TYPE
		self.state = ST_CREATED
		elements.Element.init(self, *args, **kwargs) #no id and no attrs before this line
		self.vmid = self.getResource("vmid")
		self.vncport = self.getResource("port")
		self.websocket_port = self.getResource("port", config.WEBSOCKIFY_PORT_BLACKLIST)
		self.vncpassword = cmd.randomPassword()
		#template: None, default template
				
	def _controlPath(self):
		return "/var/run/qemu-server/%d.qmp" % self.vmid
				
	def _vncPath(self):
		return "/var/run/qemu-server/%d.vnc" % self.vmid

	def _imagePathDir(self):
		return "/var/lib/vz/images/%d" % self.vmid

	def _imagePath(self, file="disk.qcow2"): #@ReservedAssignment
		return os.path.join(self._imagePathDir(), file)

	def _interfaceName(self, num):
		if qmVersion == [1, 1, 22]:
			return "vmtab%di%d" % (self.vmid, num)
		if qmVersion == [1, 1, 25]:
			return "vmtab%di%dd0" % (self.vmid, num)
		return "tap%di%d" % (self.vmid, num)

	@decorators.retryOnError(errorFilter=lambda x: isinstance(x, cmd.CommandError) and x.errorCode==4 and "lock" in x.errorMessage and "timeout" in x.errorMessage)
	def _qm(self, cmd_, params=[]):
		return cmd.run(["qm", cmd_, "%d" % self.vmid] + map(str, params))
		#fileutil.delete(host, "/var/lock/qemu-server/lock-%d.conf" % vmid)

	def _getState(self):
		if not self.vmid:
			return ST_CREATED
		try:
			res = self._qm("status")
			if "running" in res:
				return ST_STARTED
			if "stopped" in res:
				return ST_PREPARED
			if "unknown" in res:
				return ST_CREATED
			fault.raise_("Unable to determine kvm state", fault.INTERNAL_ERROR)
		except cmd.CommandError, err:
			if err.errorCode == 2:
				return ST_CREATED
			raise

	def _checkState(self):
		savedState = self.state
		realState = self._getState()
		if savedState != realState:
			self.setState(realState, True)
		fault.check(savedState == realState, "Saved state of %s element #%d was wrong, saved: %s, was: %s", (self.type, self.id, savedState, realState), fault.INTERNAL_ERROR)

	def _control(self, cmds, timeout=60):
		assert self.state == ST_STARTED, "VM must be running"
		controlPath = self._controlPath()
		fault.check(os.path.exists(controlPath), "Control path does not exist")
		cmd_ = "".join([cmd.escape(json.dumps(cmd_))+"'\n'" for cmd_ in cmds])
		return cmd.runShell("echo -e %(cmd)s'\n' | socat -T %(timeout)d - unix-connect:%(monitor)s; socat -T %(timeout)d -u unix-connect:%(monitor)s - 2>&1 | dd count=0 2>/dev/null; echo" % {"cmd": cmd_, "monitor": controlPath, "timeout": timeout})
			
	def _template(self):
		if self.template:
			return self.template.upcast()
		pref = resources.template.getPreferred(self.TYPE)
		fault.check(pref, "Failed to find template for %s", self.TYPE, fault.INTERNAL_ERROR)
		return pref
				
	def _nextIfaceNum(self):
		ifaces = self.getChildren()
		num = 0
		while num in [iface.num for iface in ifaces]:
			num += 1
		return num

	def _addInterface(self, interface):
		assert self.state == ST_PREPARED
		self._qm("set", ["-net%d" % interface.num, "e1000=%s,bridge=dummy" % interface.mac])

	def _removeInterface(self, interface):
		assert self.state == ST_PREPARED
		self._qm("set", ["-delete", "net%d" % interface.num])

	def _setCpus(self):
		assert self.state == ST_PREPARED
		self._qm("set", ["-cores", self.cpus])

	def _setRam(self):
		assert self.state == ST_PREPARED
		self._qm("set", ["-memory", self.ram])

	def _setKblang(self):
		assert self.state == ST_PREPARED
		self._qm("set", ["-keyboard", self.kblang])

	def _setUsbtablet(self):
		assert self.state == ST_PREPARED
		self._qm("set", ["-tablet", int(self.usbtablet)])

	def _useImage(self, path_):
		assert self.state == ST_PREPARED
		path.copy(path_, self._imagePath())

	def _checkImage(self, path):
		err, _ = cmd.runUnchecked(["qemu-img", "info", "-f", "qcow2", path])
		fault.check(err==0, "File is not a valid qcow2 image")

	def onChildAdded(self, interface):
		self._checkState()
		if self.state == ST_PREPARED:
			self._addInterface(interface)
		interface.setState(self.state)

	def onChildRemoved(self, interface):
		self._checkState()
		if self.state == ST_PREPARED:
			self._removeInterface(interface)
		interface.setState(self.state)

	def modify_cpus(self, cpus):
		self._checkState()
		self.cpus = cpus
		if self.state == ST_PREPARED:
			self._setCpus()

	def modify_ram(self, ram):
		self._checkState()
		self.ram = ram
		if self.state == ST_PREPARED:
			self._setRam()
		
	def modify_kblang(self, kblang):
		self._checkState()
		self.kblang = kblang
		if self.state == ST_PREPARED:
			self._setKblang()
		
	def modify_usbtablet(self, usbtablet):
		self._checkState()
		self.usbtablet = usbtablet
		if self.state == ST_PREPARED:
			self._setUsbtablet()
		
	def modify_template(self, tmplName):
		self._checkState()
		self.template = resources.template.get(self.TYPE, tmplName)
		if self.state == ST_PREPARED:
			self._useImage(self._template().getPath())

	def action_prepare(self):
		self._checkState()
		self._qm("create")
		self._qm("set", ["-boot", "cd"]) #boot priorities: disk, cdrom (no networking)
		args = "-vnc unix:%s,password -fda %s" % (self._vncPath(),self._nlxtp_device_filename()) #disable vnc tls as most clients dont support that; add nlxtp device
		if qmVersion < [1, 1]:
			args += " -chardev socket,id=qmp,path=%s,server,nowait -mon chardev=qmp,mode=control" % self._controlPath()
		self._qm("set", ["-args", args])  
		self.setState(ST_PREPARED, True)
		self._setCpus()
		self._setRam()
		self._setKblang()
		self._setUsbtablet()
		# add all interfaces
		for interface in self.getChildren():
			self._addInterface(interface)
		# use template
		if not os.path.exists(self._imagePathDir()):
			os.mkdir(self._imagePathDir())
		self._useImage(self._template().getPath())
		self._qm("set", ["-ide0", "local:%d/disk.qcow2" % self.vmid])
		
	def action_destroy(self):
		self._checkState()
		self._qm("destroy")
		self.setState(ST_CREATED, True)

	def action_start(self):
		self._checkState()
		if not net.bridgeExists("dummy"):
			net.bridgeCreate("dummy")
		net.ifUp("dummy")
		self._qm("start")
		self.setState(ST_STARTED, True)
		for interface in self.getChildren():
			ifName = self._interfaceName(interface.num)
			fault.check(util.waitFor(lambda :net.ifaceExists(ifName)), "Interface did not start properly: %s", ifName, fault.INTERNAL_ERROR) 
			con = interface.getConnection()
			if con:
				con.connectInterface(self._interfaceName(interface.num))
			interface._start()
		fault.check(util.waitFor(lambda :os.path.exists(self._controlPath())), "Control path does not exist")
		self._control([{'execute': 'qmp_capabilities'}, {'execute': 'set_password', 'arguments': {"protocol": "vnc", "password": self.vncpassword}}])
		net.freeTcpPort(self.vncport)
		self.vncpid = cmd.spawn(["tcpserver", "-qHRl", "0",  "0", str(self.vncport), "qm", "vncproxy", str(self.vmid)])
		fault.check(util.waitFor(lambda :net.tcpPortUsed(self.vncport)), "VNC server did not start")
		if not self.websocket_port:
			self.websocket_port = self.getResource("port")
		if websockifyVersion:
			net.freeTcpPort(self.websocket_port)
			self.websocket_pid = cmd.spawn(["websockify", "0.0.0.0:%d" % self.websocket_port, "localhost:%d" % self.vncport, '--cert=/etc/tomato/server.pem'])
			fault.check(util.waitFor(lambda :net.tcpPortUsed(self.websocket_port)), "Websocket VNC wrapper did not start")

	def action_stop(self):
		self._checkState()
		for interface in self.getChildren():
			con = interface.getConnection()
			if con:
				con.disconnectInterface(self._interfaceName(interface.num))
			interface._stop()
		if self.vncpid:
			process.kill(self.vncpid)
			del self.vncpid
		if self.websocket_pid:
			process.killTree(self.websocket_pid)
			del self.websocket_pid
		self._qm("shutdown", ["-timeout", 10, "-forceStop"])
		self.setState(ST_PREPARED, True)
		
	def action_upload_grant(self):
		return fileserver.addGrant(self._imagePath("uploaded.qcow2"), fileserver.ACTION_UPLOAD)
	
	def action_rextfv_upload_grant(self):
		return fileserver.addGrant(self.dataPath("rextfv_up.tar.gz"), fileserver.ACTION_UPLOAD)
		
	def action_upload_use(self):
		fault.check(os.path.exists(self._imagePath("uploaded.qcow2")), "No file has been uploaded")
		self._checkImage(self._imagePath("uploaded.qcow2"))
		os.rename(self._imagePath("uploaded.qcow2"), self._imagePath())
		
	def action_rextfv_upload_use(self):
		fault.check(os.path.exists(self.dataPath("rextfv_up.tar.gz")), "No file has been uploaded")
		self._use_rextfv_archive(self.dataPath("rextfv_up.tar.gz"))
		
	def action_download_grant(self):
		shutil.copyfile(self._imagePath(), self._imagePath("download.qcow2"))
		return fileserver.addGrant(self._imagePath("download.qcow2"), fileserver.ACTION_DOWNLOAD, removeFn=fileserver.deleteGrantFile)
	
	def action_rextfv_download_grant(self):
		self._create_rextfv_archive(self.dataPath("rextfv.tar.gz"))
		return fileserver.addGrant(self.dataPath("rextfv.tar.gz"), fileserver.ACTION_DOWNLOAD, removeFn=fileserver.deleteGrantFile)
	
	
	

	#The nlXTP directory
	def _nlxtp_path(self,filename):
		return self.dataPath(os.path.join("nlxtp","mountpoint",filename))
		
	#The nlXTP device
	def _nlxtp_device_filename(self):
		return self.dataPath(os.path.join("nlxtp","device"))
		
		
	def _nlxtp_make_readable(self): #mount device file readonly
		self._nlxtp_create_device_and_mountpoint()
		cmd.run(["mount", "-o", "loop,ro", self._nlxtp_device_filename(), self._nlxtp_path("")])
	
	def _nlxtp_make_writeable(self): #mount device file r/w
		self._nlxtp_create_device_and_mountpoint()
		cmd.run(["mount", "-o", "loop,sync", self._nlxtp_device_filename(), self._nlxtp_path("")])
	
	def _nlxtp_close(self): #unmount device file
		cmd.run(["umount", self._nlxtp_path("")])
		
	def _nlxtp_create_device_and_mountpoint(self): #if device file or mount point do not exist: create
		if not os.path.exists(self._nlxtp_path("")):
			os.makedirs(self._nlxtp_path(""))
		if not os.path.exists(self._nlxtp_device_filename()):
			cmd.run(["mkfs.vfat","-C", self._nlxtp_device_filename(), "524288" ]) # size (last argument) depends on nlxtp_max_size
	
	
		
	def upcast(self):
		return self

	def info(self):
		info = elements.Element.info(self)
		info = joinDicts(info, elements.RexTFVElement.info(self))
		info["attrs"]["template"] = self.template.upcast().name if self.template else None
		return info

	def updateUsage(self, usage, data):
		self._checkState()
		if self.state == ST_CREATED:
			return
		if self.state == ST_STARTED:
			with open("/var/run/qemu-server/%d.pid" % self.vmid) as fp:
				qmPid = int(fp.readline().strip())
			memory = 0
			cputime = 0
			if process.exists(qmPid):
				memory += process.memory(qmPid)
				cputime += process.cputime(qmPid)
			if self.vncpid and process.exists(self.vncpid):
				memory += process.memory(self.vncpid)
				cputime += process.cputime(self.vncpid)
			usage.memory = memory
			usage.updateContinuous("cputime", cputime, data)
		usage.diskspace = path.diskspace(self._imagePathDir())
		
KVMQM.__doc__ = DOC


DOC_IFACE="""
Element type: ``kvmqm_interface``

Description:
	This element type represents a network interface of kvmqm element type. Its
	state is managed by and synchronized with the parent element.

Possible parents: ``kvmqm``

Possible children: None

Default state: *created*

Removable in states: *created* and *prepared* 
	
Connection concepts: *interface*

States:
	*created*: In this state the interface is known of but qm does not know about
		it.
	*prepared*: In this state the interface is present in the qm configuration
		but not running.
	*started*: In this state the interface is running.
        
Attributes: None

Actions: None
"""

class KVMQM_Interface(elements.Element):
	num_attr = Attr("num", type="int")
	num = num_attr.attribute()
	name_attr = Attr("name", desc="Name", type="str", regExp="^eth[0-9]+$", states=[ST_CREATED])
	mac_attr = Attr("mac", desc="MAC Address", type="str")
	mac = mac_attr.attribute()
	ipspy_pid_attr = Attr("ipspy_pid", type="int")
	ipspy_pid = ipspy_pid_attr.attribute()
	used_addresses_attr = Attr("used_addresses", type=list, default=[])
	used_addresses = used_addresses_attr.attribute()
	
	TYPE = "kvmqm_interface"
	CAP_ACTIONS = {
		elements.REMOVE_ACTION: [ST_CREATED, ST_PREPARED]
	}
	CAP_NEXT_STATE = {}
	CAP_ATTRS = {
		"name": name_attr,				
		"timeout": elements.Element.timeout_attr
	}
	CAP_CHILDREN = {}
	CAP_PARENT = [KVMQM.TYPE]
	CAP_CON_CONCEPTS = [connections.CONCEPT_INTERFACE]
	DOC = DOC_IFACE
	__doc__ = DOC_IFACE #@ReservedAssignment
	
	class Meta:
		db_table = "tomato_kvm_interface"
		app_label = 'tomato'
	
	def init(self, *args, **kwargs):
		self.type = self.TYPE
		self.state = ST_CREATED
		elements.Element.init(self, *args, **kwargs) #no id and no attrs before this line
		assert isinstance(self.getParent(), KVMQM)
		self.num = self.getParent()._nextIfaceNum()
		self.mac = net.randomMac()

	def modify_name(self, val):
		self.num = int(re.match("^eth([0-9]+)$", val).groups()[0])
			
	def interfaceName(self):
		if self.state != ST_CREATED:
			return self.getParent()._interfaceName(self.num)
		else:
			return None
		
	def upcast(self):
		return self

	def _start(self):
		self.ipspy_pid = net.ipspy_start(self.interfaceName(), self.dataPath("ipspy.json"))
		self.save()
	
	def _stop(self):
		if self.ipspy_pid:
			process.kill(self.ipspy_pid)
			del self.ipspy_pid
		self.save()

	def info(self):
		if self.state == ST_STARTED:
			self.used_addresses = net.ipspy_read(self.dataPath("ipspy.json"))
		else:
			self.used_addresses = []
		info = elements.Element.info(self)
		info["attrs"]["name"] = "eth%d" % self.num
		return info

	def updateUsage(self, usage, data):
		ifname = self.interfaceName()
		if net.ifaceExists(ifname):
			traffic = sum(net.trafficInfo(ifname))
			usage.updateContinuous("traffic", traffic, data)
			
KVMQM_Interface.__doc__ = DOC_IFACE

def register(): #pragma: no cover
	if not os.path.exists("/dev/kvm"):
		print >>sys.stderr, "Warning: KVMQM needs /dev/kvm, disabled"
		return
	if not qmVersion:
		print >>sys.stderr, "Warning: KVMQM needs a Proxmox VE host, disabled"
		return
	if not ([1, 4] <= qmVersion < [1, 8]):
		print >>sys.stderr, "Warning: KVMQM not supported on pve-qemu-kvm version %s, disabled" % qmVersion
		return
	if not socatVersion:
		print >>sys.stderr, "Warning: KVMQM needs socat, disabled"
		return
	if not tcpserverVersion:
		print >>sys.stderr, "Warning: KVMQM needs ucspi-tcp, disabled"
		return
	if not dosfstoolsVersion:
		print >>sys.stderr, "Warning: KVMQM needs dosfstools, disabled"
		return
	if not ipspyVersion:
		print >>sys.stderr, "Warning: ipspy not available"
	elements.TYPES[KVMQM.TYPE] = KVMQM
	elements.TYPES[KVMQM_Interface.TYPE] = KVMQM_Interface

if not config.MAINTENANCE:
	tcpserverVersion = cmd.getDpkgVersion("ucspi-tcp")
	websockifyVersion = cmd.getDpkgVersion("websockify")
	socatVersion = cmd.getDpkgVersion("socat")
	qmVersion = cmd.getDpkgVersion("pve-qemu-kvm")
	dosfstoolsVersion = cmd.getDpkgVersion("dosfstools")
	ipspyVersion = cmd.getDpkgVersion("ipspy")
	register()
