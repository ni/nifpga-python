import os
import warnings
import xml.etree.ElementTree as ElementTree
from nifpga import DataType


class Bitfile(object):
    """ Class that represents the contents of the .lvbitx file.

    Bitfile is a class that parses and contains the data from the XML based
    .lvbitx file.  This class can be used to lookup registers and FIFOs and
    is mostly intended to be used by Session.
    """
    def __init__(self, filepath, parse_contents=False):
        if parse_contents:
            self._filepath = None
            tree = ElementTree.fromstring(filepath)
        else:
            self._filepath = os.path.abspath(filepath)
            tree = ElementTree.ElementTree().parse(self._filepath)

        self._signature = tree.find("SignatureRegister").text.upper()

        project = tree.find("Project")
        nifpga = project.find("CompilationResultsTree") \
                        .find("CompilationResults") \
                        .find("NiFpga")
        self._base_address_on_device = int(nifpga.find("BaseAddressOnDevice").text)
        self._registers = {}
        for reg_xml in tree.find("VI").find("RegisterList"):
            reg = self.create_register(reg_xml)
            if reg.datatype is not None:
                assert reg.name not in self._registers, \
                    "One or more registers have the same name '%s', this is not supported" % reg.name
                self._registers[reg.name] = reg

        self._fifos = {}
        for channel_xml in nifpga.find("DmaChannelAllocationList"):
            fifo = Fifo(channel_xml)
            self._fifos[fifo.name] = fifo

    @property
    def filepath(self):
        """ Returns the filepath used to create this bitfile. """
        return self._filepath

    @property
    def signature(self):
        """ Returns the signature of the bitfile. """
        return self._signature

    @property
    def registers(self):
        """ Returns a dictionary of Registers (Controls and Indicators) that
        the bitfile contained.  The dictionary is indexed by the name of the
        register.
        """
        return self._registers

    @property
    def fifos(self):
        """ Returns a dictionary of FIFOs that the bitfile contained.
        The dictionary is indexed by the name of the FIFO.
        """
        return self._fifos

    def base_address_on_device(self):
        """ Returns the base address on the device.  This is the offset on the
        device that Registers are located at.  So a Registers offset is
        base_address_on_device + register_offset
        """
        return self._base_address_on_device

    def create_register(self, xml):
        register = Register(xml)
        if (self._is_register_fxp(register)):
            register = Fxp_Register(xml, register)
        return register

    def _is_register_fxp(self, register):
        return register.datatype is DataType.FXP


class Register(object):
    def __init__(self, reg_xml):
        """
        A control or indicator from the front panel of the top level FPGA VI

        reg_xml: the <Register> XML element, e.g. one of these:
            <Register>
                <Name>Output Array Bool 17</Name>
                <Indicator>true</Indicator>
                <Datatype>
                    <Array>
                        <Name>Output Array Bool 17</Name>
                        <Size>17</Size>
                        <Type>
                            <Boolean>
                            </Boolean>
                        </Type>
                    </Array>
                </Datatype>
                <Offset>98364</Offset>
                <Internal>false</Internal>
                <AccessMayTimeout>false</AccessMayTimeout>
            </Register>

            Or

            <Register>
                <Name>Input U64</Name>
                <Indicator>false</Indicator>
                <Datatype>
                    <U64>
                    </U64>
                </Datatype>
                <Offset>98464</Offset>
                <Internal>false</Internal>
                <AccessMayTimeout>false</AccessMayTimeout>
            </Register>
        """
        self._name = reg_xml.find("Name").text
        self._offset = int(reg_xml.find("Offset").text)
        self._access_may_timeout = True if reg_xml.find("AccessMayTimeout").text.lower() == 'true' else False
        self._internal = True if reg_xml.find("Internal").text.lower() == 'true' else False
        datatype = reg_xml.find("Datatype")
        if datatype.find("Array") is not None:
            self._is_array = True
            typeholder = datatype.find("Array").find("Type")
            self._num_elements = int(datatype.find("Array").find("Size").text)
        else:
            self._is_array = False
            typeholder = datatype
            self._num_elements = 1
        for child in typeholder.getchildren():
            self._datatype = None
            for datatype in DataType:
                if str(datatype).lower() in child.tag.lower():
                    self._datatype = datatype
            if self._datatype is None:
                warnings.warn("Register '%s' has unsupported type" % self._name)

    def __len__(self):
        """ Returns the number of elements in this register. """
        return self._num_elements

    @property
    def name(self):
        """ Returns the name of the Register. """
        return self._name

    @property
    def datatype(self):
        """ Returns a string containing the datatype of the Register. """
        return self._datatype

    def is_array(self):
        """ Returns whether or not this Register is an array """
        return self._is_array

    @property
    def offset(self):
        """ Returns the offset of this register from the base address. """
        return self._offset

    def access_may_timeout(self):
        """ Returns Whether or not this register access could timeout.
        This could happen if the register is in an external clock domain.
        """
        return self._access_may_timeout

    def is_internal(self):
        """ Returns whether or not this register is for internal use. """
        return self._internal

    def __str__(self):
        return ("Register '%s'\n" % self._name +
                "\tType: %s\n" % self._datatype +
                "\tNum Elements: %d\n" % len(self) +
                "\tOffset: %d\n" % self._offset)


class Fxp_Register(Register):
    """
    A fixed point control or indicator from the front panel of the top level
    FPGA VI.
    """
    def __init__(self, reg_xml, register):
        self._copy_values_from_register(register)
        self._signed = True if reg_xml.find("Signed").text.lower() == 'true' else False
        self._word_length = reg_xml.find("WordLength")
        self._integer_word_length = reg_xml.find("IntegerWordLength")
        self._overflow = True if reg_xml.find("IncludeOverflowStatus") == 'true' else False

    def _copy_values_from_register(self, register):
        self._name = register.name
        self._offset = register.offset
        self._datatype = register.datatype
        self._access_may_timeout = register.access_may_timeout()
        self._internal = register.is_internal()
        self._is_array = register.is_array()

    @property
    def signed(self):
        return self._signed

    @property
    def word_length(self):
        return self._word_length

    @property
    def integer_word_length(self):
        return self._integer_word_length

    @property
    def overflow(self):
        return self._overflow


class Fifo(object):
    def __init__(self, channel_xml):
        self._name = channel_xml.attrib["name"]
        self._number = int(channel_xml.find("Number").text)
        # title() will change SGL/DBL/FXP to Sgl/Dbl/Fxp
        string_datatype = channel_xml.find("DataType").find("SubType").text.title()
        self._datatype = None
        for datatype in DataType:
            if str(datatype) in string_datatype:
                self._datatype = datatype
        assert self._datatype is not None, "FIFO '%s' has unknown type" % self._name

    @property
    def datatype(self):
        """ Returns the datatype string of the FIFO. """
        return self._datatype

    @property
    def number(self):
        """ Returns the FIFO number.
        This number is the unique identifier for the FIFO in this bitfile.
        """
        return self._number

    @property
    def name(self):
        """ Returns the name of the FIFO. """
        return self._name
