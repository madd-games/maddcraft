#! /usr/bin/python
#	Copyright (c) 2014-2016, Madd Games.
#	All rights reserved.
#	
#	Redistribution and use in source and binary forms, with or without
#	modification, are permitted provided that the following conditions are met:
#	
#	* Redistributions of source code must retain the above copyright notice, this
#	  list of conditions and the following disclaimer.
#	
#	* Redistributions in binary form must reproduce the above copyright notice,
#	  this list of conditions and the following disclaimer in the documentation
#	  and/or other materials provided with the distribution.
#	
#	THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#	AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#	IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#	DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#	FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#	DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#	SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#	CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#	OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#	OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# A MaddCraft Server enables easy set-up of Minecraft servers with modpacks.
# The MaddCraft client can connect to such server to update mods and configuration,
# as well as authorize the user.

# !!! FULLY DUAL STACK !!! #

from threading import Thread, Lock
from md5 import md5
from crypt import crypt
from socket import *
import sys, os
import json
import random
import datetime

def putlog(msg):
	print "[%s] [MADDCRAFT-SERVER] %s" % (datetime.datetime.now().strftime("%H:%M:%S on %B %d, %Y"), msg)

def usage():
	print "USAGE:\t%s --start <configuration-file>" % sys.argv[0]
	print "\tStarts the server by loading the specified configuration file."
	print
	print "\t%s --setup" % sys.argv[0]
	print "\tAsks a few questions and sets up a new server"
	print
	print "\t%s --help" % sys.argv[0]
	print "\tShows this help message."
	print
	print "\t%s --add-user <server> <admin-password> <new-user-name>" % sys.argv[0]
	print "\tAdds a new user or resets a current user's password."
	print "\tThe password will be set when the user logs in."
	print
	print "\t%s --login <server> <username> <password>" % sys.argv[0]
	print "\tLogs into the given server using the current IP address."
	print
	print "\t%s --stat <server>" % sys.argv[0]
	print "\tDisplays information about the specified server."
	sys.exit(1)
	
if len(sys.argv) < 2:
	usage()

def fileChecksum(filename):
	f = open(filename, "rb")
	data = f.read()
	f.close()
	return md5(data).hexdigest()

def getModTable(modpath):
	output = {}
	for name in os.listdir(modpath):
		output[name] = fileChecksum(modpath+"/"+name)
	return output

def getConfigTableSub(output, path, prefix):
	for name in os.listdir(path):
		fullpath = path+"/"+name
		if os.path.isdir(fullpath):
			getConfigTableSub(output, fullpath, prefix+"/"+name)
		else:
			output[prefix+"/"+name] = fileChecksum(fullpath)

def getConfigTable(confpath):
	output = {}
	getConfigTableSub(output, confpath, "")
	return output

def randomSalt():
	saltChars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ./"
	a = int(random.uniform(0, 63))
	b = int(random.uniform(0, 63))
	return saltChars[a] + saltChars[b]

def serverSetup():
	print "!!! WELCOME TO MADDCRAFT SERVER SETUP !!!"
	print "I will ask you a few questions, and your new server will be up"
	print "in no time."
	
	configFile = raw_input("Enter the location of your new config file: ")
	hostname = raw_input("Enter your server hostname: ")
	adminPassword = raw_input("Enter admin password: ")
	serverAddr = raw_input("Enter Minecraft server address: ")
	versionName = raw_input("Enter Minecraft pseudo-version name: ")
	versionJson = raw_input("Enter version JSON path: ")
	modsFolder = raw_input("Enter path to mods folder: ")
	configFolder = raw_input("Enter path of mod config folder: ")
	
	print "Creating configuration file..."
	config = {
		"server@"+hostname:	{
			"users":	{
				"admin":	crypt(adminPassword, randomSalt()),
			},
			
			"auth-ip":	{
				"admin":	"?"
			},
			
			"mcserver":	serverAddr,
			"mcversion":	versionName,
			"mcjson":	versionJson,
			"mods":		modsFolder,
			"config":	configFolder
		},
		
		"bindto": ["::", 25666]
	}
	
	try:
		f = open(configFile, "wb")
		json.dump(config, f)
		f.close()
	except Exception, e:
		print "!!! FAILED TO CREATE CONFIGURATION FILE !!!"
		print repr(e)
		sys.exit(1)
	
	print "Your MaddCraft server has now been set up!"
	print "You can run it using:"
	print "\t%s --start %s" % (sys.argv[0], configFile)
	print "You may want to edit your configuration file to use non-standard"
	print "options such as a different port"

serverConfigPath = ""
serverConfig = {}
serverResources = {}
configLock = Lock()

def saveConfig():
	f = open(serverConfigPath, "wb")
	json.dump(serverConfig, f)
	f.close()
	
class ServerConnection:
	def __init__(self, client):
		self.clientSock = client[0]
		self.clientAddr = client[1][0]
		
		# if the client address if IPv6-mapped-IPv4, we display the IPv4 address.
		if self.clientAddr.startswith("::ffff:"):
			self.clientAddr = self.clientAddr[7:]
			
	def run(self):
		self.clientSock.settimeout(10)
		line = ""
		while "\n" not in line:
			if len(line) > 512:
				putlog("Bad request from '%s': request line exceeded 512 bytes" % self.clientAddr)
			
			try:
				line += self.clientSock.recv(64)
			except Exception, e:
				putlog("Error receiving from '%s': %s" % (self.clientAddr, repr(e)))
			
		if not line.endswith("\n"):
			putlog("Bad request from '%s': garbage after request line" % self.clientAddr)
			self.clientSock.close()
			return
		
		tokens = line[:-1].split(" ")
		if len(tokens) < 3:
			putlog("Bad request from '%s': invalid request line" % self.clientAddr)
			self.clientSock.close()
			return
			
		if tokens[0] != "MADDCRAFT":
			putlog("Bad request from '%s': request line does not have 'MADDCRAFT' signature" % self.clientAddr)
			self.clientSock.close()
			return
			
		if tokens[1] != "1.0":
			putlog("Bad request from '%s': unsupported client 'MaddCraft %s'" % (self.clientAddr, tokens[1]))
			self.clientSock.close()
			return
			
		cmd = tokens[2]
		args = tokens[3:]
		
		if cmd == "stat":
			if len(args) != 1:
				putlog("Bad request from '%s': invalid syntax for 'stat' request" % self.clientAddr)
				self.clientSock.close()
				return
			
			configLock.acquire()
			server = args[0]
			if not serverConfig.has_key("server@"+server):
				putlog("Client '%s' requested unknown server '%s'" % (self.clientAddr, server))
				self.clientSock.send("MADDCRAFT 1.0 No such server\n\n")
				self.clientSock.close()
				configLock.release()
				return
			
			putlog("Client '%s' requested info about '%s'" % (self.clientAddr, server))
			response = "MADDCRAFT 1.0 OK\nServer: %s\nMinecraft: %s\nVersionName: %s\n\n" \
					% (server, serverConfig["server@"+server]["mcserver"], serverConfig["server@"+server]["mcversion"])
			self.clientSock.send(response)
			self.clientSock.close()
			configLock.release()
		elif cmd == "getjson":
			if len(args) != 1:
				putlog("Bad request from '%s': invalid syntax for 'getjson' request" % self.clientAddr)
				self.clientSock.close()
				return
			
			configLock.acquire()
			server = args[0]
			if not serverConfig.has_key("server@"+server):
				putlog("Client '%s' requested unknown server '%s'" % (self.clientAddr, server))
				self.clientSock.send("MADDCRAFT 1.0 0 No such server\n")
				self.clientSock.close()
				configLock.release()
				return
			
			putlog("Client '%s' requested JSON for '%s'" % (self.clientAddr, server))
			f = open(serverConfig["server@"+server]["mcjson"], "rb")
			data = f.read()
			f.close()
			response = "MADDCRAFT 1.0 %d\n%s" % (len(data), data)
			self.clientSock.send(response)
			self.clientSock.close()
			configLock.release()
		elif cmd == "getrc":
			if len(args) != 1:
				putlog("Bad request from '%s': invalid syntax for 'getrc' request" % self.clientAddr)
				self.clientSock.close()
				return

			configLock.acquire()
			server = args[0]
			if not serverConfig.has_key("server@"+server):
				putlog("Client '%s' requested unknown server '%s'" % (self.clientAddr, server))
				self.clientSock.send("MADDCRAFT 1.0 0 No such server\n")
				self.clientSock.close()
				configLock.release()
				return
			
			putlog("Client '%s' requested resources for '%s'" % (self.clientAddr, server))
			data = json.dumps(serverResources[server])
			response = "MADDCRAFT 1.0 %d\n%s" % (len(data), data)
			self.clientSock.send(response)
			self.clientSock.close()
			configLock.release()
		elif cmd == "getmod":
			if len(args) != 2:
				putlog("Bad request from '%s': invalid syntax for 'getmod' request" % self.clientAddr)
				self.clientSock.close()
				return
			
			configLock.acquire()
			server = args[0]
			mod = args[1]
			if not serverConfig.has_key("server@"+server):
				putlog("Client '%s' requested unknown server '%s'" % (self.clientAddr, server))
				self.clientSock.send("MADDCRAFT 1.0 0 No such server\n")
				self.clientSock.close()
				configLock.release()
				return
			
			if not serverResources[server]["mods"].has_key(mod):
				putlog("Client '%s' requested unknown mod '%s' from '%s'" % (self.clientAddr, mod, server))
				self.clientSock.send("MADDCRAFT 1.0 0 No such mod\n")
				self.clientSock.close()
				configLock.release()
				return
				
			putlog("Client '%s' requested mod '%s' from '%s'" % (self.clientAddr, mod, server))
			f = open(serverConfig["server@"+server]["mods"]+"/"+mod, "rb")
			data = f.read()
			f.close()
			response = "MADDCRAFT 1.0 %d\n" % len(data)
			self.clientSock.send(response)
			while len(data) > 2048:
				self.clientSock.send(data[:2048])
				data = data[2048:]
			self.clientSock.send(data)
			self.clientSock.close()
			configLock.release()
		elif cmd == "getconfig":
			if len(args) != 2:
				putlog("Bad request from '%s': invalid syntax for 'getconfig' request" % self.clientAddr)
				self.clientSock.close()
				return
			
			configLock.acquire()
			server = args[0]
			filename = args[1]
			if not serverConfig.has_key("server@"+server):
				putlog("Client '%s' requested unknown server '%s'" % (self.clientAddr, server))
				self.clientSock.send("MADDCRAFT 1.0 0 No such server\n")
				self.clientSock.close()
				configLock.release()
				return
			
			if not serverResources[server]["config"].has_key(filename):
				putlog("Client '%s' requested unknown config file '%s' from '%s'" % (self.clientAddr, filename, server))
				self.clientSock.send("MADDCRAFT 1.0 0 No such mod\n")
				self.clientSock.close()
				configLock.release()
				return
				
			putlog("Client '%s' requested config file '%s' from '%s'" % (self.clientAddr, filename, server))
			f = open(serverConfig["server@"+server]["config"]+filename, "rb")
			data = f.read()
			f.close()
			response = "MADDCRAFT 1.0 %d\n" % len(data)
			self.clientSock.send(response)
			while len(data) > 2048:
				self.clientSock.send(data[:2048])
				data = data[2048:]
			self.clientSock.send(data)
			self.clientSock.close()
			configLock.release()
		elif cmd == "login":
			if len(args) != 3:
				putlog("Bad request from '%s': invalid syntax for 'login' request" % self.clientAddr)
				self.clientSock.close()
				return
			
			server = "server@" + args[0]
			login = args[1]
			passwd = args[2]
			
			configLock.acquire()
			if not serverConfig.has_key(server):
				putlog("Client '%s' attempted to log into non-existent server '%s'" % (self.clientAddr, args[0]))
				self.clientSock.send("MADDCRAFT 1.0 No such server\n")
				self.clientSock.close()
				configLock.release()
				return
				
			if not serverConfig[server]["users"].has_key(login):
				putlog("Client '%s' attempted to log in with invalid username or password" % self.clientAddr)
				self.clientSock.send("MADDCRAFT 1.0 Bad login or password\n")
				self.clientSock.close()
				configLock.release()
				return
			
			if serverConfig[server]["users"][login] == "$":
				serverConfig[server]["users"][login] = crypt(passwd, randomSalt())
				
			passhash = crypt(passwd, serverConfig[server]["users"][login][:2])
			if passhash != serverConfig[server]["users"][login]:
				putlog("Client '%s' attempted to log in with invalid username or password" % self.clientAddr)
				self.clientSock.send("MADDCRAFT 1.0 Bad login or password\n")
				self.clientSock.close()
				configLock.release()
				return
			
			putlog("Client '%s' successfully logged in to '%s' as '%s'" % (self.clientAddr, args[0], login))
			serverConfig[server]["auth-ip"][login] = self.clientAddr
			configLock.release()
			self.clientSock.send("MADDCRAFT 1.0 OK\n")
			self.clientSock.close()
			saveConfig()
		elif cmd == "adduser":
			if len(args) != 3:
				putlog("Bad request from '%s': invalid syntax for 'adduser' request" % self.clientAddr)
				self.clientSock.close()
				return
			
			server = "server@" + args[0]
			adminPassword = args[1]
			username = args[2]
			
			configLock.acquire()
			if not serverConfig.has_key(server):
				putlog("Client '%s' attempted to log into non-existent server '%s'" % (self.clientAddr, args[0]))
				self.clientSock.send("MADDCRAFT 1.0 No such server\n")
				self.clientSock.close()
				configLock.release()
				return
				
			passhash = crypt(adminPassword, serverConfig[server]["users"]["admin"][:2])
			if passhash != serverConfig[server]["users"]["admin"]:
				putlog("Client '%s' attempted to add user '%s' but specified invalid admin password" % (self.clientAddr, username))
				self.clientSock.send("MADDCRAFT 1.0 Bad admin password\n")
				self.clientSock.close()
				configLock.release()
				return
			
			putlog("Client '%s' successfully added new user '%s' to '%s'" % (self.clientAddr, username, args[0]))
			serverConfig[server]["users"][username] = "$"
			serverConfig[server]["auth-ip"][username] = "?"
			configLock.release()
			self.clientSock.send("MADDCRAFT 1.0 OK\n")
			self.clientSock.close()
			saveConfig()
		else:
			putlog("Bad request from '%s': invalid command '%s'" % (self.clientAddr, cmd))
			self.clientSock.send("MADDCRAFT 1.0 ? Invalid command\n")
			self.clientSock.close()
			
def serverStart(configFile):
	global serverConfig
	global serverConfigPath
	global serverResources
	config = None
	try:
		f = open(configFile, "rb")
		config = json.load(f)
		f.close()
	except Exception, e:
		print "ERROR: Failed to load config file"
		print repr(e)
	
	serverConfigPath = configFile
	serverConfig = config
	
	for key in serverConfig.keys():
		if key.startswith("server@"):
			srvname = key[7:]
			putlog("Loading resources for '%s'" % srvname)
			serverResources[srvname] = {
				"mods":		getModTable(serverConfig[key]["mods"]),
				"config":	getConfigTable(serverConfig[key]["config"])
			}

	putlog("Server starting on [%s]:%d" % (config["bindto"][0], config["bindto"][1]))
	server = socket(AF_INET6, SOCK_STREAM, 0)
	try:
		server.setsockopt(IPPROTO_IPV6, IPV6_V6ONLY, 0)
	except Exception:
		# perhaps we don't need to turn off v6-only on this OS
		pass
	server.bind((config["bindto"][0], config["bindto"][1]))
	server.listen(5)
	
	putlog("Server up")
	while True:
		client = server.accept()
		conn = ServerConnection(client)
		t = Thread(target = conn.run)
		t.setDaemon(True)
		t.start()

def serverAddUser(hostname, adminPassword, username):
	sock = None
	for family, socktype, proto, canonname, sockaddr in getaddrinfo(hostname, 25666, 0, SOCK_STREAM, IPPROTO_TCP):
		try:
			s = socket(family, socktype, proto)
			s.connect(sockaddr)
			sock = s
			break
		except Exception, e:
			continue
	
	if sock is None:
		print "Cannot connect to server"
		sys.exit(1)
	
	sock.send("MADDCRAFT 1.0 adduser %s %s %s\n" % (hostname, adminPassword, username))
	respline = ""
	while True:
		c = sock.recv(1)
		if c == "\n":
			break
		else:
			respline += c
	
	sock.close()
	print respline

def serverLogin(hostname, username, password):
	sock = None
	for family, socktype, proto, canonname, sockaddr in getaddrinfo(hostname, 25666, 0, SOCK_STREAM, IPPROTO_TCP):
		try:
			s = socket(family, socktype, proto)
			s.connect(sockaddr)
			sock = s
			break
		except Exception, e:
			continue
	
	if sock is None:
		print "Cannot connect to server"
		sys.exit(1)
	
	sock.send("MADDCRAFT 1.0 login %s %s %s\n" % (hostname, username, password))
	respline = ""
	while True:
		c = sock.recv(1)
		if c == "\n":
			break
		else:
			respline += c
	
	sock.close()
	print respline

def serverStat(hostname):
	sock = None
	for family, socktype, proto, canonname, sockaddr in getaddrinfo(hostname, 25666, 0, SOCK_STREAM, IPPROTO_TCP):
		try:
			s = socket(family, socktype, proto)
			s.connect(sockaddr)
			sock = s
			break
		except Exception, e:
			continue
	
	if sock is None:
		print "Cannot connect to server"
		sys.exit(1)
	
	sock.send("MADDCRAFT 1.0 stat %s\n" % hostname)
	respline = ""
	while "\n\n" not in respline:
		respline += sock.recv(64)
	
	sock.close()
	print respline[:-2]	# remove the double-endline!
	
if sys.argv[1] == "--setup":
	serverSetup()
elif sys.argv[1] == "--start":
	if len(sys.argv) != 3:
		print "ERROR: no config file specified"
		print "Type `%s --help' for usage." % sys.argv[0]
	else:
		serverStart(sys.argv[2])
elif sys.argv[1] == "--add-user":
	if len(sys.argv) != 5:
		print "ERROR: not enough arguments"
		print "Type `%s --help' for usage." % sys.argv[0]
	else:
		serverAddUser(sys.argv[2], sys.argv[3], sys.argv[4])
elif sys.argv[1] == "--login":
	if len(sys.argv) != 5:
		print "ERROR: not enough arguments"
		print "Type `%s --help' for usage." % sys.argv[0]
	else:
		serverLogin(sys.argv[2], sys.argv[3], sys.argv[4])
elif sys.argv[1] == "--stat":
	if len(sys.argv) != 3:
		print "ERROR: not enough arguments"
		print "Type `%s --help' for usage." % sys.argv[0]
	else:
		serverStat(sys.argv[2])
else:
	usage()
