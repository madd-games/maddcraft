#! /usr/bin/python
#	Copyright (c) 2014, Madd Games.
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
import sys, os
import json
import urllib
from zipfile import ZipFile, BadZipfile		# JARs are secretly ZIP files.

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

class Profile:
	def __init__(self, data):
		self.data = data
		self.name = data["name"]
		self.version = data["lastVersionId"]
		self.libs = []
		self.fileIndex = [("mcdata/versions/%s/%s.json" % (self.version, self.version),
					"http://s3.amazonaws.com/Minecraft.Download/versions/%s/%s.json" % (self.version, self.version)),

					("mcdata/versions/%s/%s.jar" % (self.version, self.version),
					"http://s3.amazonaws.com/Minecraft.Download/versions/%s/%s.jar" % (self.version, self.version))
		]

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
		self.mcargs = self.versionInfo["minecraftArguments"]
		self.jar = "versions/%s/%s.jar" % (self.version, self.version)
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

	def downloadFile(self, filename, url):
		print ">Download " + filename
		dirname = filename.rsplit("/", 1)[0]
		makeDir(dirname)

		inf = urllib.urlopen(url)
		outf = open(filename, "wb")
		while 1:
			b = inf.read(1)
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

	def launchcmd(self, username = "MinecraftPlayer"):
		libs = [self.jar]
		libs.extend(self.libs)
		cp = ":".join(libs)
		if currentOS == "windows":
			# LOL
			cp = ";".join(libs).replace("/", "\\")
		args = self.mcargs
		args = args.replace("${auth_player_name}", username)
		args = args.replace("${version_name}", self.version)
		args = args.replace("${game_directory}", ".")
		args = args.replace("${game_assets}", "assets")		# Not even used.
		args = args.replace("${assets_root}", "assets")		# Not even used.
		args = args.replace("${auth_uuid}", "null")
		args = args.replace("${auth_access_token}", "null")
		args = args.replace("${assets_index_name}", self.versionInfo.get("assets", "legacy"))
		args = args.replace("${user_properties}", "{}")
		args = args.replace("${user_type}", "offline")

		return 'java -cp "%s" -Djava.library.path=natives %s %s' % (cp, self.mainClass, args)

launcherProfiles = {
	"selectedProfile": "N/A",
	"profiles": {}
}

try:
	f = open("mcdata/launcher_profiles.json", "rb")
	launcherProfiles = json.loads(f.read())
	f.close()
except:
	pass

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
	choice = raw_input("Choice (1-3): ")
	if choice == "1":
		name = raw_input("Profile to launch: ")
		if not launcherProfiles["profiles"].has_key(name):
			print "This profile does not exist!"
			return
		username = raw_input("Username: ")
		p = Profile(launcherProfiles["profiles"][name])
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
		print "Profile deleted :)"

while True:
	actionLoop()

