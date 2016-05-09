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
# TODO: OSX perhaps?
from zipfile import ZipFile, BadZipfile		# JARs are secretly ZIP files.
from socket import *
from md5 import *
from getpass import getpass
import sys, os
import json
import urllib
import ctypes
import uuid
import ssl

# Current "launcher version" emulated by MaddCraft.
MC_LAUNCHER_VERSION = 18

currentOS = None
if sys.platform.startswith("win"):
	currentOS = "windows"
else:
	currentOS = "linux"

bits = "32"
if sys.maxint == 9223372036854775807:
	bits = "64"

print "Detected OS: %s-bit %s" % (bits, currentOS)

def makeDir(dirname):
	if currentOS == "linux":
		os.system("mkdir -p " + dirname)
	else:
		# Windows
		os.system("MD " + dirname.replace("/", "\\") + " 2>NUL")

# We will use this default "launcher_profiles.json" template if no file is found yet.
launcherProfiles = {
	"selectedProfile":	"N/A",
	"profiles":	{}
}

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
	
def downloadFromModpack(hostname, request):
	srv = openRequestPipe(hostname, request)
	respline = readRespLine(srv)
	if respline.startswith("MADDCRAFT 1.0 0"):
		return None
	size = int(respline.split(" ")[2])
	data = ""
	
	while len(data) < size:
		chunk = size - len(data)
		if chunk > 4096:
			chunk = 4096
		data += srv.recv(chunk)
	
	srv.close()
	return data

def createModpackLinks(modDir, configDir):
	makeDir("mcdata/"+modDir)
	makeDir("mcdata/"+configDir)
	
	if currentOS=="windows":
		os.system("rd mcdata\\mods")
		os.system("rd mcdata\\config")
		modDir=modDir.replace("/", "\\")
		configDir=configDir.replace("/", "\\")
		os.system("mklink /j mcdata\\mods mcdata\\"+modDir)
		os.system("mklink /j mcdata\\config mcdata\\"+configDir)
	else:
		if os.path.exists("mcdata/mods"): os.remove("mcdata/mods")
		if os.path.exists("mcdata/config"): os.remove("mcdata/config")
		os.symlink(modDir, "mcdata/mods")
		os.symlink(configDir, "mcdata/config")
		

class Profile:
	def __init__(self, data):
		self.data = data
		self.name = data["name"]
		self.version = data["lastVersionId"]
		self.libs = []
		self.fileIndex = []
		
		self.creds = None
		if data.has_key("maddcraft-creds"):
			self.creds = data["maddcraft-creds"]

		# Try loading the version info so that we can launch.
		f = None
		try:
			f = open("mcdata/versions/%s/%s.json" % (self.version, self.version), "rb")
		except IOError:
			makeDir("mcdata/versions/%s" % self.version)
			self.downloadFile("mcdata/versions/%s/%s.json" % (self.version, self.version),
					"http://s3.amazonaws.com/Minecraft.Download/versions/%s/%s.json" % (self.version, self.version)
			)
			f = open("mcdata/versions/%s/%s.json" % (self.version, self.version), "rb")
		sdata = f.read()
		f.close()

		self.versionInfo = json.loads(sdata)
		self.mainClass = self.versionInfo["mainClass"]
		self.minVersion = self.versionInfo["minimumLauncherVersion"]
		self.versionType = self.versionInfo["type"]
		self.mcargs = self.versionInfo["minecraftArguments"]
		self.jar = "versions/%s/%s.jar" % (self.version, self.version)
		
		if self.versionInfo.has_key("inheritsFrom"):
			self.versionInfo["libraries"].extend(self.getLibsFrom(self.versionInfo["inheritsFrom"]))
			
		if self.versionInfo.has_key("jar"):
			jarname = self.versionInfo["jar"]
			self.fileIndex.append(("mcdata/"+self.jar, "http://s3.amazonaws.com/Minecraft.Download/versions/%s/%s.jar" % (jarname, jarname)))
		else:
			self.fileIndex.append(("mcdata/"+self.jar, "http://s3.amazonaws.com/Minecraft.Download/"+self.jar))
			
		for libinfo in self.versionInfo["libraries"]:
			librep = libinfo.get("url", "https://libraries.minecraft.net/")
			name = libinfo["name"]
			package, name, version = name.split(":")
			relpath = package.replace(".", "/") + "/" + name + "/" + version + "/" + name + "-" + version + ".jar"
			self.fileIndex.append(("mcdata/libraries/" + relpath, librep + relpath))
			self.libs.append("libraries/" + relpath)

			if libinfo.has_key("natives"):
				if libinfo["natives"].has_key(currentOS):
					makeDir("mcdata/natives")
					natstr = libinfo["natives"][currentOS].replace("${arch}", bits)
					relpath = package.replace(".", "/") + "/" + name + "/" + version + "/" + name + "-" + version + "-" + natstr + ".jar"
					libpath = "mcdata/libraries/" + relpath
					liburl = librep + relpath
					if not os.path.exists(libpath):
						self.downloadFile(libpath, liburl)
						print ">Extract " + libpath
						try:
							zipfile = ZipFile(libpath, "r")
							for name in zipfile.namelist():
								if not (name.startswith("META-INF") or name.startswith(".")):
									zipfile.extract(name, "mcdata/natives")
							zipfile.close()
						except BadZipfile:
							print "!!! NOT A REAL JAR/ZIP FILE  !!!"
							print "!!! SKIPPING, BUT BEWARE     !!!"
							print "!!! WILL TRY AGAIN NEXT TIME !!!"
							try:
								os.remove(libpath)
							except:
								pass

		# We must also get the assets index.
		assetsName = self.versionInfo.get("assets", "legacy")
		assetsIndexFile = "mcdata/assets/indexes/%s.json" % assetsName
		assetsIndexLink = "https://s3.amazonaws.com/Minecraft.Download/indexes/%s.json" % assetsName
		if not os.path.exists(assetsIndexFile):
			self.downloadFile(assetsIndexFile, assetsIndexLink)

		f = open(assetsIndexFile, "rb")
		assetsData = json.loads(f.read())
		f.close()

		for key, value in assetsData["objects"].items():
			hash = value["hash"]
			pref = hash[:2]
			self.fileIndex.append((
				"mcdata/assets/objects/%s/%s" % (pref, hash),
				"http://resources.download.minecraft.net/%s/%s" % (pref, hash)
			))
		
		modDir = "mods-single"
		configDir = "config-single"
		
		if data.has_key("modpackServer"):
			print ">Update resources"
			makeDir("mcdata/mods-%s" % data["modpackServer"])
			makeDir("mcdata/config-%s" % data["modpackServer"])
			modDir = "mods-%s" % data["modpackServer"]
			configDir = "config-%s" % data["modpackServer"]
			myModTable = getModTable("mcdata/mods-" + data["modpackServer"])
			jsonData = downloadFromModpack(data["modpackServer"], "MADDCRAFT 1.0 getrc %s" % data["modpackServer"])
			if jsonData is None:
				print "ERROR: failed to get resource data from server"
				sys.exit(1)
			srvModTable = json.loads(jsonData)["mods"]
			
			# delete mods that the server does not announce anymore
			for modname in myModTable.keys():
				if not srvModTable.has_key(modname):
					print ">Remove %s" % modname
					os.remove("mcdata/mods-%s/%s" % (data["modpackServer"], modname))
			
			# download mods which the client does not have or with mismatching checksums
			for modname in srvModTable.keys():
				shouldDownload = False
				if not myModTable.has_key(modname):
					shouldDownload = True
				else:
					if srvModTable[modname] != myModTable[modname]:
						# different checksum
						shouldDownload = True
				
				if shouldDownload:
					print ">Update mod %s" % modname
					f = open("mcdata/mods-%s/%s" % (data["modpackServer"], modname), "wb")
					f.write(downloadFromModpack(data["modpackServer"], "MADDCRAFT 1.0 getmod %s %s" % (data["modpackServer"], modname)))
					f.close()
			
			# load the config tables
			myConfigTable = getConfigTable("mcdata/config-%s" % data["modpackServer"])
			srvConfigTable = json.loads(jsonData)["config"]

			# download config files which the client does not have or with mismatching checksums
			for filename in srvConfigTable.keys():
				shouldDownload = False
				dirname = "mcdata/config-%s%s" % (data["modpackServer"], filename.rsplit("/", 1)[0])
				makeDir(dirname)
				
				if not myConfigTable.has_key(filename):
					shouldDownload = True
				else:
					if srvConfigTable[filename] != myConfigTable[filename]:
						# different checksum
						shouldDownload = True
				
				if shouldDownload:
					print ">Update config file %s" % filename
					f = open("mcdata/config-%s%s" % (data["modpackServer"], filename), "wb")
					f.write(downloadFromModpack(data["modpackServer"], "MADDCRAFT 1.0 getconfig %s %s" % (data["modpackServer"], filename)))
					f.close()
					
		print ">Set up links"
		createModpackLinks(modDir, configDir)			

	def hasCreds(self):
		return self.creds is not None

	def getLibsFrom(self, version):
		f = None
		try:
			f = open("mcdata/versions/%s/%s.json" % (version, version), "rb")
		except IOError:
			makeDir("mcdata/versions/%s" % version)
			self.downloadFile("mcdata/versions/%s/%s.json" % (version, version),
					"http://s3.amazonaws.com/Minecraft.Download/versions/%s/%s.json" % (version, version)
			)
			f = open("mcdata/versions/%s/%s.json" % (version, version), "rb")
		sdata = f.read()
		f.close()
		
		info = json.loads(sdata)
		return info["libraries"]
		
	def downloadFile(self, filename, url):
		print ">Download " + filename + " from " + url
		dirname = filename.rsplit("/", 1)[0]
		makeDir(dirname)

		inf = urllib.urlopen(url)
		outf = open(filename, "wb")
		while 1:
			b = inf.read(4096)
			if len(b) == 0:
				break
			else:
				outf.write(b)
		inf.close()
		outf.close()

	def downloadMissingFiles(self):
		for filename, url in self.fileIndex:
			if not os.path.exists(filename):
				self.downloadFile(filename, url)

	def sendAuthRequest(self, endpoint, request):
		body = json.dumps(request)
		text = "POST /%s HTTP/1.1\r\nHost: authserver.mojang.com\r\nUser-Agent: MaddCraft by Madd Games\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s" % (endpoint, len(body), body)

		baseSock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
		baseSock.connect(("authserver.mojang.com", 443))
		
		sock = ssl.wrap_socket(baseSock)
		sock.send(text)
		
		headers = ""
		
		while not headers.endswith("\r\n\r\n"):
			headers += sock.recv(1)
		
		lines = headers.split("\r\n")
		props = {}
		for line in lines[1:]:
			if ": " in line:
				key, value = line.split(": ", 1)
				props[key] = value
		
		if not props.has_key("Content-Length"):
			return None
		
		size = int(props["Content-Length"])
		data = ""
		while len(data) < size:
			data += sock.recv(1)
		
		sock.close()
		
		return json.loads(data)
			
	def login(self, username, password):
		creds = {
			"username":	username,
			"uuid":		str(uuid.uuid4())
		}
		
		request = {
			"agent":	{
				"name":		"Minecraft",
				"version":	1
			},
			
			"username":	username,
			"password":	password,
			"clientToken":	creds["uuid"]
		}
		
		print ">Authenticate"
		resp = self.sendAuthRequest("authenticate", request)
		if resp.has_key("error"):
			print "ERROR: " + resp["errorMessage"]
			return
		
		creds["accessToken"] = resp["accessToken"]
		if not resp.has_key("selectedProfile"):
			print "ERROR: This account is not premium"
			return
			
		creds["name"] = resp["selectedProfile"]["name"]
		self.data["maddcraft-creds"] = creds
		print "Login successful!"
		
	def launchcmd(self, username = "MinecraftPlayer"):
		if self.minVersion > MC_LAUNCHER_VERSION:
			print "!!! WARNING !!!"
			print "This profile requires Minecraft launcher version %d." % self.minVersion
			print "MaddCraft emulates launcher version %d." % MC_LAUNCHER_VERSION
			print "Running this profile might not work."
			print " * If it does work, please tell Madd Games so that we get rid of this warning."
			print " * If it doesn't, tell us so we can fix it."
			answer = raw_input("Do you want to run this profile? (yes/no) ")
			if answer != "yes":
				return "echo"
		libs = [self.jar]
		libs.extend(self.libs)
		cp = ":".join(libs)
		if currentOS == "windows":
			# LOL
			cp = ";".join(libs).replace("/", "\\")

		authUUID = "null"
		authToken = "null"
		mode = "offline"
		
		if username is None:
			validateReq = {
				"accessToken":	self.creds["accessToken"],
				"clientToken":	self.creds["uuid"]
			}
			validateResponse = self.sendAuthRequest("validate", validateReq)
			if validateResponse is not None:
				refreshReq = {
					"accessToken":	self.creds["accessToken"],
					"clientToken":	self.creds["uuid"]
				}
				refreshResponse = self.sendAuthRequest("refresh", refreshReq)
				if refreshResponse.has_key("error"):
					print "ERROR: %s" % refreshResponse["errorMessage"]
					return "echo"
				else:
					self.creds["accessToken"] = refreshResponse["accessToken"]
			username = self.creds["name"]
			authUUID = self.creds["uuid"]
			authToken = self.creds["accessToken"]
			mode = "online"
			
		args = self.mcargs
		args = args.replace("${auth_player_name}", username)
		args = args.replace("${version_name}", self.version)
		args = args.replace("${game_directory}", ".")
		args = args.replace("${game_assets}", "assets")
		args = args.replace("${assets_root}", "assets")
		args = args.replace("${auth_uuid}", authUUID)
		args = args.replace("${auth_access_token}", authToken)
		args = args.replace("${assets_index_name}", self.versionInfo.get("assets", "legacy"))
		args = args.replace("${user_properties}", "{}")
		args = args.replace("${user_type}", mode)
		args = args.replace("${version_type}", self.versionType)

		return 'java -cp "%s" -Dfml.ignoreInvalidMinecraftCertificates=true  -Djava.library.path=natives %s %s' % (cp, self.mainClass, args)

# Duplicate because YOLO
def downloadFile(filename, url):
	print ">Download " + filename
	dirname = filename.rsplit("/", 1)[0]
	makeDir(dirname)

	inf = urllib.urlopen(url)
	outf = open(filename, "wb")
	while 1:
		b = inf.read(4096)
		if len(b) == 0:
			break
		else:
			outf.write(b)
	inf.close()
	outf.close()

try:
	f = open("mcdata/launcher_profiles.json", "rb")
	launcherProfiles = json.loads(f.read())
	f.close()
except:
	pass

def openRequestPipe(hostname, request):
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
		return None
	
	sock.send(request+"\n")
	return sock

def readRespLine(sock):
	respline = ""
	while True:
		c = sock.recv(1)
		if c == "\n":
			break
		respline += c
	return respline
	
def saveProfiles():
	makeDir("mcdata")
	f = open("mcdata/launcher_profiles.json", "wb")
	f.write(json.dumps(launcherProfiles))
	f.close()

def actionLoop():
	if len(launcherProfiles["profiles"]) == 0:
		print "There are not profiles yet!"
	else:
		print "Current profiles:"
		for profile in launcherProfiles["profiles"].keys():
			print " * " + profile

	print "Options:"
	print " 1. Launch a profile."
	print " 2. Create a new profile (or replace one)."
	print " 3. Delete a profile."
	print " 4. Rename profile"
	print " 5. Create profile with modpack server"
	print " 6. Log in to a Mojang account"
	print "(NOTE: There is also a command-line interface; type '%s usage' for more info)" % sys.argv[0]
	choice = raw_input("Choice (1-6): ")
	if choice == "1":
		name = raw_input("Profile to launch: ")
		if not launcherProfiles["profiles"].has_key(name):
			print "This profile does not exist!"
			return
		p = Profile(launcherProfiles["profiles"][name])
		username = None
		if not p.hasCreds():
			username = raw_input("Username: ")
		p.downloadMissingFiles()
		print ">Starting Minecraft..."
		os.system("cd mcdata && %s" % p.launchcmd(username))
	elif choice == "2":
		name = raw_input("New profile name: ")
		version = raw_input("Minecraft version: ")
		profile = {
			"name": name,
			"lastVersionId": version
		}
		launcherProfiles["profiles"][name] = profile
		saveProfiles()
		print "Profile created :)"
	elif choice == "3":
		name = raw_input("Profile name to delete: ")
		if launcherProfiles["profiles"].has_key(name):
			del launcherProfiles["profiles"][name]
			saveProfiles()
		print "Profile deleted :)"
	elif choice == "4":
		name = raw_input("Enter current name of profile: ")
		newName = raw_input("Enter new name of said profile: ")
		
		if not launcherProfiles["profiles"].has_key(name):
			print "This profile does not exist."
		else:
			profile = launcherProfiles["profiles"][name]
			del launcherProfiles["profiles"][name]
			profile["name"] = newName
			launcherProfiles["profiles"][newName] = profile
			saveProfiles()
			print "Profile renamed :)"
	elif choice == "5":
		name = raw_input("Enter name of new profile: ")
		addr = raw_input("Enter address of MaddCraft modpack server: ")
		
		print ">Create profile"
		srv = openRequestPipe(addr, "MADDCRAFT 1.0 stat %s" % addr)
		if srv is None:
			return
			
		respline = readRespLine(srv)
		if respline != "MADDCRAFT 1.0 OK":
			print "Bad response from server: " + respline
			return
		
		info = {}
		while True:
			line = readRespLine(srv)
			if line == "":
				srv.close()
				break
			key, value = line.split(": ", 1)
			info[key] = value
		
		profile = {
			"name":					name,
			"lastVersionId":			info["VersionName"],
			"modpackServer":			info["Server"],
			"minecraftServer":			info["Minecraft"]
		}
		
		launcherProfiles["profiles"][name] = profile
		saveProfiles()
		
		print ">Download version JSON"
		makeDir("mcdata/versions/%s" % info["VersionName"])
		srv = openRequestPipe(addr, "MADDCRAFT 1.0 getjson %s" % addr)
		respline = readRespLine(srv)
		if respline.startswith("MADDCRAFT 1.0 0"):
			print "Server responded with error: " + respline
			return
		
		size = int(respline.split(" ")[2])
		count = 0
		
		f = open("mcdata/versions/%s/%s.json" % (info["VersionName"], info["VersionName"]), "wb")
		while count < size:
			data = srv.recv(4096)
			count += len(data)
			f.write(data)
		f.close()
		srv.close()
		print "Profile created :)"
	elif choice == "6":
		name = raw_input("Profile name: ")
		username = raw_input("Mojang username: ");
		print "[[NOTE: The password you type will not appear on screen!]]"
		password = getpass("Mojang password: ")
		
		p = Profile(launcherProfiles["profiles"][name])
		p.login(username, password)
		saveProfiles()
		
def usage():
	sys.stderr.write("USAGE:\t%s usage\n" % sys.argv[0])
	sys.stderr.write("\t\tDisplays this text.\n")
	sys.stderr.write("\t%s launch <profile-name> <username>\n" % sys.argv[0])
	sys.stderr.write("\t\tLaunch the specified profile, with the specified username.\n")
	sys.exit(1)
	
if len(sys.argv) == 1:
	while True:
		actionLoop()
else:
	cmd = sys.argv[1]
	if cmd == "usage":
		usage()
	elif cmd == "launch":
		if len(sys.argv) != 4:
			sys.stderr.write("invalid syntax\n")
			usage()

		name = sys.argv[2]
		if not launcherProfiles["profiles"].has_key(name):
			sys.stderr.write("%s: profile %s does not exist\n" % (sys.argv[0], name))
			sys.exit(1)
		username = sys.argv[3]
		p = Profile(launcherProfiles["profiles"][name])
		p.downloadMissingFiles()
		print ">Starting Minecraft..."
		os.system("cd mcdata && %s" % p.launchcmd(username))
