from aj.api import *
from aj.plugins import PluginManager


info = PluginInfo(
    title='USB Router Status',
    icon='fa fa-router',
    dependencies=[
        PluginDependency('main'),
        PluginDependency('dashboard'),
    ],
)