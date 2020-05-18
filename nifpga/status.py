"""
An set of status exception classes to be used when an NiFpga
function returns either a warning or error status.

Use check_status() to raise an appropriate exception if necessary.

Error and Warning exception class names are auto-generated from the
strings in 'codeToString' in this file.
For example, handle a fatal error like this:

    >>> @check_status('frob', ['foo', 'bar', 'baz'])
    ... def frob(foo, bar, baz):
    ...     return -61141
    ...
    >>> try:
    ...     frob(0, 1, 2)
    ... except FpgaBusyError as e:
    ...     print(e)  # doctest: +NORMALIZE_WHITESPACE
    Error: FpgaBusy (-61141) when calling 'frob' with arguments:
        foo: 0x0
        bar: 0x1
        baz: 0x2

Or handle a warning like this:

    >>> @check_status('frob', ['foo', 'bar', 'baz'])
    ... def frob(foo, bar, baz):
    ...     return 61003
    ...
    >>> with warnings.catch_warnings(record=True) as w:
    ...     frob(0, 1, 2)
    ...     print(w[0].message)  # doctest: +NORMALIZE_WHITESPACE
    Warning: FpgaAlreadyRunning (61003) when calling 'frob' with arguments:
        foo: 0x0
        bar: 0x1
        baz: 0x2

Copyright (c) 2017 National Instruments
"""
import functools
import warnings


def _raise_or_warn_if_nonzero_status(status, function_name, argument_names, *args):
    """
    Helper for the 'check_status' decorator.

    Raises the proper ErrorStatus subclass or warns the proper WarnStatus
    subclass if status is not 0 (success).

    function_name: the name of the function, e.g. "NiFpga_ConfigureFifo"
        Used to make the exception message more useful.
    argument_names: list of names of the arguments to the function
        e.g. ["session", "fifo"]
    args: the arguments that were passed to the function

    'argument_names' and 'args' are used to make the exception message
    more useful, and to find the arguments after catching an exception if
    the function fails (e.g. 'e.get_args()["session"]').
    """
    if status == 0:
        return

    if status in codes_to_exception_classes:
        if status < 0:
            raise codes_to_exception_classes[status](function_name, argument_names, *args)
        else:
            warning = codes_to_exception_classes[status](function_name, argument_names, *args)
            warnings.warn(warning)
    else:
        if status < 0:
            raise UnknownError(status, function_name, argument_names, *args)
        else:
            warnings.warn(UnknownWarning(status, function_name, argument_names, *args))


def check_status(function_name, argument_names):
    """
    Decorator (that takes arguments) to call a function and raise
    an appropriate subclass of Status if the
    returned status is not zero.
    Also validates that the number of parameters passed to the
    function is correct.

    function_name: the name of the function, e.g. "NiFpga_ConfigureFifo"
        Used to make the exception message more useful.
    argument_names: list of names of the arguments to the function
        e.g. ["session", "fifo"]
        Used to make the exception message more useful, and to find the
        arguments after catching an exception if the function fails
        (e.g. 'e.get_args()["session"]').
    """
    def decorator(function):
        @functools.wraps(function)
        def internal(*args):
            if hasattr(function, "argtypes") and len(args) != len(function.argtypes):
                raise TypeError("%s takes exactly %u arguments (%u given)"
                                % (function_name, len(function.argtypes), len(args)))
            status = function(*args)
            _raise_or_warn_if_nonzero_status(status, function_name, argument_names, args)
        return internal
    return decorator


class Status(BaseException):
    def __init__(self, code, code_string, function_name, argument_names,
                 function_args):
        """ Base exception class for when an NiFpga function returns a non-zero
        status.

        Args:
            code (int): e.g. -52000
            code_string (str) : e.g. 'MemoryFull'
            function_name (string): the function that returned the error or
                warning status. e.g. 'NiFpga_ConfigureFifo'
            argument_names (list): a list of the names of the arguments to the
                function. e.g. ["session", "fifo", "requested depth"]
            function_args (tuple) : a tuple of the arguments passed to the
                function. The order of argument_names should correspond to the
                order of function_args. e.g. '(session, fifo, depth)'
        """
        self._code = code
        self._code_string = code_string
        self._function_name = function_name

        self._named_args = []
        for i, arg in enumerate(function_args):
            self._named_args.append(
                {
                    "name": argument_names[i],
                    "value": arg
                })
        # this is also necessary to properly reconstruct the object when
        # passing it between processes
        super(Status, self).__init__(self._code,
                                     self._code_string,
                                     self._function_name,
                                     self._named_args)

    def get_code(self):
        return self._code

    def get_code_string(self):
        return self._code_string

    def get_function_name(self):
        """ Returns a string for the functions name, """
        return self._function_name

    def get_args(self):
        """
        Returns a dictionary of argument names to argument values of
        the function that caused the exception to be raised.

        Returns:
        arg_dict (dictionary): Converts ctypes args to their actual values
        instead of the  ctypes instance. e.g.

        .. code-block:: python

            {
            "session":0x10000L,
            "fifo" : 0x0,
            ...}



        """
        arg_dict = {}
        for arg in self._named_args:
            # ctypes types all have a member named 'value'.
            value = arg["value"].value if hasattr(arg["value"], "value") else arg["value"]
            arg_dict[arg["name"]] = value
        return arg_dict

    def _stringify_arg(self, arg):
        """
        Converts a function argument to a readable string for debugging.

        Stringify ctypes values, instead of the ctypes instance itself.
        Adds single quotes around strings (so it's obvious they are strings).
        Stringify numbers as hex to make it easier to decode
        bit packed sessions, attributes, etc.
        """
        # ctypes types all have a member named 'value'.
        if hasattr(arg, "value"):
            return self._stringify_arg(arg.value)

        if isinstance(arg, str):
            return "'%s'" % arg

        try:
            return hex(arg)
        except TypeError:
            return str(arg)

    def __str__(self):
        """
        Returns the function name, status code, and arguments used.
        Example:

        .. code-block:: python

            Error: FifoTimeout (-50400) when calling 'Dummy Function Name' with
            arguments:
                session: 0xbeef
                fifo: 0xf1f0L
                data: 0xda7aL
                number of elements: 0x100L
                timeout ms: 0x200L
                elements remaining: 0x300L
                a bogus string argument: 'I am a string'
        """
        arg_string = ""
        for arg in self._named_args:
            arg_string += "\n\t%s: %s" % (arg["name"], self._stringify_arg(arg["value"]))
        return "%s: %s (%d) when calling '%s' with arguments:%s" \
            % ("Error" if self._code < 0 else "Warning",
               self._code_string,
               self._code,
               self._function_name,
               arg_string)


class WarningStatus(Status, RuntimeWarning):
    """
    Base warning class for when an NiFpga function returns a warning (> 0)
    status.

    Useful if trying to catch warning and error status exceptions separately
    """
    def __init__(self, code, code_string, function_name, argument_names,
                 function_args):
        super(WarningStatus, self).__init__(code, code_string, function_name,
                                            argument_names, function_args)


class ErrorStatus(Status, RuntimeError):
    """
    Base Error class for when an NiFpga function returns an error (< 0)
    status.

    Useful if trying to catch warning and error status exceptions separately
    """
    def __init__(self, code, code_string, function_name, argument_names,
                 function_args):
        super(ErrorStatus, self).__init__(code, code_string, function_name,
                                          argument_names, function_args)


class UnknownWarning(WarningStatus):
    def __init__(self, code, function_name, argument_names, function_args):
        super(UnknownWarning, self).__init__(code=code,
                                             code_string="Unknown code",
                                             function_name=function_name,
                                             argument_names=argument_names,
                                             function_args=function_args)


class UnknownError(ErrorStatus):
    def __init__(self, code, function_name, argument_names, function_args):
        super(UnknownError, self).__init__(code=code,
                                           code_string="Unknown code",
                                           function_name=function_name,
                                           argument_names=argument_names,
                                           function_args=function_args)


# Define error codes and their names.
# Each code in this list will be codegened into two classes, e.g.:
#   FifoTimeoutError (for code -50400)
#   FifoTimeoutWarning (for code 50400)
error_codes = [
    (-50400, "FifoTimeout"),
    (-50405, "TransferAborted"),
    (-52000, "MemoryFull"),
    (-52003, "SoftwareFault"),
    (-52005, "InvalidParameter"),
    (-52006, "ResourceNotFound"),
    (-52007, "OperationTimedOut"),
    (-52008, "OSFault"),
    (-52010, "ResourceNotInitialized"),
    (-52012, "EndOfData"),
    (-52013, "ObjectNameCollision"),
    (-61003, "FpgaAlreadyRunning"),
    (-61018, "DownloadError"),
    (-61024, "DeviceTypeMismatch"),
    (-61046, "CommunicationTimeout"),
    (-61060, "IrqTimeout"),
    (-61070, "CorruptBitfile"),
    (-61072, "BadDepth"),
    (-61073, "BadReadWriteCount"),
    (-61083, "ClockLostLock"),
    (-61141, "FpgaBusy"),
    (-61200, "FpgaBusyFpgaInterfaceCApi"),
    (-61201, "FpgaBusyScanInterface"),
    (-61202, "FpgaBusyFpgaInterface"),
    (-61203, "FpgaBusyInteractive"),
    (-61204, "FpgaBusyEmulation"),
    (-61211, "ResetCalledWithImplicitEnableRemoval"),
    (-61212, "AbortCalledWithImplicitEnableRemoval"),
    (-61213, "CloseAndResetCalledWithImplicitEnableRemoval"),
    (-61214, "ImplicitEnableRemovalButNotYetRun"),
    (-61215, "RunAfterStoppedCalledWithImplicitEnableRemoval"),
    (-61216, "GatedClockHandshakingViolation"),
    (-61217, "RegionsOutstandingForSession"),
    (-61219, "ElementsNotPermissibleToBeAcquired"),
    (-61252, "FpgaBusyConfiguration"),
    (-61253, "CloseCalledWithResetNotSupported"),
    (-61254, "RunAfterStoppedNotSupported"),
    (-61499, "InternalError"),
    (-63003, "TotalDmaFifoDepthExceeded"),
    (-63033, "AccessDenied"),
    (-63038, "HostVersionMismatch"),
    (-63040, "RpcConnectionError"),
    (-63041, "RpcServerError"),
    (-63042, "NetworkFault"),
    (-63043, "RpcSessionError"),
    (-63044, "RpcServerMissing"),
    (-63045, "FeatureNotSupportedOverRpc"),
    (-63046, "UsingRemoteSessionForLocalTarget"),
    (-63050, "TriggerReserved"),
    (-63051, "TriggerNotReserved"),
    (-63080, "BufferInvalidSize"),
    (-63081, "BufferNotAllocated"),
    (-63082, "FifoReserved"),
    (-63083, "FifoElementsCurrentlyAcquired"),
    (-63084, "MisalignedAccess"),
    (-63085, "ControlOrIndicatorTooLarge"),
    (-63086, "OperationNotSupportedWhileStarted"),
    (-63087, "TypesDoNotMatch"),
    (-63088, "OutOfFifoRegions"),
    (-63101, "BitfileReadError"),
    (-63106, "SignatureMismatch"),
    (-63107, "IncompatibleBitfile"),
    (-63150, "HardwareFault"),
    (-63170, "PowerShutdown"),
    (-63171, "ThermalShutdown"),
    (-63180, "InvalidAliasName"),
    (-63181, "AliasNotFound"),
    (-63182, "InvalidDeviceAccess"),
    (-63183, "InvalidPort"),
    (-63184, "ChildDeviceNotInserted"),
    (-63192, "InvalidResourceName"),
    (-63193, "FeatureNotSupported"),
    (-63194, "VersionMismatch"),
    (-63195, "InvalidSession"),
    (-63196, "InvalidAttribute"),
    (-63198, "OutOfHandles"),
]

# create an exception class for each error code and add to dictionary
# ie FifoTimeoutWarning, FifoTimeoutError
codes_to_exception_classes = {}
_g = globals()
for code, code_string in error_codes:
    # we need introduce a scope, otherwise code, and code_string
    # will all reference the same value.
    def add_classes(code, code_string):
        classname = code_string + 'Error'

        def __init__(self, function_name, argument_names, function_args):
            ErrorStatus.__init__(self,
                                 code=code,
                                 code_string=code_string,
                                 function_name=function_name,
                                 argument_names=argument_names,
                                 function_args=function_args)
        error_class = type(classname, (ErrorStatus,),
                           {'__init__': __init__, 'CODE': code})
        codes_to_exception_classes[code] = error_class
        # copy the exception type into module globals
        _g[error_class.__name__] = error_class

        classname = code_string + 'Warning'

        def __init__(self, function_name, argument_names, function_args):
            WarningStatus.__init__(self,
                                   code=-code,
                                   code_string=code_string,
                                   function_name=function_name,
                                   argument_names=argument_names,
                                   function_args=function_args)
        warning_class = type(classname, (WarningStatus,),
                             {'__init__': __init__, 'CODE': -code})
        codes_to_exception_classes[-code] = warning_class
        # copy the warning type into module globals
        _g[warning_class.__name__] = warning_class

    add_classes(code, code_string)
