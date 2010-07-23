# -*- coding: utf-8 -*-

from connector import *
from resource_store import *
from host_store import *
from util import *
import os, subprocess, shutil

class TincConnector(Connector):

	tinc_ids = ResourceStore(1,10000)

	def __init__(self, topology, dom, load_ids):
		Connector.__init__(self, topology, dom, load_ids)
		self.decode_xml(dom, load_ids)
		Connection.port_number = property(curry(Connection.get_attr, "port_number"), curry(Connection.set_attr, "port_number"))
		Connection.tinc_id = property(curry(Connection.get_attr, "tinc_id"), curry(Connection.set_attr, "tinc_id"))

	def retake_resources(self):
		for con in self.connections:
			con.retake_resources()
			if con.port_number:
				con.interface.device.host.ports.take_specific(con.port_number)
			if con.tinc_id:
				TincConnector.tinc_ids.take_specific(con.tinc_id)

	def take_resources(self):
		for con in self.connections:
			con.take_resources()
			if not con.port_number:
				con.port_number = str(con.interface.device.host.ports.take())
			if not con.tinc_id:
				con.tinc_id = TincConnector.tinc_ids.take()

	def free_resources(self):
		for con in self.connections:
			con.free_resources()
			con.interface.device.host.ports.free(con.port_number)
			con.port_number = None
			TincConnector.tinc_ids.free(con.tinc_id)
			con.tinc_id = None

	def decode_xml ( self, dom, load_ids ):
		if not load_ids:
			for con in connections:
				con.port_number = None
				con.tinc_id = None

	def encode_xml ( self, dom, doc, print_ids ):
		Connector.encode_xml(self,dom,doc,print_ids)
		if not print_ids:
			for con in dom.getElementsByTagName ( "connection" ):
				if con.hasAttribute("port_number"):
					con.removeAttribute("port_number")
				if con.hasAttribute("tinc_id"):
					con.removeAttribute("tinc_id")

	def tincname(self, con):
		return "tinc_" + con.tinc_id
				

	def write_deploy_script(self):
		print "\tcreating scripts for tinc %s %s ..." % ( self.type, self.id )
		for con in self.connections:
			con.write_deploy_script()
		for con in self.connections:
			host = con.interface.device.host
			tincname = self.tincname(con)
			path = self.topology.get_deploy_dir(host.name) + "/" + tincname
			if not os.path.exists(path+"/hosts"):
				os.makedirs(path+"/hosts")
			subprocess.check_call (["openssl",  "genrsa",  "-out",  path + "/rsa_key.priv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			self_host_fd = open(path+"/hosts/"+tincname, "w")
			self_host_fd.write("Address=%s\n" % host.name)
			self_host_fd.write("Port=%s\n" % con.port_number )
			subprocess.check_call (["openssl",  "rsa", "-pubout", "-in",  path + "/rsa_key.priv", "-out",  path + "/hosts/" + tincname + ".pub"], stderr=subprocess.PIPE)
			self_host_pub_fd = open(path+"/hosts/"+tincname+".pub", "r")
			shutil.copyfileobj(self_host_pub_fd, self_host_fd)
			self_host_fd.close()
			self_host_pub_fd.close()
			tinc_conf_fd = open(path+"/tinc.conf", "w")
			tinc_conf_fd.write ( "Mode=%s\n" % self.type )
			tinc_conf_fd.write ( "Name=%s\n" % tincname )
			for con2 in self.connections:
				host2 = con2.interface.device.host
				tincname2 = self.tincname(con2)
				if not tincname == tincname2:
					tinc_conf_fd.write ( "ConnectTo=%s\n" % tincname2 )
			tinc_conf_fd.close()
			create_fd=open(self.topology.get_deploy_script(host.name,"create"), "a")
			create_fd.write ( "[ -e /etc/tinc/%s ] || ln -s %s/%s /etc/tinc/%s\n" % (tincname, self.topology.get_remote_deploy_dir(), tincname, tincname) )
			create_fd.close ()
			destroy_fd=open(self.topology.get_deploy_script(host.name,"destroy"), "a")
			destroy_fd.write ( "rm /etc/tinc/%s\n" % tincname )
			destroy_fd.write ( "true\n" )
			destroy_fd.close ()
			start_fd=open(self.topology.get_deploy_script(host.name,"start"), "a")
			start_fd.write ( "tincd --net=%s\n" % tincname )
			#FIXME: brctl does not work for routing
			start_fd.write ( "brctl addif %s %s\n" % (con.bridge_name, tincname ) )
			start_fd.write ( "ip link set %s up\n" %  tincname )
			start_fd.close ()
			stop_fd=open(self.topology.get_deploy_script(host.name,"stop"), "a")
			stop_fd.write ( "cat /var/run/tinc.%s.pid | xargs kill\n" % tincname )
			stop_fd.write ( "rm /var/run/tinc.%s.pid\n" % tincname )
			stop_fd.write ( "true\n" )
			stop_fd.close ()
		for con in self.connections:
			host = con.interface.device.host
			tincname = self.tincname(con)
			path = self.topology.get_deploy_dir(host.name) + "/" + tincname
			for con2 in self.connections:
				host2 = con2.interface.device.host
				tincname2 = self.tincname(con2)
				path2 = self.topology.get_deploy_dir(host2.name) + "/" + tincname2
				if not tincname == tincname2:
					shutil.copy(path+"/hosts/"+tincname, path2+"/hosts/"+tincname)