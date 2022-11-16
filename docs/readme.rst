===========  =================================================================================================================================
Info         Python API for interacting with LabVIEW FPGA Devices. See our `GitHub <https://github.com/ni/nifpga-python/>`_.
Author       National Instruments
Maintainers  Michael Strain <Michael.Strain@ni.com>
===========  =================================================================================================================================

About
=====

The ``nifpga`` package contains an API for interacting with National Instrument's
LabVIEW FPGA Devices - from Python. This package was created and is officially
supported by National Instruments.

**nifpga**  supports versions 16.0 and later of the RIO driver.

Some functions in the **nifpga** package may be unavailable with earlier
versions of your RIO driver. Visit the
`National Instruments downloads page <http://www.ni.com/downloads/>`_ to
upgrade the appropriate RIO device driver for your hardware.

**nifpga** supports Windows and Linux operating systems.

**nifpga** supports Python  3.5+ . **nifpga** will likely work on other Python implementations.  Feel free to open a issue on github for supporting a new implementation.

Bugs / Feature Requests
=======================

To report a bug or submit a feature request, please use our
`GitHub issues page <https://github.com/ni/nifpga-python/issues>`_ to open a
new issue.

Information to Include When Asking For Help
-------------------------------------------

Please include **all** of the following information when opening an issue:

- Detailed steps on how to reproduce the problem, and full traceback (if
  applicable).
- The exact python version used::

  $ python -c "import sys; print(sys.version)"

- The exact versions of packages used::

  $ python -m pip list

- The exact version of the RIO driver used. Follow
  `this KB article <http://digital.ni.com/public.nsf/allkb/2266B58A5061E86A8625758C007A4FE3>`_
  to determine the RIO driver you have installed.
- The operating system and version (e.g. Windows 7, CentOS 7.2, ...)

Additional Documentation
========================

If you are unfamiliar with LabVIEW FPGA module, perusing the
`LabVIEW FPGA Module <http://www.ni.com/labview/fpga/>`_
resource is a great way to get started. This documentation is API-agnostic.

License
=======
**nifpga** is licensed under an MIT-style license (see LICENSE). Other
incorporated projects may be licensed under different licenses. All licenses
allow for non-commercial and commercial use.