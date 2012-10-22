import lib, time, os

def checkCreate(indent=""):
	print indent + "creating element..."
	res = element_create("kvmqm")
	assert res["id"]
	print indent + "\tID: %d" % res["id"]
	return res["id"]

def checkCreateInterface(id, indent=""):
	print indent + "creating interface..."
	res = element_create("kvmqm_interface", id)
	assert res["id"]
	print indent + "\tID: %d" % res["id"]
	return res["id"]

def checkRemove(id, indent=""):
	print indent + "removing element..."
	res = element_remove(id)
	assert not res

def checkAction(id, action, params={}, assertState=None, indent=""):
	print indent + "executing action %s on element..." % action
	res = element_action(id, action, params)
	if assertState:
		info = element_info(id)
		assert info["state"] == assertState
	return res

def tearDown(id, indent=""):
	try:
		info = element_info(id)
	except:
		return
	if info["state"] == "prepared":
		checkAction(id, "destroy", assertState="created", indent=indent)
	if info["state"] == "started":
		checkAction(id, "stop", assertState="prepared", indent=indent)
		checkAction(id, "destroy", assertState="created", indent=indent)
	checkRemove(id, indent=indent)

def check(indent="", shellError=False):
	print indent + "checking KVMQM element type..." 
	indent += "\t"
	try:
		id = checkCreate(indent=indent)

		id1 = checkCreateInterface(id, indent=indent)
		
		checkAction(id, "prepare", assertState="prepared", indent=indent)
		
		id2 = checkCreateInterface(id, indent=indent)

		print indent + "checking attribute changes in state prepared..."
		element_modify(id, {"cpus": 2, "ram": 128, "usbtablet": False, "kblang": "de", "template": None})
		
		checkAction(id, "start", assertState="started", indent=indent)
		
		print indent + "checking VNC server..."
		info = element_info(id)
		assert "attrs" in info and "vncport" in info["attrs"]
		assert lib.tcpPortOpen(__hostname__, info["attrs"]["vncport"]), "VNC Port not open"
		
		checkAction(id, "stop", assertState="prepared", indent=indent)
		
		print indent + "checking disk download and upload..."
		fileserver_port = host_info()["fileserver_port"]
		assert fileserver_port	
		grant = element_action(id, "download_grant")
		assert grant
		lib.download("http://%s:%d/%s/download" % (__hostname__, fileserver_port, grant), "disk.qcow2")
		assert os.path.exists("disk.qcow2")
		grant = element_action(id, "upload_grant")
		assert grant
		lib.upload("http://%s:%d/%s/upload" % (__hostname__, fileserver_port, grant), "disk.qcow2")
		element_action(id, "upload_use")
		
		checkRemove(id1, indent=indent)		
		
		checkAction(id, "destroy", assertState="created", indent=indent)
		
		checkRemove(id, indent=indent)
	except:
		import traceback
		traceback.print_exc()
		if shellError:
			shell()
	finally:
		if os.path.exists("disk.qcow2"):
			os.remove("disk.qcow2")
		tearDown(id, indent)

if __name__ == "__main__":
	try:
		check(shellError=True)
	except:
		import traceback
		traceback.print_exc()