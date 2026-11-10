"""Deprecation shim for the #78 keyword-only API (0.11.0 warns; 1.0 adds `*` and drops this module)."""

import functools
import inspect
import warnings


def warn_positional(keep, removal="1.0"):
    """Decorate an `__init__` so arguments past the first `keep` (after self) warn when positional.

    Behaviour is otherwise unchanged: the original `__init__` receives the call as
    given. A call that would not bind (too many positional arguments, a parameter
    given both positionally and by keyword, or an unknown keyword) is forwarded
    without a warning so it raises the same TypeError as before. `functools.wraps`
    keeps `__wrapped__`, so `inspect.signature`, `help()` and the generated
    `guide embed` keyword list still see the real parameters.
    """
    def decorate(init):
        code = init.__code__
        names = code.co_varnames[1:code.co_argcount]
        # The bind check below is exact only for plain parameters that all have defaults.
        if (code.co_flags & (inspect.CO_VARARGS | inspect.CO_VARKEYWORDS) or code.co_kwonlyargcount
                or len(init.__defaults__ or ()) != len(names)):
            raise TypeError("warn_positional needs an __init__ of defaulted plain parameters only")
        known = frozenset(names)
        owner = init.__qualname__.rpartition(".")[0]

        @functools.wraps(init)
        def wrapper(self, *args, **kwargs):
            if (keep < len(args) <= len(names) and known.issuperset(kwargs)
                    and not any(name in kwargs for name in names[:len(args)])):
                extras = names[keep:len(args)]
                warnings.warn(
                    f"{owner}(): passing {', '.join(extras)} positionally is deprecated; "
                    f"use keyword arguments ({extras[0]}=...); parameters after "
                    f"{names[keep - 1]} become keyword-only in {removal}",
                    DeprecationWarning, stacklevel=2)
            return init(self, *args, **kwargs)
        return wrapper
    return decorate
