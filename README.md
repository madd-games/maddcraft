MaddCraft
=========

A simple Python script for launching Minecraft. You could use it as a template to make custom Minecraft launchers for modpacks and stuff. You might find it useful. Do what you want. It's on the BSD license.

FAQ 
===

Oh no, where are all the Minecraft files ?!
-------------------------------------------

They are in the `mcdata` folder that this scripts creates instead of the normal `.minecraft` folder.

Can I install Forge and play cool mods?
---------------------------------------

Yes, but when installing Forge, you must direct it to the `mcdata` folder isntead of the default `.minecraft`. Also, the multi-modpack support must be able to create symlinks/shortcuts called `config` and `mods`, so instead of putting your mods and config into those folders, rename them to `mods-single` and `config-single`, and MaddCraft will automatically create the appropriate links to direct Forge to them. You may also have other mods and config folders, when using MaddCraft modpack servers.
