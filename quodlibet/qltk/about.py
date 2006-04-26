# -*- coding: utf-8 -*-
# Copyright 2004-2005 Joe Wreschnig, Michael Urman, Iñigo Serna
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation
#
# $Id$

import gst
import gtk

import const
import formats

def _fver(tup):
    return ".".join(map(str, tup))

class AboutQuodLibet(gtk.AboutDialog):
    def __init__(self, parent, player):
        super(AboutQuodLibet, self).__init__()
        self.set_name("Quod Libet")
        self.set_version(const.VERSION)
        self.set_authors(const.AUTHORS)
        fmts = ", ".join(formats.modules)
        text = []
        text.append(_("Supported formats: %s") % fmts)
        text.append(_("Audio device: %s") % player.name)
        text.append("GTK+: %s / PyGTK: %s" %(
            _fver(gtk.gtk_version), _fver(gtk.pygtk_version)))
        text.append("GStreamer: %s / PyGSt: %s" %(
            _fver(gst.version()), _fver(gst.pygst_version)))
        self.set_comments("\n".join(text))
        # Translators: Replace this with your name/email to have it appear
        # in the "About" dialog.
        self.set_translator_credits(_('translator-credits'))
        self.set_website("http://www.sacredchao.net/quodlibet")
        self.set_copyright(
            "Copyright © 2004-2006 Joe Wreschnig, Michael Urman, & others\n"
            "<quodlibet@lists.sacredchao.net>")
        self.child.show_all()

def show(window, player):
    about = AboutQuodLibet(window, player)
    about.run()
    about.destroy()
