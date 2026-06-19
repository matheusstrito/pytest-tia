"""Dynamic dispatch: handlers resolved by a runtime string via getattr.

Which handler `dispatch` calls is decided by data, not by any static
reference — coverage records only the edge that happened to run during
`tia record`. tia flags this file as dynamic and degrades to file-level
selection here instead of pretending its method-level map is complete.
"""

import sys


def handle_greet(name):
    return f"hello {name}"


def handle_shout(name):
    return f"HELLO {name.upper()}"


def dispatch(action, name):
    # getattr by a computed name — the target is invisible to static analysis.
    handler = getattr(sys.modules[__name__], f"handle_{action}")
    return handler(name)
