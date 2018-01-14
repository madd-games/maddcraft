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
import wx

app = wx.App()

ID_LAUNCH = wx.NewId()

class MaddCraftWindow(wx.Frame):
	def __init__(self):
		wx.Frame.__init__(self, None, title="MaddCraft")
		self.controls = []
		
		panel = wx.Panel(self)
		mainBox = wx.BoxSizer(wx.VERTICAL)
		ctrlBox = wx.BoxSizer(wx.HORIZONTAL)
		mainBox.Add(ctrlBox, 1, wx.ALL, 0)
		
		profileList = wx.ListBox(panel)
		for profile in launcherProfiles["profiles"].keys():
			profileList.Append(profile)

		self.profileList = profileList
		ctrlBox.Add(profileList, 1, wx.EXPAND | wx.ALL, 5);
		
		buttonBox = wx.BoxSizer(wx.VERTICAL)
		ctrlBox.Add(buttonBox, 0, wx.EXPAND | wx.ALL, 5)
		
		self.btnLaunch = wx.Button(panel, ID_LAUNCH, "Launch profile")
		self.btnNew = wx.Button(panel, -1, "New profile")
		
		self.controls.append(self.btnLaunch)
		self.controls.append(self.btnNew)
		self.controls.append(profileList)
		
		self.Bind(wx.EVT_BUTTON, self.Launch, id=ID_LAUNCH)
		self.Bind(wx.EVT_LISTBOX_DCLICK, self.Launch)

		buttonBox.Add(self.btnLaunch, 0, wx.EXPAND, 0)
		buttonBox.Add(self.btnNew, 0, wx.EXPAND, 0)
		
		self.console = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
		mainBox.Add(self.console, 1, wx.EXPAND | wx.ALL, 5)
		self.console.SetBackgroundColour('#000000')
		self.console.SetDefaultStyle(wx.TextAttr(wx.WHITE))
		self.console.AppendText("Welcome to MaddCraft\n")
		
		panel.SetSizer(mainBox)
		self.Show()
	
	def Launch(self, event):
		for ctrl in self.controls:
			ctrl.Disable()

mainWindow = MaddCraftWindow()
app.MainLoop()
