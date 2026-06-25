Installation
============

If you want to install the mod manager, please head over to the "Releases" tab over on GitHub and grab the version for your operating system, we currently ship for the following configurations:

Windows
MacOS
Linux (AppImage)
Linux (Flatpak)

Building from source
----------------------

To build the project from source, you can use the provided build scripts found in the `packaging/` folder for your platform. The script takes care of dependency installation and project building. The finished compiled project will
be placed inside the `dist/` folder

The following example shows a basic Windows installation (assuming you are using powershell).
.. code-block:: bash

   git clone https://github.com/PetricaT/IsaacMM.git
   IsaacMM/packaging/windows/build.ps1
