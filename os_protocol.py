"""
Compatibility bridge: re-exports everything from os_protocols.
Prevents any ModuleNotFoundError whether imported as 'os_protocol' or 'os_protocols'.
Works seamlessly across Windows, macOS, and Linux.
"""
import sys
import os

_parent_dir = os.path.dirname(os.path.abspath(__file__))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

import os_protocols
from os_protocols import *

# Register in sys.modules so both singular and plural forms resolve to the module
sys.modules['os_protocol'] = os_protocols
sys.modules['os_protocols'] = os_protocols
