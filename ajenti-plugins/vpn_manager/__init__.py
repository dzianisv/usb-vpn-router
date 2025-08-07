from aj.api import *
from aj.plugins import PluginManager


info = PluginInfo(
    title='VPN Manager',
    icon='fa fa-shield-alt',
    dependencies=[
        PluginDependency('main'),
        PluginDependency('dashboard'),
    ],
)