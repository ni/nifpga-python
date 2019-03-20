import os
import xml.etree.ElementTree as ElementTree
from collections import OrderedDict
from decimal import Decimal
from nifpga import DataType
from numbers import Number
from warnings import warn
import ctypes


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
            try:
                reg = Register(reg_xml)
                assert reg.name not in self._registers, \
                    "One or more registers have the same name '%s', this is not supported" % reg.name
                self._registers[reg.name] = reg
            except UnsupportedTypeError as e:
                warn("Skipping Register: %s, %s" % (reg_xml.find("Name").text, str(e)))
            except ClusterMustContainUniqueNames as e:
                warn("Skipping Register: %s, %s" % (reg_xml.find("Name").text, str(e)))

        self._fifos = {}
        for channel_xml in nifpga.find("DmaChannelAllocationList"):
            try:
                fifo = Fifo(channel_xml)
                self._fifos[fifo.name] = fifo
            except UnsupportedTypeError as e:
                warn("Skipping FIFO: %s, %s" % (fifo.name, str(e)))
            except ClusterMustContainUniqueNames as e:
                warn("Skipping FIFO: %s, %s" % (fifo.name, str(e)))

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


class UnsupportedTypeError(RuntimeError):
    pass


def _parse_type(type_xml):
    """ Parses the XML given and creates the appropriate type class for it.

    Type XML comes in 2 flavors and we need to handle both.
    We will sometimes (for FIFOs) get a non-recursive "SubType" that just
    provides the type and does not name it.  We will never see Clusters or
    Arrays as the "SubType".
    For registers and sometimes FIFOs, we will always get a recursive type
    containing names for all members.
    """
    type = type_xml.find("SubType")
    if type is not None:
        type_name = type.text
        name = ""
    else:
        type_name = type_xml.tag
        name = type_xml.find("Name").text
    if type_name == "Boolean":
        return _Bool(name)
    if type_name == "Cluster":
        return _Cluster(name, type_xml)
    if type_name == "FXP":
        return _FXP(name, type_xml)
    if type_name == "Array":
        return _Array(name, type_xml)
    if type_name == "SGL" or type_name == "DBL":
        return _Float(name, type_name)
    if type_name == "String":
        # Strings are not supported on the FPGA, but show up in error clusters
        return _String(name)
    if type_name == "CFXP":
        raise UnsupportedTypeError("The FPGA Interface Python API does not yet support Complex Fixed Point")
    return _Numeric(name, type_name)


class _BaseType(object):
    def __init__(self, name):
        if name is None:
            self._name = ""
        else:
            self._name = name

    @property
    def name(self):
        return self._name


class _String(_BaseType):
    """ Handles ignoring string types on the FPGA.  Strings are not supported
    on the FPGA, but sometimes show up in error clusters. """
    def __init__(self, name):
        super(_String, self).__init__(name)

    @property
    def datatype(self):
        return DataType.Cluster  # lie and claim we are a cluster so callers don't make assumptions about our contents

    @property
    def size_in_bits(self):
        return 0

    @property
    def is_c_api_type(self):
        return False

    def unpack_data(self, data):
        return ""

    def pack_data(self, data_to_pack, packed_data):
        return packed_data  # don't pack anything for a string


class _Numeric(_BaseType):
    """ Handles packing and unpacking Numerics such as U8, I8, EnumU8, etc"""
    def __init__(self, name, type_name):
        super(_Numeric, self).__init__(name)
        type_name = type_name.replace("Enum", "")
        for datatype in DataType:
            if str(datatype).lower() in type_name.lower():
                self._datatype = datatype
                break
        else:
            raise UnsupportedTypeError("Unrecognized type encountered: %s.  Consider opening an issue on github.com/ni/nifpga" % type_name)
        self._signed = type_name[0].lower() == 'i'
        self._size_in_bits = int(type_name[1:])
        self._data_mask = (1 << self._size_in_bits) - 1
        self._signed_bit_mask = 1 << (self._size_in_bits - 1)
        self._unpack = self._unpack_numeric_signed if self._signed else self._unpack_numeric_unsigned

    def _unpack_numeric_unsigned(self, bits_from_fpga):
        data = bits_from_fpga & self._data_mask
        return data

    def _unpack_numeric_signed(self, bits_from_fpga):
        data = bits_from_fpga & self._data_mask
        if data & self._signed_bit_mask:
            data = data ^ self._data_mask
            data += 1
            data *= -1
        return data

    @property
    def datatype(self):
        return self._datatype

    @property
    def size_in_bits(self):
        return self._size_in_bits

    @property
    def is_c_api_type(self):
        return True

    def unpack_data(self, data):
        return self._unpack(data)

    def pack_data(self, data_to_pack, packed_data):
        packed_data = packed_data << self._size_in_bits
        return packed_data | (data_to_pack & self._data_mask)


class _Float(_BaseType):
    """ Handles packing and unpacking floating point values from the FPGA. """
    def __init__(self, name, type_name):
        super(_Float, self).__init__(name)
        if "SGL" == type_name:
            self._size_in_bits = 32
            self._datatype = DataType.Sgl
        elif "DBL" == type_name:
            self._size_in_bits = 64
            self._datatype = DataType.Dbl
        self._data_mask = (1 << self._size_in_bits) - 1

    @property
    def datatype(self):
        return self._datatype

    @property
    def size_in_bits(self):
        return self._size_in_bits

    @property
    def is_c_api_type(self):
        return True

    def unpack_data(self, data):
        data = data & self._data_mask
        if self._datatype == DataType.Sgl:
            return ctypes.c_float.from_buffer(ctypes.c_uint(data)).value
        if self._datatype == DataType.Dbl:
            return ctypes.c_double.from_buffer(ctypes.c_ulonglong(data)).value

    def pack_data(self, data_to_pack, packed_data):
        if self._datatype == DataType.Sgl:
            bits_to_pack = ctypes.c_uint.from_buffer(ctypes.c_float(data_to_pack)).value
        if self._datatype == DataType.Dbl:
            bits_to_pack = ctypes.c_ulonglong.from_buffer(ctypes.c_double(data_to_pack)).value
        return (packed_data << self._size_in_bits) | bits_to_pack


class _Bool(_BaseType):
    """ Handles packing and unpacking bools. """
    def __init__(self, name):
        super(_Bool, self).__init__(name)

    @property
    def datatype(self):
        return DataType.Bool

    @property
    def size_in_bits(self):
        return 1

    @property
    def is_c_api_type(self):
        return True

    def unpack_data(self, data):
        return bool(data & 1)

    def pack_data(self, data_to_pack, packed_data):
        bit_to_pack = 1 if data_to_pack else 0
        return (packed_data << 1) | bit_to_pack


class ClusterMustContainUniqueNames(RuntimeError):
    """ For the FPGA Interface Python API, we have chosen to represent clusters
    as dictionaries.  This has a relatively straight forward conversion, but
    requires that all members of the cluster have a unique label."""
    pass


class _Cluster(_BaseType):
    """ Handles packing and unpacking clusters. """
    def __init__(self, name, type_xml):
        super(_Cluster, self).__init__(name)
        self._datatype = DataType.Cluster
        member_types = type_xml.find("TypeList")
        self._children = []
        names = set()
        for child in list(member_types):
            child_type = _parse_type(child)
            if child_type.name in names:
                raise ClusterMustContainUniqueNames("Cluster: '%s', contains multiple members with the name: '%s'" % (self._name, child_type.name))
            names.add(child_type.name)
            self._children.append(_parse_type(child))
        self._size_in_bits = sum(child.size_in_bits for child in self._children)

    @property
    def datatype(self):
        return DataType.Cluster

    @property
    def size_in_bits(self):
        return self._size_in_bits

    @property
    def is_c_api_type(self):
        return False

    def _unpack_data_recursive(self, data, result, child_iter):
        """ Clusters are stored in the correct order in the blob, but since we
        parse the blob from least significant to most, we are parsing the clusters
        out backwards. So parse out the data backwards going down the stack and
        add it to the dict going back up the stack. This way we insert into the
        OrderedDict in the correct order"""
        child = next(child_iter, None)
        if child is None:
            return
        current_result = child.unpack_data(data)
        data >>= child.size_in_bits
        self._unpack_data_recursive(data, result, child_iter)
        result[child.name] = current_result

    def unpack_data(self, data):
        result = OrderedDict()
        self._unpack_data_recursive(data, result, reversed(self._children))
        return result

    def pack_data(self, data_to_pack, packed_data):
        i = 0
        for child in self._children:
            packed_data = child.pack_data(data_to_pack[child.name], packed_data)
            i += 1
        return packed_data


class _Array(_BaseType):
    """ Handles packing and unpacking arrays. """
    def __init__(self, name, type_xml):
        super(_Array, self).__init__(name)
        self._subtype = _parse_type(list(type_xml.find("Type"))[0])
        self._size = int(type_xml.find("Size").text)
        self._size_in_bits = self._subtype.size_in_bits * self._size

    @property
    def datatype(self):
        return self._subtype.datatype

    @property
    def size(self):
        return self._size

    @property
    def size_in_bits(self):
        return self._size_in_bits

    @property
    def is_c_api_type(self):
        return self._subtype.is_c_api_type

    def unpack_data(self, data):
        results = [0] * self._size
        for i in range(0, self._size):
            results[i] = self._subtype.unpack_data(data)
            data = data >> self._subtype.size_in_bits
        # Arrays are packed in order, which means that as we are grabbing out values
        # and shifting data, we are grabbing from the back of the array.  So reverse it.
        results.reverse()
        return results

    def pack_data(self, data_to_pack, packed_data):
        for i in range(0, self._size):
            packed_data = self._subtype.pack_data(data_to_pack[i], packed_data)
        return packed_data


class _FXP(_BaseType):
    """ Handles packing and unpacking FXP values from the FPGA. """
    def __init__(self, name, type_xml):
        super(_FXP, self).__init__(name)
        self._datatype = DataType.Fxp
        signed_tag = type_xml.find("Signed")
        if signed_tag is None:
            raise UnsupportedTypeError("Unsupported FXP type encountered. This bitfile "
                                       "was likely compiled with LabVIEW Communications 2.0. "
                                       "Recompile with LabVIEW Communications 2.1 or later.")
        self._signed = True if signed_tag.text.lower() == 'true' else False
        overflow_enabled_xml = type_xml.find("IncludeOverflowStatus")
        if overflow_enabled_xml is not None:
            self._overflow_enabled = True if overflow_enabled_xml.text.lower() == 'true' else False
        else:
            self._overflow_enabled = False
        self._word_length = int(type_xml.find("WordLength").text)
        self._integer_word_length = int(type_xml.find("IntegerWordLength").text)
        # Delta, min, and max exist in the XML, but are incorrect...
        # So we calculate them here instead.
        self._delta = self._calculate_delta()
        self._minimum = self._calculate_minimum()
        self._maximum = self._calculate_maximum()
        self._size_in_bits = self._calculate_size_in_bits()
        self._data_mask = (1 << self._size_in_bits) - 1
        self._word_length_mask = (1 << self._word_length) - 1
        if self._signed:
            self._signed_bit_mask = 1 << (self._word_length - 1)

    @property
    def datatype(self):
        return self._datatype

    @property
    def size_in_bits(self):
        return self._size_in_bits

    @property
    def is_c_api_type(self):
        return False

    def _calculate_delta(self):
        """ Determines the fixed point delta value, the value of the register
        is only allowed to be an integer multiple of the delta. For example if
        delta is 1, then it is impossible to represent a fraction.
        The value persisted in the bitfile for delta is not always correct,
        therefore we must calculate it manually.
        """
        return Decimal(2**(self._integer_word_length - self._word_length))

    def _calculate_minimum(self):
        """ Determines the minimum possible value that can be represented with
        the given fixed point register. The value persisted in the bitfile for
        the minimum value is not always accurate, therefore we must calculate
        it manually.
        """
        if self._signed:
            magnitude_bits = self._word_length - 1
            return -1 * (2**(magnitude_bits) * self._delta)
        else:
            return 0

    def _calculate_maximum(self):
        """ Determines the minimum possible value that can be represented with
        the given fixed point register.The value persisted in the bitfile for
        the maximum value is not always accurate, therefore we must calculate
        it manually.
        """
        if self._signed:
            magnitude_bits = self._word_length - 1
        else:
            magnitude_bits = self._word_length
        return (2**(magnitude_bits) - 1) * self._delta

    def _calculate_size_in_bits(self):
        """ Fixed point values are transfered to the driver as an array of U32
        The length is between 1 and 3 determined by the word length (includes
        the signed bit) plus the include_overflow_status_enable bit.
        """
        bits_required = self._word_length
        if self._overflow_enabled:
            """ If overflow status is enabled we need an extra bit. """
            bits_required += 1
        return bits_required

    def unpack_data(self, data):
        """ This method converts value from hardware and returns the respective
        decimal value or a tuple with the overflow status and the decimal
        value.
        """
        data = data & self._data_mask
        overflow = None
        if self._overflow_enabled:
            overflow = self._get_overflow_value(data)
            data = self._remove_overflow_bit(data)

        if self._signed:
            data = self._integer_twos_comp(data)
        decimal_value = data * self._delta
        if self._overflow_enabled:
            return (overflow, decimal_value)
        else:
            return decimal_value

    def _get_overflow_value(self, data):
        """ Mask out all the data within the word length, leaving the overflow
        bit. If the result after masking the the word portion of the fixed
        point is nonzero that indicates the data read has overflowed. """
        mask = 2**(self._word_length)
        if data & mask > 0:
            return True
        return False

    def _remove_overflow_bit(self, data):
        """ This helper method masks out all bits not inside the word length,
        ultimately returning a value of data without the overflow bit. """
        return data & self._word_length_mask

    def _integer_twos_comp(self, data):
        """ Checks the signed bit and determines if the value is negative, If
        so take the twos complement of the input."""
        if data & self._signed_bit_mask > 0:
            data = data ^ self._word_length_mask
            data += 1
            data *= -1
        return data

    def pack_data(self, data_to_pack, packed_data):
        (overflow, data) = self._validate_and_parse_user_input(data_to_pack)

        fxp_representation = 0
        if data < self._minimum:
            fxp_representation = self._convert_value_to_fxp(self._minimum)
            self.warn_coerced_data()
        elif data > self._maximum:
            fxp_representation = self._convert_value_to_fxp(self._maximum)
            self.warn_coerced_data()
        else:
            fxp_representation = self._convert_value_to_fxp(data)

        if self._signed and data < 0:
            fxp_representation = self._integer_twos_comp(fxp_representation)

        if overflow:
            fxp_representation += 2**(self._word_length)

        packed_data <<= self._size_in_bits
        packed_data |= fxp_representation
        return packed_data

    def _validate_and_parse_user_input(self, user_input):
        overflow = None
        data = None
        if self._overflow_enabled:
            try:
                (overflow, data) = user_input
            except TypeError:
                """ If the user does not input any overflow status, eat the
                exception and use default value of False. """
                overflow = False
                data = user_input
            assert isinstance(overflow, bool)
        else:
            data = user_input
        assert isinstance(data, Number)
        return (overflow, data)

    def _convert_value_to_fxp(self, data):
        calculated_fxp = Decimal(data) / Decimal(self._delta)
        fxp_representation = int(calculated_fxp)
        """ If the result of the division is not an integer, we lost some of
        the input data. In this case we warn the user that we had to coerce the
        value to the nearest fixed point representation. """
        if fxp_representation != calculated_fxp:
            self.warn_coerced_data()
        return fxp_representation

    def warn_coerced_data(self):
        warn("The inputed value was not able to be converted to FXP, without coercion. ")


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
        self._type = _parse_type(list(datatype)[0])
        if self.is_array():
            self._num_elements = self._type.size
        else:
            self._num_elements = 1

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
        return self._type.datatype

    @property
    def type(self):
        return self._type

    def is_array(self):
        """ Returns whether or not this Register is an array """
        return isinstance(self._type, _Array)

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
        return ("Register '%s'\n" % self._name
                + "\tType: %s\n" % self._datatype
                + "\tNum Elements: %d\n" % len(self)
                + "\tOffset: %d\n" % self._offset)


def _is_not_power_of_2(value):
    return value & (value - 1) != 0


class Fifo(object):
    def __init__(self, channel_xml):
        self._name = channel_xml.attrib["name"]
        self._number = int(channel_xml.find("Number").text)
        datatype_xml = channel_xml.find("DataType")
        if datatype_xml.find("SubType") is not None:
            self._type = _parse_type(datatype_xml)
        else:
            self._type = _parse_type(list(datatype_xml)[0])
        transfer_size_bytes_xml = channel_xml.find("TransferSizeBytes")
        # only newer XML that supports composite types will have TransferSizeBytes
        if transfer_size_bytes_xml is not None:
            self._transfer_size_bytes = int(transfer_size_bytes_xml.text)
            # As of 2018 transfer size must be a power of two.
            if _is_not_power_of_2(self._transfer_size_bytes):
                raise UnsupportedTypeError("This FIFO is incompatible with this version of 'nifpga'.  Upgrade to the latest version or open an issue on github.")
        else:
            if self._type.datatype is DataType.Fxp:
                self._transfer_size_bytes = 8
            else:
                self._transfer_size_bytes = ctypes.sizeof(self._type.datatype._return_ctype())

    @property
    def datatype(self):
        """ Returns the datatype string of the FIFO. """
        return self._type.datatype

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

    @property
    def type(self):
        return self._type

    @property
    def transfer_size_bytes(self):
        """ The size of one FIFO element in bytes. """
        return self._transfer_size_bytes

    def is_fxp(self):
        return isinstance(self._type, _FXP)

    def is_composite(self):
        return isinstance(self._type, _Cluster) or isinstance(self._type, _Array)
