#!/usr/bin/env python

# Copyright 2004 Joe Wreschnig, Michael Urman
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# $Id$

VERSION = "0.4"

import os, sys

# This object communicates with the playing thread. It's the only way
# the playing thread talks to the UI, so replacing this with something
# using e.g. Curses would change the UI. The converse is not true. Many
# parts of the UI talk to the player.
#
# The single instantiation of this is widgets.wrap, created at startup.
class GTKSongInfoWrapper(object):
    def __init__(self):
        self.image = widgets["albumcover"]
        self.iframe = widgets["iframe"]
        self.text = widgets["currentsong"]
        self.pos = widgets["song_pos"]
        self.timer = widgets["song_timer"]
        self.button = widgets["play_button"]
        self.but_image = widgets["play_image"]
        self.playing = gtk.gdk.pixbuf_new_from_file("pause.png")
        self.paused = gtk.gdk.pixbuf_new_from_file("play.png")

        try:
            import statusicon
            p = gtk.gdk.pixbuf_new_from_file_at_size("quodlibet.png", 16, 16)
            self.icon = statusicon.StatusIcon(p)
            self.icon.connect("activate", self._toggle_window, ())
            print _("Initialized status icon.")
        except:
            print _("W: Failed to initialize status icon.")
            self.icon = None

        try:
            import mmkeys
            self.keys = mmkeys.MmKeys()
            self.keys.connect("mm_prev", self._previous)
            self.keys.connect("mm_next", self._next)
            self.keys.connect("mm_playpause", self._playpause)
            print _("Initialized multimedia key support.")
        except:
            print _("W: Failed to initialize multimedia key support.")

        self._time = (0, 1)
        gtk.timeout_add(300, self._update_time)

    def _previous(*args): player.playlist.previous()
    def _next(*args): player.playlist.next()
    def _playpause(*args): player.playlist.paused ^= True

    def _toggle_window(self, *args):
        w = widgets["main_window"]
        if w.get_property('visible'):
            self.window_pos = w.get_position()
            w.hide()
        else:
            w.move(*self.window_pos)
            w.show()

    # The pattern of getting a call from the playing thread and then
    # queueing an idle function prevents thread-unsafety in GDK.

    # The pause toggle was clicked.
    def set_paused(self, paused):
        gtk.idle_add(self._update_paused, paused)

    def _update_paused(self, paused):
        if paused:
            self.but_image.set_from_pixbuf(self.paused)
            widgets["play_menu"].child.set_text("_Play song")
        else:
            self.but_image.set_from_pixbuf(self.playing)
            widgets["play_menu"].child.set_text("_Pause song")
        widgets["play_menu"].child.set_use_underline(True)

    # The player told us about a new time.
    def set_time(self, cur, end):
        self._time = (cur, end)

    def _update_time(self):
        cur, end = self._time
        self.pos.set_value(cur)
        self.timer.set_text("%d:%02d/%d:%02d" %
                            (cur / 60000, (cur % 60000) / 1000,
                             end / 60000, (end % 60000) / 1000))
        return True

    # A new song was selected, or the next song started playing.
    def set_song(self, song, player):
        gtk.idle_add(self._update_song, song, player)

    def missing_song(self, song):
        gtk.idle_add(self._missing_song, song)

    def _missing_song(self, song):
        path = (player.playlist.get_playlist().index(song),)
        iter = widgets.songs.get_iter(path)
        widgets.songs.remove(iter)
        statusbar = widgets["statusbar"]
        statusbar.set_text(_("Could not play %s.") % song['=filename'])
        library.remove(song)
        player.playlist.remove(song)

    # Called when no cover is available, or covers are off.
    def disable_cover(self):
        self.iframe.hide()

    # Called when a covers are turned on; an image may not be available.
    def enable_cover(self):
        if self.image.get_pixbuf():
            self.iframe.show()

    def update_markup(self, song):
        if song:
            self.text.set_markup(song.to_markup())
            if self.icon: self.icon.set_tooltip(song.to_short(), "magic")
        else:
            s = _("Not playing")
            self.text.set_markup("<span size='xx-large'>%s</span>" % s)
            if self.icon: self.icon.set_tooltip(s, "magic")

    def scroll_to_current(self):
        song = CURRENT_SONG[0]
        if song:
            try: path = (player.playlist.get_playlist().index(song),)
            except ValueError: pass
            else: widgets["songlist"].scroll_to_cell(path)

    def _update_song(self, song, player):
        for wid in ["web_button", "next_button", "play_button", "prop_menu",
                    "play_menu", "jump_menu", "next_menu", "prop_button"]:
            widgets[wid].set_sensitive(bool(song))
        if song:
            self.pos.set_range(0, player.length)
            self.pos.set_value(0)

            cover = song.find_cover()
            if cover:
                try:
                    p = gtk.gdk.pixbuf_new_from_file_at_size(cover, 100, 100)
                except:
                    self.image.set_from_pixbuf(None)
                    self.disable_cover()
                else:
                    self.image.set_from_pixbuf(p)
                    if config.state("cover"): self.enable_cover()
                    
            else:
                self.image.set_from_pixbuf(None)
                self.disable_cover()
            self.update_markup(song)
        else:
            self.image.set_from_pixbuf(None)
            self.pos.set_range(0, 1)
            self.pos.set_value(0)
            self._time = (0, 1)
            self.update_markup(None)

        # Update the currently-playing song in the list by bolding it.
        last_song = CURRENT_SONG[0]
        CURRENT_SONG[0] = song
        col = len(HEADERS)
        def update_if_last_or_current(model, path, iter):
            if model[iter][col] is song:
                model[iter][col + 1] = 700
                model.row_changed(path, iter)
            elif model[iter][col] is last_song:
                model[iter][col + 1] = 400
                model.row_changed(path, iter)
        widgets.songs.foreach(update_if_last_or_current)
        if config.state("jump"): self.scroll_to_current()
        gc.collect()
        return False

# Make a standard directory-chooser, and return the filenames and response.
def make_chooser(title, initial_dir = None):
    chooser = gtk.FileChooserDialog(
        title = title,
        parent = widgets["main_window"],
        action = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                   gtk.STOCK_OPEN, gtk.RESPONSE_OK))
    if initial_dir: chooser.set_current_folder(initial_dir)
    chooser.set_local_only(True)
    chooser.set_select_multiple(True)
    resp = chooser.run()
    fns = chooser.get_filenames()
    chooser.destroy()
    return resp, fns

# Display the error dialog.
def make_error(title, description, buttons):
    text = "<span size='xx-large'>%s</span>\n\n%s" % (
        util.escape(title), util.escape(description))
    dialog = gtk.MessageDialog(widgets["main_window"],
                               gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                               gtk.MESSAGE_ERROR,
                               buttons)
    dialog.set_markup(text)
    dialog.show_all()
    return dialog

# Standard Glade widgets wrapper.
class Widgets(object):
    def __init__(self, file):
        self.widgets = gtk.glade.XML("quodlibet.glade",
                                     domain = gettext.textdomain())
        self.widgets.signal_autoconnect(GladeHandlers.__dict__)

    def __getitem__(self, key):
        return self.widgets.get_widget(key)

# Glade-connected handler functions.
class GladeHandlers(object):
    last_dir = os.environ["HOME"]

    def gtk_main_quit(*args): gtk.main_quit()

    def save_size(widget, *args):
        old_size = map(int, config.get("memory", "size").split(" "))
        new_size = widget.get_size()
        if old_size != new_size:
            config.set("memory", "size", " ".join(map(str, new_size)))

    def open_website(button):
        song = CURRENT_SONG[0]
        site = song.website().replace("\\", "\\\\").replace("\"", "\\\"")
        for s in ["sensible-browser"]+os.environ.get("BROWSER","").split(":"):
            if util.iscommand(s):
                if "%s" in s:
                    s = s.replace("%s", '"' + site + '"')
                    s = s.replace("%%", "%")
                else: s += " \"%s\"" % site
                print _("Opening web browser: %s") % s
                if os.system(s + " &") == 0: break
        else:
            d = make_error(_("Unable to start a web browser"),
                           _("A web browser could not be found. Please set "
                             "your $BROWSER variable, or make sure "
                             "/usr/bin/sensible-browser exists."),
                           gtk.BUTTONS_OK)
            r = d.run()
            d.destroy()

    def play_pause(button):
        player.playlist.paused ^= True

    def jump_to_current(*args):
        widgets.wrap.scroll_to_current()

    def next_song(*args):
        player.playlist.next()

    def previous_song(*args):
        player.playlist.previous()

    def toggle_repeat(button):
        player.playlist.repeat = button.get_active()

    def show_about(menuitem):
        widgets["about_window"].set_transient_for(widgets["main_window"])
        widgets["about_window"].show()

    def close_about(*args):
        widgets["about_window"].hide()
        return True

    def toggle_shuffle(button):
        player.playlist.shuffle = button.get_active()

    def seek_slider(slider, v):
        gtk.idle_add(player.playlist.seek, v)

    # Set up the preferences window.
    def open_prefs(*args):
        widgets["prefs_window"].set_transient_for(widgets["main_window"])
        # Fill in the general checkboxes.
        widgets["cover_t"].set_active(config.state("cover"))
        widgets["color_t"].set_active(config.state("color"))
        widgets["jump_t"].set_active(config.state("jump"))
        old_h = HEADERS[:]

        # Fill in the header checkboxes.
        widgets["disc_t"].set_active("=d" in old_h)
        widgets["track_t"].set_active("=#" in old_h)
        widgets["album_t"].set_active("album" in old_h)
        widgets["artist_t"].set_active("artist" in old_h)
        widgets["genre_t"].set_active("genre" in old_h)
        widgets["year_t"].set_active("year" in old_h)
        widgets["version_t"].set_active("version" in old_h)
        widgets["performer_t"].set_active("performer" in old_h)
        widgets["filename_t"].set_active("=basename" in old_h)

        # Remove the standard headers, and put the rest in the list.
        for t in ["=d", "=#", "album", "artist", "genre", "year", "version",
                  "performer", "title", "=basename"]:
            try: old_h.remove(t)
            except ValueError: pass
        widgets["extra_headers"].set_text(" ".join(old_h))

        # Fill in the scanned directories.
        widgets["scan_opt"].set_text(config.get("settings", "scan"))
        widgets["split_entry"].set_text(config.get("settings", "splitters"))
        widgets["prefs_window"].show()

    def set_headers(*args):
        # Based on the state of the checkboxes, set up new column headers.
        new_h = []
        if widgets["disc_t"].get_active(): new_h.append("=d")
        if widgets["track_t"].get_active(): new_h.append("=#")
        new_h.append("title")
        if widgets["version_t"].get_active(): new_h.append("version")
        if widgets["album_t"].get_active(): new_h.append("album")
        if widgets["artist_t"].get_active(): new_h.append("artist")
        if widgets["performer_t"].get_active(): new_h.append("performer")
        if widgets["year_t"].get_active(): new_h.append("year")
        if widgets["genre_t"].get_active(): new_h.append("genre")
        if widgets["filename_t"].get_active(): new_h.append("=basename")
        new_h.extend(widgets["extra_headers"].get_text().split())
        HEADERS[:] = new_h
        config.set("settings", "headers", " ".join(HEADERS))
        set_column_headers(widgets["songlist"])

    def change_scan(*args):
        config.set("settings", "scan", widgets["scan_opt"].get_text())

    def prefs_change_split(*args):
        config.set("settings", "splitters", widgets["split_entry"].get_text())

    def toggle_color(toggle):
        config.set("settings", "color", str(bool(toggle.get_active())))

    def toggle_cover(toggle):
        config.set("settings", "cover", str(bool(toggle.get_active())))
        if config.state("cover"): widgets.wrap.enable_cover()
        else: widgets.wrap.disable_cover()

    def toggle_jump(toggle):
        config.set("settings", "jump", str(bool(toggle.get_active())))

    def select_scan(*args):
        resp, fns = make_chooser(_("Select Directories"), os.environ["HOME"])
        if resp == gtk.RESPONSE_OK:
            widgets["scan_opt"].set_text(":".join(fns))

    def prefs_closed(*args):
        widgets["prefs_window"].hide()
        config_fn = os.path.join(os.environ["HOME"], ".quodlibet", "config")
        util.mkdir(os.path.dirname(config_fn))
        save_config()
        return True

    def select_song(tree, indices, col):
        iter = widgets.songs.get_iter(indices)
        song = widgets.songs.get_value(iter, len(HEADERS))
        player.playlist.go_to(song)
        player.playlist.paused = False

    def open_chooser(*args):
        resp, fns = make_chooser(_("Add Music"), GladeHandlers.last_dir)
        if resp == gtk.RESPONSE_OK:
            progress = widgets["throbber"]
            label = widgets["found_count"]
            wind = widgets["scan_window"]
            wind.set_transient_for(widgets["main_window"])
            wind.show()
            for added, changed in library.scan(fns):
                progress.pulse()
                label.set_text("%d new songs found" % added)
                while gtk.events_pending(): gtk.main_iteration()
            wind.hide()
            player.playlist.refilter()
            refresh_songlist()
        if fns: GladeHandlers.last_dir = fns[0]

    def update_volume(slider):
        player.device.volume = int(slider.get_value())

    def songs_button_press(view, event):
        if event.button != 3:
            return False
        x, y = map(int, [event.x, event.y])
        try: path, col, cellx, celly = view.get_path_at_pos(x, y)
        except TypeError: return True
        view.grab_focus()
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            view.set_cursor(path, col, 0)
        widgets["songs_popup"].popup(None,None,None, event.button, event.time)
        return True

    def songs_popup_menu(view):
        widgets["songs_popup"].popup(None, None, None, 1, 0)

    def song_col_filter(item):
        view = widgets["songlist"]
        path, col = view.get_cursor()
        coln = view.get_columns().index(col)
        header = HEADERS[coln]
        filter_on_header(header)

    def artist_filter(item): filter_on_header('artist')
    def album_filter(item): filter_on_header('album')

    def remove_song(item):
        view = widgets["songlist"]
        selection = widgets["songlist"].get_selection()
        model, rows = selection.get_selected_rows()
        rows.sort()
        rows.reverse()
        for row in rows:
            song = model[row][len(HEADERS)]
            iter = widgets.songs.get_iter(row)
            widgets.songs.remove(iter)
            library.remove(song)
            player.playlist.remove(song)

    def current_song_prop(*args):
        song = CURRENT_SONG[0]
        if song:
            l = widgets["songlist"]
            try: path = (player.playlist.get_playlist().index(song),)
            except ValueError: ref = None
            else: ref = gtk.TreeRowReference(l.get_model(), path)
            make_song_properties([(song, ref)])
            
    def song_properties(item):
        view = widgets["songlist"]
        selection = view.get_selection()
        model, rows = selection.get_selected_rows()
        songrefs = [ (model[row][len(HEADERS)],
                      gtk.TreeRowReference(model, row)) for row in rows]
        make_song_properties(songrefs)

class MultiInstanceWidget(object):

    def __init__(self, file=None, widget=None):
        self.widgets = gtk.glade.XML(file or "quodlibet.glade", widget)
        self.widgets.signal_autoconnect(self)
        menu = gtk.glade.XML(file or "quodlibet.glade", "props_popup")
        menu.signal_autoconnect(self)
        self.menu = menu.get_widget("props_popup")
        self.menu_w = menu

    def songprop_close(self, *args):
        self.fview.set_model(None)
        self.fbasemodel.clear()
        self.fmodel.clear_cache()
        self.model.clear()
        self.window.destroy()
        self.menu.destroy()
        del(self.songrefs)

    def songprop_save_click(self, button):
        updated = {}
        deleted = {}
        added = {}
        def create_property_dict(model, path, iter):
            row = model[iter]
            # Edited, and or and not Deleted
            if row[2] and not row[4]:
                if row[5] is not None:
                    updated[row[0]] = (util.decode(row[1]),
                                       util.decode(row[5]))
                else:
                    added.setdefault(row[0], [])
                    added[row[0]].append(util.decode(row[1]))
            if row[2] and row[4]:
                if row[5] is not None: deleted[row[0]] = util.decode(row[5])
        self.model.foreach(create_property_dict)

        progress = widgets["writing_progress"]
        label = widgets["saved_count"]
        widgets["write_window"].set_transient_for(self.window)
        widgets["write_window"].show()
        saved = 0
        progress.set_fraction(0.0)
        while gtk.events_pending(): gtk.main_iteration()
        for song, ref in self.songrefs:
            changed = False
            for key, (new_value, old_value) in updated.iteritems():
                new_value = util.unescape(new_value)
                if song.can_change(key):
                    if old_value is None: song.add(key, new_value)
                    else: song.change(key, old_value, new_value)
                    changed = True
            for key, values in added.iteritems():
                for value in values:
                    value = util.unescape(value)
                    if song.can_change(key):
                        song.add(key, value)
                        changed = True
            for key, value in deleted.iteritems():
                value = util.unescape(value)
                if song.can_change(key) and key in song:
                    song.remove(key, value)
                    changed = True

            if changed and ref:
                path = ref.get_path()
                song.write()
                if path is not None:
                    row = widgets.songs[path]
                    for i, h in enumerate(HEADERS): row[i] = song.get(h, "")

            saved += 1
            progress.set_fraction(saved / float(len(self.songrefs)))
            label.set_text(_("%d/%d songs saved")%(saved, len(self.songrefs)))
            while gtk.events_pending(): gtk.main_iteration()

        widgets["write_window"].hide()
        self.save.set_sensitive(False)
        self.revert.set_sensitive(False)
        self.fill_property_info()
        widgets.wrap.update_markup(CURRENT_SONG[0])

    def songprop_revert_click(self, button):
        self.save.set_sensitive(False)
        self.revert.set_sensitive(False)
        self.fill_property_info()

    def songprop_toggle(self, renderer, path, model):
        row = model[path]
        row[2] = not row[2] # Edited
        self.save.set_sensitive(True)
        self.revert.set_sensitive(True)

    def split_into_list(self, *args):
        model, iter = self.view.get_selection().get_selected()
        row = model[iter]
        spls = config.get("settings", "splitters")
        vals = util.split_value(util.unescape(row[1]), spls)
        if vals[0] != util.unescape(row[1]):
            row[1] = util.escape(vals[0])
            row[2] = True
            for val in vals[1:]: self.add_new_tag(row[0], val)

    def split_title(self, *args):
        model, iter = self.view.get_selection().get_selected()
        row = model[iter]
        spls = config.get("settings", "splitters")
        title, versions = util.split_title(util.unescape(row[1]), spls)
        if title != util.unescape(row[1]):
            row[1] = util.escape(title)
            row[2] = True
            for val in versions: self.add_new_tag("version", val)

    def split_album(self, *args):
        model, iter = self.view.get_selection().get_selected()
        row = model[iter]
        album, disc = util.split_album(util.unescape(row[1]))
        if album != util.unescape(row[1]):
            row[1] = util.escape(album)
            row[2] = True
            self.add_new_tag("discnumber", disc)

    def split_people(self, tag):
        model, iter = self.view.get_selection().get_selected()
        row = model[iter]
        spls = config.get("settings", "splitters")
        person, others = util.split_people(util.unescape(row[1]), spls)
        if person != util.unescape(row[1]):
            row[1] = util.escape(person)
            row[2] = True
            for val in others: self.add_new_tag(tag, val)

    def split_performer(self, *args): self.split_people("performer")
    def split_arranger(self, *args): self.split_people("arranger")

    def songprop_edit(self, renderer, path, new, model, colnum):
        row = model[path]
        date = sre.compile("^\d{4}(-\d{2}-\d{2})?$")
        if row[0] == "date" and not date.match(new):
            msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL,
                                    gtk.MESSAGE_WARNING,
                                    gtk.BUTTONS_OK)
            msg.set_markup(_("Invalid date: <b>%s</b>.\n\n"
                             "The date must be entered in YYYY or "
                             "YYYY-MM-DD format.") % new)
            msg.run()
            msg.destroy()
        elif row[colnum].replace('<i>','').replace('</i>','') != new:
            row[colnum] = util.escape(new)
            row[2] = True # Edited
            row[4] = False # not Deleted
            self.enable_save()

    def songprop_selection_changed(self, selection):
        model, iter = selection.get_selected()
        may_remove = bool(selection.count_selected_rows()) and model[iter][3]
        self.remove.set_sensitive(may_remove)

    def songprop_files_toggled(self, toggle):
        getattr(self.fview_scroll,['hide','show'][bool(toggle.get_active())])()

    def songprop_files_changed(self, selection):
        songrefs = []
        def get_songrefs(model, path, iter, songrefs):
            path = model.convert_path_to_child_path(path)
            model = model.get_model()
            songrefs.append([model[path][0], model[path][1]])
        selection.selected_foreach(get_songrefs, songrefs)
        if len(songrefs): self.songrefs = songrefs
        self.fill_property_info()

    def prop_popup_menu(self, view):
        self.menu.popup(None, None, None, 1, 0)

    def prop_button_press(self, view, event):
        if event.button != 3:
            return False
        x, y = map(int, [event.x, event.y])
        try: path, col, cellx, celly = view.get_path_at_pos(x, y)
        except TypeError: return True
        view.grab_focus()
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            view.set_cursor(path, col, 0)
        row = view.get_model()[path]
        self.menu_w.get_widget("split_album").hide()
        self.menu_w.get_widget("split_title").hide()
        self.menu_w.get_widget("split_performer").hide()
        self.menu_w.get_widget("split_arranger").hide()
        self.menu_w.get_widget("special_sep").hide()

        if row[0] == "album":
            self.menu_w.get_widget("split_album").show()
            self.menu_w.get_widget("special_sep").show()

        if row[0] == "title":
            self.menu_w.get_widget("split_title").show()
            self.menu_w.get_widget("special_sep").show()

        if row[0] == "artist":
            self.menu_w.get_widget("split_performer").show()
            self.menu_w.get_widget("split_arranger").show()
            self.menu_w.get_widget("special_sep").show()

        self.menu.popup(None, None, None, event.button, event.time)
        return True

    def songprop_add(self, button):
        add = widgets["add_tag_dialog"]
        tag = widgets["add_tag_tag"]
        val = widgets["add_tag_value"]
        tag.child.set_text("")
        val.set_text("")
        tag.child.set_activates_default(gtk.TRUE)
        val.set_activates_default(gtk.TRUE)
        tag.child.grab_focus()

        while True:
            resp = add.run()
            if resp != gtk.RESPONSE_OK: break

            comment = tag.child.get_text().decode("utf-8").lower().strip()
            value = val.get_text().decode("utf-8")
            date = sre.compile("^\d{4}(-\d{2}-\d{2})?$")
            if not self.songinfo.can_change(comment):
                msg = gtk.MessageDialog(add, gtk.DIALOG_MODAL,
                                        gtk.MESSAGE_WARNING, gtk.BUTTONS_OK)
                msg.set_markup(_("Invalid tag <b>%s</b>\n\nThe files currently"
                                 " selected do not support editing this tag")%
                               util.escape(comment))
                msg.run()
                msg.destroy()
            elif comment == "date" and not date.match(value):
                msg = gtk.MessageDialog(add, gtk.DIALOG_MODAL,
                                        gtk.MESSAGE_WARNING,
                                        gtk.BUTTONS_OK)
                msg.set_markup(_("Invalid date: <b>%s</b>.\n\n"
                                 "The date must be entered in YYYY or "
                                 "YYYY-MM-DD format.") % value)
                msg.run()
                msg.destroy()
            else:
                self.add_new_tag(comment, value)
                tag.child.set_text("")
                val.set_text("")
                break

        add.hide()

    def add_new_tag(self, comment, value):
        edited = True
        edit = True
        orig = None
        deleted = False
        iters = []
        def find_same_comments(model, path, iter):
            if model[path][0] == comment: iters.append(iter)
        self.model.foreach(find_same_comments)
        row = [comment, util.escape(value), edited, edit,deleted,orig]
        if len(iters): self.model.insert_after(iters[-1], row=row)
        else: self.model.append(row=row)
        self.enable_save()

    def enable_save(self):
        self.save.set_sensitive(True)
        self.revert.set_sensitive(True)
        if self.window.get_title()[0] != "*":
            self.window.set_title("* " + self.window.get_title())

    def songprop_remove(self, *args):
        model, iter = self.view.get_selection().get_selected()
        row = model[iter]
        if row[0] in self.songinfo:
            row[2] = True # Edited
            row[4] = True # Deleted
        else:
            model.remove(iter)
        self.enable_save()

    def fill_property_info(self):
        from library import AudioFileGroup
        songinfo = AudioFileGroup([song for (song,ref) in self.songrefs])
        self.songinfo = songinfo
        if len(self.songrefs) == 1:
            self.window.set_title(_("%s - Properties") %
                    self.songrefs[0][0]["title"])
        elif len(self.songrefs) > 1:
            self.window.set_title(_("%s and %d more - Properties") %
                    (self.songrefs[0][0]["title"], len(self.songrefs)-1))
        else:
            raise ValueError("Properties of no songs?")

        self.artist.set_markup(songinfo['artist'].safenicestr())
        self.title.set_markup(songinfo['title'].safenicestr())
        self.album.set_markup(songinfo['album'].safenicestr())
        filename = util.unexpand(songinfo['=filename'].safenicestr())
        self.filename.set_markup(filename)

        if len(self.songrefs) > 1:
            listens = sum([song["=playcount"] for song, i in self.songrefs])
            if listens == 1: s = ("%d songs head") % listens
            else: s = _("%d songs heard") % listens
            self.played.set_markup("<i>%s</i>" % s)
        else:
            self.played.set_text(self.songrefs[0][0].get_played())

        self.model.clear()
        comments = {} # dict of dicts to see if comments all share value

        # prune some 'comments' we don't want shown
        for k in songinfo.keys():
            if k.startswith('='): del(songinfo[k])

        keys = songinfo.keys()
        keys.sort()
        # reverse order here so insertion puts them in proper order.
        for comment in ['album', 'artist', 'title']:
            try: keys.remove(comment)
            except ValueError: pass
            else: keys.insert(0, comment)

        for comment in keys:
            orig_value = songinfo[comment].split("\n")
            value = songinfo[comment].safenicestr()
            edited = False
            edit = songinfo.can_change(comment)
            deleted = False
            for i, v in enumerate(value.split("\n")):
                self.model.append(row=[comment, v, edited, edit, deleted,
                                       orig_value[i]])

        self.add.set_sensitive(bool(songinfo.can_change()))
        self.save.set_sensitive(False)
        self.revert.set_sensitive(False)

        self.songprop_tbp_preview()
        self.songprop_nbp_preview()

    def songprop_nbp_preview(self, *args):
        self.nbp_model.clear()
        pattern = self.nbp_entry.get_text().decode('utf-8')
        try:
            pattern = util.FileFromPattern(pattern)
        except ValueError: 
            make_error(_("Pattern with subdirectories is not absolute"),
                       _("The pattern\n<b>%s</b>\ncontains / but does not "
                         "start from root. This results in bad renaming, so "
                         "is not supported.") % util.escape(pattern),
                       gtk.BUTTONS_OK)
            return
            
        for song, ref in self.songrefs:
            newname = pattern.match(song)
            self.nbp_model.append(row=[song, ref, song['=basename'], newname])


    def songprop_tbp_preview(self, *args):
        self.tbp_view.set_model(None)
        self.tbp_model.clear()

        # build the pattern
        pattern_text = self.tbp_entry.get_text().decode('utf-8')
        pattern = util.PatternFromFile(pattern_text)

        # create model to store the matches, and view to match
        self.tbp_model = gtk.ListStore(object, object, str,
                *([str] * len(pattern.headers)))

        for col in self.tbp_view.get_columns(): self.tbp_view.remove_column(col)
        col = gtk.TreeViewColumn(_('File'), gtk.CellRendererText(), text=2)
        self.tbp_view.append_column(col)
        for i, header in enumerate(pattern.headers):
            col = gtk.TreeViewColumn(header, gtk.CellRendererText(), text=i+3)
            self.tbp_view.append_column(col)

        # get info for all matches
        for song, ref in self.songrefs:
            row = [song, ref, song['=basename']]
            match = pattern.match(song)
            row.extend([match.get(h, '') for h in pattern.headers])
            self.tbp_model.append(row=row)

        # save for last to potentially save time
        self.tbp_view.set_model(self.tbp_model)


def make_song_properties(songrefs):
    dlg = MultiInstanceWidget(widget="properties_window")
    dlg.window = dlg.widgets.get_widget('properties_window')
    #dlg.menu = dlg.widgets.get_widget('props_popup')
    dlg.save = dlg.widgets.get_widget('songprop_save')
    dlg.revert = dlg.widgets.get_widget('songprop_revert')
    dlg.artist = dlg.widgets.get_widget('songprop_artist')
    dlg.played = dlg.widgets.get_widget('songprop_played')
    dlg.title = dlg.widgets.get_widget('songprop_title')
    dlg.album = dlg.widgets.get_widget('songprop_album')
    dlg.filename = dlg.widgets.get_widget('songprop_file')
    dlg.view = dlg.widgets.get_widget('songprop_view')
    dlg.add = dlg.widgets.get_widget('songprop_add')
    dlg.remove = dlg.widgets.get_widget('songprop_remove')
    # comment, value, use-changes, edit, deleted
    dlg.model = gtk.ListStore(str, str, bool, bool, bool, str)
    dlg.view.set_model(dlg.model)
    selection = dlg.view.get_selection()
    selection.connect('changed', dlg.songprop_selection_changed)

    render = gtk.CellRendererToggle()
    column = gtk.TreeViewColumn(_('Write'), render, active=2, activatable=3)
    render.connect('toggled', dlg.songprop_toggle, dlg.model)
    dlg.view.append_column(column)
    render = gtk.CellRendererText()
    render.connect('edited', dlg.songprop_edit, dlg.model, 0)
    column = gtk.TreeViewColumn(_('Tag'), render, text=0)
    dlg.view.append_column(column)
    render = gtk.CellRendererText()
    render.connect('edited', dlg.songprop_edit, dlg.model, 1)
    column = gtk.TreeViewColumn(_('Value'), render, markup=1, editable=3,
                                strikethrough=4)
    dlg.view.append_column(column)

    # select active files
    dlg.fview = dlg.widgets.get_widget('songprop_files')
    dlg.fview_scroll = dlg.widgets.get_widget('songprop_files_scroll')
    dlg.fbasemodel = gtk.ListStore(object, object, str, str, str)
    dlg.fmodel = gtk.TreeModelSort(dlg.fbasemodel)
    dlg.fview.set_model(dlg.fmodel)
    selection = dlg.fview.get_selection()
    selection.set_mode(gtk.SELECTION_MULTIPLE)
    selection.connect('changed', dlg.songprop_files_changed)
    column = gtk.TreeViewColumn(_('File'), gtk.CellRendererText(), text=2)
    column.set_sort_column_id(2)
    dlg.fview.append_column(column)
    column = gtk.TreeViewColumn(_('Path'), gtk.CellRendererText(), text=3)
    column.set_sort_column_id(4)
    dlg.fview.append_column(column)
    for song, ref in songrefs:
        dlg.fbasemodel.append(row=[song, ref, song.get('=basename',''),
                song.get('=dirname',''), song['=filename']])


    # tag by pattern
    dlg.tbp_combo = dlg.widgets.get_widget("songprop_tbp_combo")
    dlg.tbp_entry = dlg.tbp_combo.child
    dlg.tbp_view = dlg.widgets.get_widget("songprop_tbp_view")
    dlg.tbp_model = gtk.ListStore(int) # fake first one
    dlg.tbp_headers = []

    # rename by pattern
    dlg.nbp_combo = dlg.widgets.get_widget("songprop_nbp_combo")
    dlg.nbp_entry = dlg.nbp_combo.child
    dlg.nbp_view = dlg.widgets.get_widget("songprop_nbp_view")
    dlg.nbp_model = gtk.ListStore(object, object, str, str)
    dlg.nbp_view.set_model(dlg.nbp_model)
    column = gtk.TreeViewColumn(_('File'), gtk.CellRendererText(), text=2)
    dlg.nbp_view.append_column(column)
    column = gtk.TreeViewColumn(_('New Name'), gtk.CellRendererText(), text=3)
    dlg.nbp_view.append_column(column)

    # select all files, causing selection update to fill the info
    selection.select_all()

    dlg.window.show()

# Non-Glade handlers:

# Grab the text from the query box, parse it, and make a new filter.
def text_parse(*args):
    text = widgets["query"].child.get_text()
    config.set("memory", "query", text)
    text = text.decode("utf-8").strip()
    orig_text = text
    if text and "=" not in text and "/" not in text:
        # A simple search, not regexp-based.
        parts = ["* = /" + sre.escape(p) + "/" for p in text.split()]
        text = "&(" + ",".join(parts) + ")"
        # The result must be well-formed, since no /s were
        # in the original string and we escaped it.

    if player.playlist.playlist_from_filter(text):
        m = widgets["query"].get_model()
        for i, row in enumerate(iter(m)):
             if row[0] == orig_text:
                 m.remove(m.get_iter((i,)))
                 break
        else:
            if len(m) > 10: m.remove(m.get_iter((10,)))
        m.prepend([orig_text])
        set_entry_color(widgets["query"].child, "black")
        refresh_songlist()
        widgets["query"].child.set_text(orig_text)
    return True

def filter_on_header(header):
    if header == "=#": header = "tracknumber"
    elif header == "=d": header = "discnumber"
    selection = widgets["songlist"].get_selection()
    model, rows = selection.get_selected_rows()
    values = {}
    for row in rows:
        song = model[row][len(HEADERS)]
        if header in song:
            for val in song[header].split("\n"):
                values[val] = True

    text = "|".join([sre.escape(s) for s in values.keys()])
    query = u"%s = /%s/c" % (header, text)
    widgets["query"].child.set_text(query.encode('utf-8'))
    widgets["search_button"].clicked()

# Try and construct a query, but don't actually run it; change the color
# of the textbox to indicate its validity (if the option to do so is on).
def test_filter(*args):
    if not config.state("color"): return
    textbox = widgets["query"].child
    text = textbox.get_text()
    if "=" not in text and "/" not in text:
        gtk.idle_add(set_entry_color, textbox, "blue")
    elif parser.is_valid(text):
        gtk.idle_add(set_entry_color, textbox, "dark green")
    else:
        gtk.idle_add(set_entry_color, textbox, "red")

# Resort based on the header clicked.
def set_sort_by(header, i, sortdir=None):
    s = header.get_sort_order()
    if sortdir is not None: s = sortdir
    elif not header.get_sort_indicator() or s == gtk.SORT_DESCENDING:
        s = gtk.SORT_ASCENDING
    else: s = gtk.SORT_DESCENDING
    for h in widgets["songlist"].get_columns():
        h.set_sort_indicator(False)
    header.set_sort_indicator(True)
    header.set_sort_order(s)
    player.playlist.sort_by(HEADERS[i[0]], s == gtk.SORT_DESCENDING)
    refresh_songlist()

# Clear the songlist and readd the songs currently wanted.
def refresh_songlist():
    sl = widgets["songlist"]
    sl.set_model(None)
    widgets.songs.clear()
    statusbar = widgets["statusbar"]
    for song in player.playlist:
        wgt = ((song is CURRENT_SONG[0] and 700) or 400)
        widgets.songs.append([song.get(h, "") for h in HEADERS] + [song, wgt])

    i = len(list(player.playlist))
    if i != 1:statusbar.set_text(_("%d songs found.") % i)
    else: statusbar.set_text(_("%d song found.") % i)
    sl.set_model(widgets.songs)
    gc.collect()

HEADERS = ["=#", "title", "album", "artist"]
HEADERS_FILTER = { "=#": "track", "tracknumber": "track",
                   "discnumber": "disc", "=d": "disc",
                   "=lastplayed": "last played", "=filename": "full name",
                   "=playcount": "play count", "=basename": "filename",
                   "=dirname": "directory"}

CURRENT_SONG = [ None ]

# Set the color of some text.
def set_entry_color(entry, color):
    layout = entry.get_layout()
    text = layout.get_text()
    markup = '<span foreground="%s">%s</span>' % (color, util.escape(text))
    layout.set_markup(markup)

# Build a new filter around our list model, set the headers to their
# new values.
def set_column_headers(sl):
    SHORT_COLS = ["=#", "=d", "tracknumber", "discnumber"]
    sl.set_model(None)
    widgets.songs = gtk.ListStore(*([str] * len(HEADERS) + [object, int]))
    for c in sl.get_columns(): sl.remove_column(c)
    widgets["songlist"].realize()    
    width = widgets["songlist"].get_allocation()[2]
    c = len(HEADERS)
    for t in SHORT_COLS:
        if t in HEADERS: c -= 0.5
    width = int(width / c)
    for i, t in enumerate(HEADERS):
        render = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_(HEADERS_FILTER.get(t, t)).title(),
                                    render, text = i, weight = len(HEADERS)+1)
        if t in SHORT_COLS: render.set_fixed_size(-1, -1)
        else: render.set_fixed_size(width, -1)
        column.set_resizable(True)
        column.set_clickable(True)
        column.set_sort_indicator(False)
        column.connect('clicked', set_sort_by, (i,))
        sl.append_column(column)
    refresh_songlist()
    sl.set_model(widgets.songs)

def setup_nonglade():
    # Restore window size.
    w, h = map(int, config.get("memory", "size").split())
    widgets["main_window"].set_property("default-width", w)
    widgets["main_window"].set_property("default-height", h)

    # Set up the main song list store.
    sl = widgets["songlist"]
    sl.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
    widgets.songs = gtk.ListStore(object)

    # Build a model and view for our ComboBoxEntry.
    liststore = gtk.ListStore(str)
    widgets["query"].set_model(liststore)
    widgets["query"].set_text_column(0)
    cell = gtk.CellRendererText()
    widgets["query"].pack_start(cell, True)
    widgets["query"].child.connect('activate', text_parse)
    widgets["query"].child.connect('changed', test_filter)
    widgets["search_button"].connect('clicked', text_parse)

    # Initialize volume controls.
    widgets["volume"].set_value(player.device.volume)

    # Show main window.
    widgets["main_window"].show()
    # Wait to fill in the column headers because otherwise the
    # spacing is off, since the window hasn't been sized until now.
    set_column_headers(sl)
    widgets.wrap = GTKSongInfoWrapper()
    widgets["query"].child.set_text(config.get("memory", "query"))
    gtk.threads_init()

def save_config():
    config_fn = os.path.join(os.environ["HOME"], ".quodlibet", "config")
    util.mkdir(os.path.dirname(config_fn))
    f = file(config_fn, "w")  
    config.write(f)
    f.close()

def main():
    HEADERS[:] = config.get("settings", "headers").split()
    if "title" not in HEADERS: HEADERS.append("title")
    setup_nonglade()
    if config.get("memory", "song"):
        widgets["query"].child.set_text(config.get("memory", "query"))
        text_parse()
    else:
        player.playlist.set_playlist(library.values())
        refresh_songlist()
    player.playlist.sort_by(HEADERS[0])
    print _("Loaded song library.")

    for opt in config.options("header_maps"):
        val = config.get("header_maps", opt)
        HEADERS_FILTER[opt] = val

    from threading import Thread
    t = Thread(target = player.playlist.play, args = (widgets.wrap,))
    util.mkdir(os.path.join(os.environ["HOME"], ".quodlibet"))
    signal.signal(signal.SIGINT, gtk.main_quit)
    t.start()
    gtk.main()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    player.playlist.quitting()
    t.join()

    print _("Saving song library.")
    cache_fn = os.path.join(os.environ["HOME"], ".quodlibet", "songs")
    library.save(cache_fn)

    save_config()

def print_help():
    print _("""\
Quod Libet - a music library and player
Options:
  --help, -h        Display this help message
  --version         Display version and copyright information
  --refresh-library Rescan your song cache; remove dead files; add new ones;
                    and then exit.""")

    raise SystemExit

def print_version():
    print _("""\
Quod Libet %s
Copyright 2004 Joe Wreschnig <piman@sacredchao.net>, Michael Urman

This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.\
""") % VERSION
    raise SystemExit

def refresh_cache():
    cache_fn = os.path.join(os.environ["HOME"], ".quodlibet", "songs")
    config_fn = os.path.join(os.environ["HOME"], ".quodlibet", "config")
    import library, config
    config.init(config_fn)
    library.init()
    print _("Loading, scanning, and saving your library.")
    library.library.load(cache_fn)
    if config.get("settings", "scan"):
        for a, c in library.scan(config.get("settings", "scan").split(":")):
            pass
    library.library.save(cache_fn)
    raise SystemExit

def print_playing(fstring):
    try:
        fn = file(os.path.join(os.environ["HOME"], ".quodlibet", "current"))
        data = {}
        for line in fn:
            line = line.strip()
            parts = line.split("=")
            key = parts[0]
            val = "=".join(parts[1:])
            if key in data: data[key] += "\n" + val
            else: data[key] = val
        print fstring % data
        raise SystemExit
    except (OSError, IOError):
        print _("No song is currently playing.")
        raise SystemExit(True)

def error_and_quit():
    d = make_error(_("No audio device found"),
                   _("Quod Libet was unable to open your audio device. "
                     "Often this means another program is using it, or "
                     "your audio drivers are not configured.\n\nQuod Libet "
                     "will now exit."),
                   gtk.BUTTONS_OK)
    d.show()
    d.run()
    gtk.main_quit()
    return True

if __name__ == "__main__":
    import os, sys

    basedir = os.path.split(os.path.realpath(__file__))[0]
    if os.path.isdir(os.path.join(basedir, "po")):
        i18ndir = os.path.join(basedir, "po")
    else: i18ndir = "/usr/share/locale"

    import locale, gettext
    try: locale.setlocale(locale.LC_ALL, '')
    except: pass
    gettext.bindtextdomain("quodlibet", i18ndir)
    gettext.textdomain("quodlibet")
    gettext.install("quodlibet", i18ndir, unicode = 1)
    _ = gettext.gettext

    # Check command-line parameters before doing "real" work, so they
    # respond quickly.
    for command in sys.argv[1:]:
        if command in ["--help", "-h"]: print_help()
        elif command in ["--version", "-v"]: print_version()
        elif command in ["--refresh-library"]: refresh_cache()
        elif command in ["--print-playing"]: print_playing(sys.argv[2])
        else:
            print _("E: Unknown command line option: %s") % command
            raise SystemExit(_("E: Try %s --help") % sys.argv[0])

    # Get to the right directory for our data.
    d = os.path.split(os.path.realpath(__file__))[0]
    os.chdir(d)
    if os.path.exists(os.path.join(d, "quodlibet.zip")):
        sys.path.insert(0, os.path.join(d, "quodlibet.zip"))

    # Initialize GTK/Glade.
    import pygtk
    pygtk.require('2.0')
    import gtk
    if gtk.pygtk_version < (2, 4) or gtk.gtk_version < (2, 4):
        print _("E: You need GTK+ and PyGTK 2.4 or greater to run Quod Libet.")
        print _("E: You have GTK+ %s and PyGTK %s.") % (
            ".".join(map(str, gtk.gtk_version)),
            ".".join(map(str, gtk.pygtk_version)))
        raise SystemExit(_("E: Please upgrade GTK+/PyGTK."))
    import gtk.glade
    gtk.glade.bindtextdomain("quodlibet", i18ndir)
    gtk.glade.textdomain("quodlibet")
    widgets = Widgets("quodlibet.glade")

    import gc
    import util

    # Load the library.
    import library
    cache_fn = os.path.join(os.environ["HOME"], ".quodlibet", "songs")
    library.init(cache_fn)
    from library import library

    # Load configuration data and scan the library for new/changed songs.
    import config
    config_fn = os.path.join(os.environ["HOME"], ".quodlibet", "config")
    config.init(config_fn)
    if config.get("settings", "scan"):
        for a, c in library.scan(config.get("settings", "scan").split(":")):
            pass

    # Try to initialize the playlist and audio output.
    print _("Opening audio device.")
    import player
    try: player.init()
    except IOError:
        # The audio device was busy; we can't do anything useful yet.
        # FIXME: Allow editing but not playing in this case.
        gtk.idle_add(error_and_quit)
        gtk.main()
        raise SystemExit(True)

    import parser
    import signal
    import sre
    main()
