Usage
=====

Here you can get the basics of utilizing the mod manager.

Getting Started
---------------

On the first launch, the mod manager will try and query steam's VDF files to find where the binding of isaac is installed.
If the mod manager cannot find it, and your mod list appears empty, please check in settings and select the mod path of your game.
Once the path is set, you should be able to see the list get populated.

.. TODO: Image here

The Mod List
------------

The modlist provides a mirror of the one that can be found in the game itself. Any mod that you disable via the checklist, will
also be disabled in game, and some styling is applied to indicate that.

If a mod is currently in a conflict, you will see a colored background on all mods which are in that conflict.

The Mod Info Panel
------------------

The mod info panel will display useful information about the currently selected mod. There are 3 tabs which can be used here.

- Description
- Conflicts
- Files

The description is taken from the mod's own `manifest.xml`, and is typically a mirror of the steam workshop description.

The conflicts tab can show you the exact files which the mod conflicts with.

.. TODO: Image

The files tab will show you the entire folder structure of the actively selected mod.

.. TODO: Image

Sorting Mods
------------

In order to sort the mods, you must move them accordingly in the list, the higher the mod is, the more priority it will have over others.

Once you are happy with your order, do not forget to press "Apply sort order", otherwise no changes will be saved to the disk.

Because some mods depend on other, and because of this dependency they require to be higher priority than the requester, an auto-sort function
is provided, which integrates the predefined `masterlist.yaml` to automatically place certain mods below/above other. (If you notice
any incompatibilities or issues where the order causes problems, make sure to create a bug report so it can be fixed!)

Workshop Integration
--------------------

If a mod does not ship with its own thumbnail on the workshop, you can enable a feature in settings that automatically fetches
these thumbnails from the workshop, and caches them locally. The Steam api is used for this, but I found it to be
rather fragile, so a Queue & Cooldown mechanism is implemented, which limits how often we try to fetch these elements.

This feature is turned off by default, to prevent accidental abuse and network traffic. You may turn this on in settings

.. TODO: IMAGE HERE

Conflict Resolution
-------------------

Because of the way Isaac loads mods and prioritizes them, whatever mod is on the bottom of the list loses all conflicts, therefore,
the higher the mod in the list, the more priority it has over everything else. This is indicated by the fact that when you hover
over a mod that is trying to change similar files to another mod, the mods who lose to the active mod are highlighted in green
and the mods who overwrite the active mod, are highlighted in red.

.. TODO: IMAGE HERE

Preview
-------

The conflict/file browser offer a quick way to look at the local files. When you hover over a supported item (.png, .anm2)
a small preview will be shown next to your cursor.

This preview can be turned off from the settings.

.. TODO: IMAGE HERE
