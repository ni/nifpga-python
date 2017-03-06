FPGA Interface Python API
=======

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

NOTE: It is always recommended that you use a Session with 'with'.
Opening a Session without 'with' could cause you to leak it if close is not
called.

Controls and indicators are used to transmit small amounts of data to and from
the FPGA. The controls and indicators accessible by the FPGA Interface Python
API are from the front panel of the top level VI from the LabVIEW FPGA code that
was built into the bitfile. Accessing a control or indicator is done via its
unique name from Sessions's register property.

    my_control = session.registers["MyControl"]
    my_control.write(4)
    data = my_control.read()

FIFOs are used for streaming data to and from the FPGA. A FIFO is accessible by
the FPGA Interface Python API via the top level VI from LabVIEW FPGA code.

    myHostToFpgaFifo = session.fifos["MyHostToFpgaFifo"]
    myHostToFpgaFifo.stop()
    actual_depth = myHostToFpgaFifo.configure(requested_depth=4096)
    myHostToFpgaFifo.start()
    empty_elements_remaining = myHostToFpgaFifo.write(data=[1, 2, 3, 4], timeout_ms=2)

    myFpgaToHostFifo = session.fifos["MyHostToFpgaFifo"]
    read_values = myFpgaToHostFifo.read(number_of_elements=4, timeout_ms=0)
    print(read_values.data)

See our readthedocs documentation for more detailed examples.

