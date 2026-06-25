Configuration
=============

.. TODO: Write configuration reference

Settings Dialog
---------------

.. TODO: Describe each setting in the Settings dialog

.. glossary::

   Mods Path
      Path to The Binding of Isaac's ``mods`` directory.

   Download Icons
      Toggle automatic workshop icon downloads.

   Animate Icons
      Play animated GIF icons in the Mod Info panel.

   Animate .anm2 Previews
      Play .anm2 sprite animations on hover preview.

   Theme
      UI theme selection.

   Accent Color
      Primary accent color for the mod list.

   Disabled Mod Color
      Text color for disabled mods in the list.

   Log Level
      Minimum log level shown in the console (Debug, Info, Warning, Error).

Configuration File
------------------

The configuration file location differs for each opearting system, but the simplest way to go about this would be to open Settings
and press the Open Config. Here is an example of the default configuration.

.. code-block:: toml
    [paths]
    mods = "~/.local/share/Steam/steamapps/common/The Binding of Isaac Rebirth/mods/"

    [settings]
    backup_enabled = false
    theme = "fusion"
    animate_icons = true
    animate_anm2_preview = true
    preview_images = false
    download_icons = false
    log_level = "info"
    dead_workshop_ids = [ ]
    ignored_items = [ ".git", "__pycache__", "metadata.xml", "disable.it", ".DS_Store", "Thumbs.db", "desktop.ini", ".Trashes", ".Spotlight-V100", "$RECYCLE.BIN", ".directory", "~",]

    [theme]
    accent = "#3daee9"
    disabled_mod = "#808080"

    [workshop]
    timestamps = [ ]

Another interesting configuration file is the user defined auto-sort rules ``user_rules.yaml``.

.. code-block:: yaml
    rules:
    #   - id: 1234567890
    #   after: [9876543210]

Here you can define a mod by it's workshop id, and a before/after which mods you want to place it at when auto-sorting.
