"""COM apartment helpers for pywin32 calls.

pywin32 dispatch objects (and the cyclic garbage they can form) must be
released *before* ``CoUninitialize``.  Releasing them afterwards crashes the
process with "access violation" while releasing IUnknown, and cyclic COM
references are common enough that we cannot guarantee they are gone.  We
therefore initialise COM for the calling thread and let the thread teardown
release the apartment once every Python object has been destroyed.
"""

from __future__ import annotations

from collections.abc import Callable


def run_in_com[T](fn: Callable[[], T]) -> T:
    """Run *fn* with a COM apartment available on the calling thread."""
    import pythoncom

    try:
        pythoncom.CoInitialize()
    except Exception:
        # RPC_E_CHANGED_MODE: the thread already owns a COM apartment.
        pass
    return fn()
