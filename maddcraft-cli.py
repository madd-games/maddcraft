#! /usr/bin/python
#	Copyright (c) 2014-2018, Madd Games.
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
from libcraft import *

def actionLoop():
	if len(launcherProfiles["profiles"]) == 0:
		print "There are no profiles yet!"
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
