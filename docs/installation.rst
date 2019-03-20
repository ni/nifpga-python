.. _installation_page:

============
Installation
============
The NI FPGA Interface Python API can be installed through pip, see below
for more detailed instructions.

Windows
-------
#. Install the correct driver for your RIO device

   * You can find drivers at http://www.ni.com/downloads/ni-drivers/

#. Install Python https://www.python.org/downloads/
#. Install nifpga using pip (pip will be installed under "Scripts" in your python installation location.

   .. code-block:: sh

      pip install nifpga

Desktop Linux
-------------
#. Install the correct driver for your RIO device

   * You can find drivers at http://www.ni.com/downloads/ni-drivers/

#. Use your package manager to install the "python-pip" package
#. Install nifpga using pip

.. code-block:: sh

   pip install nifpga

NI Linux RT
-----------
#. Install the driver for your device using NI MAX
#. Enable SSH or the serial console from NI MAX
#. Connect to SSH or the serial console and login as admin
#. Run the following commands

.. code-block:: sh

   opkg update
   opkg install python3 python3-misc
   # follow the latest instructions to install pip:
   # https://pip.pypa.io/en/stable/installing/
   python3 -m pip install nifpga
