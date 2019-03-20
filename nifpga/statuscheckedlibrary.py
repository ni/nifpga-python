from .status import check_status, VersionMismatchError
import ctypes
import ctypes.util

StatusType = ctypes.c_int32


class FunctionInfo(object):
    def __init__(self, function, name, argument_names):
        """
        A struct describing a function to be used in StatusCheckedFunctions.
        Args:
            function (str): the callable function itself
            name (str): A name used to call 'function'
                e.g. "ReadFifoU32".
                See 'StatusCheckedFunctions' to see this parameter's usage
                and how functions are called with this name.
            argument_names (list): a list of the strings of the arguments to
            'function'
                e.g. ["session",
                        "fifo",
                        "data",
                        "number of elements",
                        "timeout ms",
                        "elements remaining"]
                Used for printing helpful messages if the function fails,
                and to get arguments after catching an exception if
                the function fails (e.g. 'e.get_args()["session"]').
        """
        self.function = function
        self.name = name
        self.argument_names = argument_names

    def __str__(self):
        return ("FunctionInfo"
                + "\n\tFunction: %s" % self.function
                + "\n\tName: %s" % self.name
                + "\n\tArguments:"
                + "\n\t\t%s" % "\n\t\t".join(self.argument_names))


class StatusCheckedFunctions(object):
    def __init__(self, function_infos):
        """
        A class to wrap functions that return an Status error code. Each
        function is wrapped with a closure that raises an appropriate derived
        class of Status if the returned error code is non-zero.

        Args:
            function_infos (list): A list of FunctionInfo objects

        The name from each FunctionInfo can be used to call its associated
        function, e.g.::

            def my_raw_func(code)
                return code

            checked_functions = \
                    StatusCheckedFunctions(
                        function_infos=[\
                            FunctionInfo(
                                function=my_raw_func,
                                name="MyFunc",
                                argument_names="code to return")
                        ])

            # This raises FifoTimeoutError with a useful error message
            # mentioning all arguments, such as 'code to return'.
            checked_functions.MyFunc(-50400)

            # Returns with no exceptions thrown
            checked_functions.MyFunc(0)

            # You can also call functions using the bracket operator.
            # This raises FifoTimeoutWarning.
            checked_functions["MyFunc"](50400)
        """
        # dictionary of function names to a closure that wraps a
        # function with a status check
        self._wrapped_functions = {}
        for function_info in function_infos:
            decorator = check_status(function_info.function.__name__,
                                     function_info.argument_names)
            closure = decorator(function_info.function)

            # e.g. "self.Open = closure"
            # So now "<this object>.Open(...)" works
            setattr(self, function_info.name, closure)

            # Store closure this so __getitem__ can provide more convenience
            self._wrapped_functions[function_info.name] = closure

    def __getitem__(self, key):
        """
        Override bracket operator to call wrapped functions.

        For convenience when function names are dynamically built, e.g.,
        makes this work:
            datatype = "U64"
            <this object>['ReadArray%s' % datatype](session, ...)
        """
        return self._wrapped_functions[key]


class NamedArgtype(object):
    def __init__(self, name, argtype):
        """
        A struct of a name and ctypes argtype for a function argument
        to be used in a LibraryFunctionInfo.
        name: e.g. "session"
            Used for printing helpful messages if the function fails,
            and to get arguments after catching an exception if
            the function fails (e.g. 'e.get_args()["session"]').
        argtype: e.g. "ctypes.c_uint32", the ctypes type of the argument
        """
        self.name = name
        self.argtype = argtype


class LibraryFunctionInfo(object):
    def __init__(self, pretty_name, name_in_library, named_argtypes):
        """
        A struct describing a library entry point function to be used
        in StatusCheckedLibrary.
        pretty_name: e.g. "Run"
            A "pretty" name by which a StatusCheckedLibrary object will
            call the function.
        name_in_library: e.g. "NiFpgaDll_Run"
            The name of the actual DLL entry point used to call the function.
        named_argtypes: e.g. [NamedArgtype("session", _SessionType),
                                NamedArgtype("fifo", ctypes.c_uint32)]
            A list of NamedArgtype structs used to call the function.
        """
        self.pretty_name = pretty_name
        self.name_in_library = name_in_library
        self.named_argtypes = named_argtypes


class LibraryNotFoundError(RuntimeError):
    pass


class StatusCheckedLibrary(StatusCheckedFunctions):
    def __init__(self, library_name, library_function_infos):
        """
        Raises exceptions from entry points that return NiFpga_Status codes.

        library_name: e.g. "NiFpga" (libNiFpga.so, NiFpga.dll)
        library_function_infos: a list of library_function_info objects

        Automatically wraps each entry point named in library_function_infos
        with a closure that raises an appropriate derived class of
        Status if the returned error code is non-zero.

        The pretty_name from the LibraryFunctionInfo's passed to the
        constructor can be used to call functions in the library, e.g.:
            cool_library = \
                StatusCheckedLibrary(
                    library_name="CoolLibrary",  # CoolLibrary.dll, libCoolLibrary.so
                    library_function_infos=[\
                        LibraryFunctionInfo(
                            pretty_name="AwesomeFunction",
                            name_in_library="CoolLibraryEntrypoint_AwesomeFunction",
                            named_argtypes=[NamedArgtype("session", ctypes.c_uint32)])
                    ])

            # Both lines below call "CoolLibraryEntrypoint_AwesomeFunction()"
            # from CoolLibrary.dll (or libCoolLibrary.so) with '7' as a uint32_t
            # argument.
            cool_library.AwesomeFunction(7)
            cool_library["AwesomeFunction"](7)
        """
        library = ctypes.util.find_library(library_name)
        if library is None:
            raise LibraryNotFoundError(library_name)
        library = ctypes.cdll.LoadLibrary(library)
        function_infos = []
        for lfi in library_function_infos:
            try:
                func = getattr(library, lfi.name_in_library)  # i.e., dlsym()
                # ctypes functions have special 'argtypes' and 'restype' fields
                # that we set, so ctypes can automatically convert types and knows
                # how to call into the library.
                func.argtypes = [named_argtype.argtype for named_argtype in lfi.named_argtypes]
                # Assume that everything returns an NiFpga_Status
                func.restype = StatusType
            except AttributeError:
                # if we can't find the symbol, instead insert a function that
                # always returns the VersionMismatch error, that way they can
                # use the rest of the API
                def returnsVersionMismatchError(*args, **kwargs):
                    """ Always returns the version mismatch error code. """
                    return VersionMismatchError.CODE
                func = returnsVersionMismatchError
            function_infos.append(
                FunctionInfo(function=func,
                             name=lfi.pretty_name,
                             argument_names=[named_argtype.name for named_argtype in lfi.named_argtypes]))
        super(StatusCheckedLibrary, self).__init__(function_infos)
