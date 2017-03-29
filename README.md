FPGA Interface Python API
=======

[![Build Status](https://travis-ci.org/ni/nifpga-python.svg?branch=master)](https://travis-ci.org/ni/nifpga-python)

Overview
--------
The National Instruments FPGA Interface Python API is used for communication between processor and FPGA within NI reconfigurable I/O (RIO) hardware such as NI CompactRIO, NI Single-Board RIO, NI FlexRIO, and NI R Series multifunction RIO.

With the FPGA Interface Python API, developers can use LabVIEW FPGA to program the FPGA within NI hardware and communicate to it from Python running on a host computer. This gives engineers and scientists with Python expertise the ability to take advantage of compiled LabVIEW FPGA bitfiles, also the option to reuse existing Python code.

Installation
------------
NiFpga can be installed by cloning the master branch and then in a command
line in the directory of setup.py run:

    pip install --pre .

Or by installing from PyPI using:

    pip install nifpga

Examples
--------

The FPGA Interface Python API is session based. LabVIEW FPGA will generate
bitfiles (.lvbitx) that can be used to program the hardware. For additional
information on sessions view our Read the docs documentation

Example usage of FPGA configuration functions:

    with Session(bitfile="BitfilePath.lvbitx", resource="RIO0") as session:
       try:
          session.run()
       except FpgaAlreadyRunningWarning:
          pass
       session.download()
       session.abort()
       session.reset()
       my_control = session.registers["MyControl"]
       my_control.write(4)
       data = my_control.read()


See our [readthedocs page](http://nifpga-python.readthedocs.io/en/latest/) for more detailed examples and documentation.

