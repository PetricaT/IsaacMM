from cx_Freeze import setup, Executable

setup(name="IsaacMM",
      version = "0.2.4",
      description = "Simple Tboi mod manager",
      executables = [Executable("gui.py")])
