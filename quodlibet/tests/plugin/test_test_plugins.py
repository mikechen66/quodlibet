# Copyright 2013 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from tests.plugin import PluginTestCase


class TTestPlugins(PluginTestCase):

    def test_pickle(self):
        plugin = self.plugins["pickle_plugin"].cls
        instance = plugin()
        instance.enabled()
        instance.disabled()
