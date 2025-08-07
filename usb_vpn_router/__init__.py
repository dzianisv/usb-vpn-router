"""
USB VPN Router - Turn your Orange Pi into a secure USB ethernet gadget with VPN routing.
"""

__version__ = "1.0.0"
__author__ = "USB VPN Router Team"
__email__ = "support@example.com"
__description__ = "USB ethernet gadget with VPN routing and web dashboard"

from .core import USBRouterCore
from .config import RouterConfig

__all__ = ['USBRouterCore', 'RouterConfig']