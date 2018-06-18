from nifpga.bitfile import (_parse_type,
                            UnsupportedTypeError,
                            ClusterMustContainUniqueNames)
import unittest
import xml.etree.ElementTree as ElementTree

cluster_xml = """
<Cluster>
    <Name>input cluster</Name>
    <TypeList>
        <U16>
            <Name>Input Cluster U16</Name>
        </U16>
        <Cluster>
            <Name>output cluster 2</Name>
            <TypeList>
                <FXP>
                    <Name>Input Cluster FXP 4-bit Signed</Name>
                    <Signed>true</Signed>
                    <WordLength>4</WordLength>
                    <IntegerWordLength>2</IntegerWordLength>
                    <Minimum>-2.000000</Minimum>
                    <Maximum>1.750000</Maximum>
                    <Delta>0.250000</Delta>
                    <IncludeOverflowStatus>true</IncludeOverflowStatus>
                </FXP>
                <U8>
                      <Name>Input Cluster  U8</Name>
                </U8>
                <U64>
                      <Name>Input Cluster U64</Name>
                </U64>
                <I8>
                      <Name>Input Cluster I8</Name>
                </I8>
            </TypeList>
        </Cluster>
        <Array>
            <Name>output cluster array</Name>
            <Size>2</Size>
            <Type>
                <Cluster>
                    <Name/>
                    <TypeList>
                        <FXP>
                            <Name>Input Cluster FXP 64-bit Signed Overflow 2</Name>
                            <Signed>true</Signed>
                            <WordLength>64</WordLength>
                            <IntegerWordLength>32</IntegerWordLength>
                            <Minimum>-2147483648.000000</Minimum>
                            <Maximum>2147483648.000000</Maximum>
                            <Delta>0.000000</Delta>
                            <IncludeOverflowStatus>true</IncludeOverflowStatus>
                        </FXP>
                        <I16>
                            <Name>Input Cluster I16 2</Name>
                        </I16>
                        <FXP>
                            <Name>Input Cluster FXP 32-bit Unsigned Overflow 2</Name>
                            <Signed>false</Signed>
                            <WordLength>32</WordLength>
                            <IntegerWordLength>16</IntegerWordLength>
                            <Minimum>0.000000</Minimum>
                            <Maximum>65535.999985</Maximum>
                            <Delta>0.000015</Delta>
                            <IncludeOverflowStatus>true</IncludeOverflowStatus>
                        </FXP>
                        <Boolean>
                            <Name>Input Cluster Bool 2</Name>
                        </Boolean>
                    </TypeList>
                </Cluster>
            </Type>
        </Array>
        <I32>
            <Name>Input Cluster I32</Name>
        </I32>
        <EnumU16>
            <Name>Input Cluster EnumU8</Name>
            <StringList>
                <String>G</String>
                <String>F</String>
                <String>E</String>
                <String>D</String>
                <String>C</String>
                <String>B</String>
                <String>A</String>
            </StringList>
        </EnumU16>
        <U32>
            <Name>Input Cluster U32</Name>
        </U32>
        <Array>
            <Name>output fxp array</Name>
            <Size>2</Size>
            <Type>
                <FXP>
                    <Name>Input Cluster FXP 13-bit Signed 2</Name>
                    <Signed>true</Signed>
                    <WordLength>16</WordLength>
                    <IntegerWordLength>8</IntegerWordLength>
                    <Minimum>-128.000000</Minimum>
                    <Maximum>127.996094</Maximum>
                    <Delta>0.003906</Delta>
                    <IncludeOverflowStatus>false</IncludeOverflowStatus>
                </FXP>
            </Type>
        </Array>
    </TypeList>
</Cluster>
"""

cluster_with_cfxp_xml = """
<Cluster>
    <Name>input cluster</Name>
    <TypeList>
        <U16>
            <Name>Input Cluster U16</Name>
        </U16>
        <CFXP>
          <Name>Some CFXP Register</Name>
        </CFXP>
    </TypeList>
</Cluster>
"""

cluster_with_multiple_members_with_the_same_name = """
<Cluster>
    <Name>input cluster</Name>
    <TypeList>
        <U16>
            <Name>Name</Name>
        </U16>
        <U32>
          <Name>Name</Name>
        </U32>
    </TypeList>
</Cluster>
"""


class ClusterTests(unittest.TestCase):
    def setUp(self):
        tree = ElementTree.fromstring(cluster_xml)
        self.testRegister = _parse_type(tree)

    def test_cluster_zero_data(self):
        data = self.testRegister.unpack_data(0)
        expected_data = \
            {'Input Cluster U16': 0,
             'output cluster 2': {'Input Cluster FXP 4-bit Signed': (False, 0),
                                  'Input Cluster  U8': 0,
                                  'Input Cluster U64': 0,
                                  'Input Cluster I8': 0},
             'output cluster array': [{'Input Cluster FXP 64-bit Signed Overflow 2': (False, 0),
                                       'Input Cluster I16 2': 0,
                                       'Input Cluster FXP 32-bit Unsigned Overflow 2': (False, 0),
                                       'Input Cluster Bool 2': False},
                                      {'Input Cluster FXP 64-bit Signed Overflow 2': (False, 0),
                                       'Input Cluster I16 2': 0,
                                       'Input Cluster FXP 32-bit Unsigned Overflow 2': (False, 0),
                                       'Input Cluster Bool 2': False}],
             'Input Cluster I32': 0,
             'Input Cluster EnumU8': 0,
             'Input Cluster U32': 0,
             'output fxp array': [0, 0]}
        assert data == expected_data
        packed_data = self.testRegister.pack_data(expected_data, 0)
        assert packed_data == 0

    def test_cluster_values_set_to_1(self):
        actual_data = 389948983317742165538549719682430202967988854558358925786670372898282524917257258819755320125926426630253986178278732200331444480
        data = self.testRegister.unpack_data(actual_data)
        expected_data = \
            {'Input Cluster U16': 1,
             'output cluster 2': {'Input Cluster FXP 4-bit Signed': (False, 1),
                                  'Input Cluster  U8': 1,
                                  'Input Cluster U64': 1,
                                  'Input Cluster I8': 1},
             'output cluster array': [{'Input Cluster FXP 64-bit Signed Overflow 2': (False, 1),
                                       'Input Cluster I16 2': 1,
                                       'Input Cluster FXP 32-bit Unsigned Overflow 2': (False, 1),
                                       'Input Cluster Bool 2': True},
                                      {'Input Cluster FXP 64-bit Signed Overflow 2': (False, 1),
                                       'Input Cluster I16 2': 1,
                                       'Input Cluster FXP 32-bit Unsigned Overflow 2': (False, 1),
                                       'Input Cluster Bool 2': True}],
             'Input Cluster I32': 1,
             'Input Cluster EnumU8': 1,
             'Input Cluster U32': 1,
             'output fxp array': [1, 1]}
        assert data == expected_data
        packed_data = self.testRegister.pack_data(expected_data, 0)
        assert packed_data == actual_data

    def test_cluster_random_data(self):
        actual_data = 650140623102406731927256098101662313669128987008919352549838047850309849438881231947219947572849073945363668902620592607917571840
        data = self.testRegister.unpack_data(actual_data)
        expected_cluster = \
            {'Input Cluster U16': 1,
             'output cluster 2': {'Input Cluster FXP 4-bit Signed': (True, -1),
                                  'Input Cluster  U8': 7,
                                  'Input Cluster U64': 4564564654564654,
                                  'Input Cluster I8': -32},
             'output cluster array': [{'Input Cluster FXP 64-bit Signed Overflow 2': (False, -11111),
                                       'Input Cluster I16 2': -1,
                                       'Input Cluster FXP 32-bit Unsigned Overflow 2': (True, 17.5),
                                       'Input Cluster Bool 2': False},
                                      {'Input Cluster FXP 64-bit Signed Overflow 2': (True, 797979),
                                       'Input Cluster I16 2': 0,
                                       'Input Cluster FXP 32-bit Unsigned Overflow 2': (False, 1000.75),
                                       'Input Cluster Bool 2': True}],
             'Input Cluster I32': 1919919,
             'Input Cluster EnumU8': 0,
             'Input Cluster U32': 4294967295,
             'output fxp array': [0, -1]}
        assert data == expected_cluster
        packed_data = self.testRegister.pack_data(expected_cluster, 0)
        assert packed_data == actual_data

    def test_unsupported_type(self):
        tree = ElementTree.fromstring(cluster_with_cfxp_xml)
        with self.assertRaises(UnsupportedTypeError):
            self.testRegister = _parse_type(tree)

    def test_error_when_multiple_members(self):
        tree = ElementTree.fromstring(cluster_with_multiple_members_with_the_same_name)
        with self.assertRaises(ClusterMustContainUniqueNames):
            self.testRegister = _parse_type(tree)
