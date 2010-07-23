# -*- coding: utf-8 -*-

from xml.dom import minidom

from openvz_device import *
from dhcpd_device import *
from tinc_connector import *
from real_network_connector import *
from config import *
from resource_store import *

import shutil, os, stat

class Topology(XmlObject):
  
	def __init__ (self, file, load_ids):
		self.devices={}
		self.connectors={}
		self.load_from(file, load_ids)
		
	id=property(curry(XmlObject.get_attr, "id"), curry(XmlObject.set_attr, "id"))
	state=property(curry(XmlObject.get_attr, "state"), curry(XmlObject.set_attr, "state"))
	
	def add_device ( self, device ):
		device.topology = self
		self.devices[device.id] = device
		
	def add_connector ( self, connector ):
		connector.topology = self
		self.connectors[connector.id] = connector
		
	def load_from ( self, file, load_ids ):
		dom = minidom.parse ( file )
		x_top = dom.getElementsByTagName ( "topology" )[0]
		if not load_ids:
			if x_top.hasAttribute("id"):
				x_top.removeAttribute("id")
			if x_top.hasAttribute("state"):
				x_top.removeAttribute("state")
		XmlObject.decode_xml(self,x_top)
		for x_dev in x_top.getElementsByTagName ( "device" ):
			Type = { "openvz": OpenVZDevice, "dhcpd": DhcpdDevice }[x_dev.getAttribute("type")]
			self.add_device ( Type ( self, x_dev, load_ids ) )
		for x_con in x_top.getElementsByTagName ( "connector" ):
			Type = { "hub": TincConnector, "switch": TincConnector, "router": TincConnector, "real": RealNetworkConnector }[x_con.getAttribute("type")]
			self.add_connector ( Type ( self, x_con, load_ids ) )
			
	def create_dom ( self, print_ids ):
		dom = minidom.Document()
		x_top = dom.createElement ( "topology" )
		XmlObject.encode_xml(self,x_top)
		if not print_ids:
			if x_top.hasAttribute("id"):
				x_top.removeAttribute("id")
			if x_top.hasAttribute("state"):
				x_top.removeAttribute("state")
		dom.appendChild ( x_top )
		for dev in self.devices.values():
			x_dev = dom.createElement ( "device" )
			dev.encode_xml ( x_dev, dom, print_ids )
			x_top.appendChild ( x_dev )
		for con in self.connectors.values():
			x_con = dom.createElement ( "connector" )
			con.encode_xml ( x_con, dom, print_ids )
			x_top.appendChild ( x_con )
		return dom

	def save_to (self, file, print_ids):
		dom = self.create_dom(print_ids)
		fd = open ( file, "w" )
		dom.writexml(fd, indent="", addindent="\t", newl="\n")
		fd.close()

	def output (self):
		dom = self.create_dom(False)
		print dom.toprettyxml(indent="\t", newl="\n")

	def retake_resources ( self ):
		for dev in self.devices.values():
			dev.retake_resources()
		for con in self.connectors.values():
			con.retake_resources()

	def take_resources ( self ):
		for dev in self.devices.values():
			dev.take_resources()
		for con in self.connectors.values():
			con.take_resources()

	def free_resources ( self ):
		for dev in self.devices.values():
			dev.free_resources()
		for con in self.connectors.values():
			con.free_resources()

	def affected_hosts (self):
		hosts=set()
		for dev in self.devices.values():
			hosts.add(dev.host)
		return hosts

	def get_deploy_dir(self,host_name):
		return Config.local_deploy_dir+"/"+host_name

	def get_remote_deploy_dir(self):
		return Config.remote_deploy_dir+"/"+str(self.id)

	def get_deploy_script(self,host_name,script):
		return self.get_deploy_dir(host_name)+"/"+script+".sh"

	def deploy(self):
		if not self.id:
			raise Exception("not registered")
		self.take_resources()
		self.write_deploy_scripts()
		self.upload_deploy_scripts()
		if self.state == None:
			self.state = "deployed"
	
	def write_deploy_scripts(self):
		if not self.id:
			raise Exception("not registered")
		print "creating scripts ..."
		if Config.local_deploy_dir and os.path.exists(Config.local_deploy_dir):
			shutil.rmtree(Config.local_deploy_dir)
		for host in self.affected_hosts():
			dir=self.get_deploy_dir(host.name)
			if not os.path.exists(dir):
				os.makedirs(dir)
			for script in ("create", "destroy", "start", "stop"):
				script_fd = open(self.get_deploy_script(host.name,script), "w")
				script_fd.write("#!/bin/bash\ncd %s\n\n" % self.get_remote_deploy_dir())
				script_fd.close()
				os.chmod(self.get_deploy_script(host.name,script), stat.S_IRWXU)
		for dev in self.devices.values():
			dev.write_deploy_script()
		for con in self.connectors.values():
			con.write_deploy_script()

	def upload_deploy_scripts(self):
		if not self.id:
			raise Exception("not registered")
		print "uploading scripts ..."
		for host in self.affected_hosts():
			print "%s ..." % host.name
			src = self.get_deploy_dir(host.name)
			dst = "root@%s:%s" % ( host.name, self.get_remote_deploy_dir() )
			if parse_bool(Config.remote_dry_run):
				print "DRY RUN: ssh root@%s mkdir -p %s/%s" % ( host.name, Config.remote_deploy_dir, self.id )
				print "DRY RUN: ssh root@%s rm -r %s/%s" % ( host.name, Config.remote_deploy_dir, self.id )
				print "DRY RUN: rsync -a %s/ %s" % ( src, dst )
			else:
				subprocess.check_call (["ssh",  "root@%s" % host.name, "mkdir -p %s/%s" % ( Config.remote_deploy_dir, self.id ) ])
				subprocess.check_call (["ssh",  "root@%s" % host.name, "rm -r %s/%s" % ( Config.remote_deploy_dir, self.id ) ])
				subprocess.check_call (["rsync",  "-a",  "%s/" % src, dst])
			print
	
	def exec_script(self, script):
		if not self.id:
			raise Exception("not registered")
		print "executing %s ..." % script
		script = "%s/%s/%s.sh" % ( Config.remote_deploy_dir, self.id, script )
		for host in self.affected_hosts():
			print "%s ..." % host.name
			if bool(Config.remote_dry_run):
				print "DRY RUN: ssh root@%s %s" % ( host.name, script )
			else:
				subprocess.check_call (["ssh",  "root@%s" % host.name, script ])
			print

	def start(self):
		if self.state == None:
			raise Exception ("not deployed")
		if self.state == "deployed":
			raise Exception ("not created")
		if self.state == "created":
			pass
		if self.state == "started":
			raise Exception ("already started")
		self.exec_script("start")
		self.state = "started"

	def stop(self):
		if self.state == None:
			raise Exception ("not deployed")
		if self.state == "deployed":
			raise Exception ("not created")
		if self.state == "created":
			pass
		if self.state == "started":
			pass
		self.exec_script("stop")
		self.state = "created"

	def create(self):
		if self.state == None:
			raise Exception ("not deployed")
		if self.state == "deployed":
			pass
		if self.state == "created":
			raise Exception ("already created")
		if self.state == "started":
			raise Exception ("already started")
		self.exec_script("create")
		self.state = "created"

	def destroy(self):
		if self.state == None:
			raise Exception ("not deployed")
		if self.state == "deployed":
			pass
		if self.state == "created":
			pass
		if self.state == "started":
			raise Exception ("already started")
		self.exec_script("destroy")
		self.state = "deployed"