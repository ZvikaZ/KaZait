# -*- coding: utf-8 -*-

import updater
# external imports

import gtk
import gobject
import os
import sys
import subprocess
import time
import datetime
import tempfile
import ctypes.wintypes
import re
import string
import urllib
from threading import Thread
from Queue import Queue, Empty
import webbrowser


# TODO:
# - proxy not working on compiled
# - still delta between compiled icons
# - check: no proxy on Intel - update causes delayes on startup
# - return open file menu
# - add previous releases link
# - dNd:  highlight/change cursor when possible
# - verify that temp file get erased
# - ? add some waiting on progress bar, to save some cpu cycles...  (measure first!)
# - Make output file name clickable, or at least copyable
# - Add label and frame to output name
# - As explanation for quality, above 5
# - InnoSetup: avoid highlighting uninstaller in start menu
# - beautify GUI
# - check for updates?
# - translation ?
#
# investigate:
# - search not working in FileChooserDialog


# copied from http://stackoverflow.com/questions/7674790/bundling-data-files-with-pyinstaller-onefile/13790741#13790741
# allows
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS

    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_win_my_documents():
    # based on http://stackoverflow.com/questions/3858851/python-get-windows-special-folders-for-currently-logged-in-user
    # and http://stackoverflow.com/questions/6227590/finding-the-users-my-documents-path

    CSIDL_PERSONAL = 5       # My Documents
    # the 2 stackoverflow answers use different values for this constant!
    SHGFP_TYPE_CURRENT = 0   # Get current, not default value

    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)

    if os.path.isdir(buf.value):
        return buf.value
    else:
        # fall back to simple "home" notion
        return(os.path.expanduser("~"))


# copied from http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

class GladeGTK:
    qualities = {
        1: '8k',
        2: '16k',
        3: '24k',
        4: '32k',
        5: '40k',
        6: '48k',
        7: '64k',
        8: '80k',
        9: '96k',
        10: '112k',
    }
    def setFileName(self, origFileName):
        self.origFileName = origFileName.lower()
        splitFileName = os.path.splitext(self.origFileName)[0]
        self.newFileName = splitFileName+".mp3"
        i = 0
        while os.path.exists(self.newFileName.encode(sys.getfilesystemencoding())):
            i += 1
            self.newFileName = splitFileName+"_"+str(i)+".mp3"

        self.builder.get_object("outputNameLabel").set_text(self.newFileName)

    def translate_time(self, t):
        pt = datetime.datetime.strptime(t.rstrip(), "%H:%M:%S.%f")
        # return value in seconds, ignores microsecond
        return pt.second + pt.minute*60 + pt.hour*3600

    def update_progress_bar(self, progressFileName):
        # init duration - from stderr
        regularExp = re.compile(r"(Duration:)\s(.*?),")
        for line in iter(self.proc.stderr.readline,''):
            m = regularExp.search(line)
            if m:
                duration = self.translate_time(m.group(2))
                break

        # open thread to read from stderr - to avoid ffmpeg stuck because of full fifo
        q = Queue()
        t = Thread(target=enqueue_output, args=(self.proc.stderr, q))
        t.daemon = True # thread dies with the program
        t.start()

        # open clean progress window
        self.builder.get_object("labelElapsedTime").set_text("")
        self.builder.get_object("labelRemainingTime").set_text("")
        self.builder.get_object("labelTotalTime").set_text("")
        self.builder.get_object("progressbar1").set_fraction(0)
        self.builder.get_object("progressbar1").set_text("")
        self.builder.get_object("ProgressWindow").show()

        # start working
        startTime = time.clock()
        last_pos = 0
        while self.proc.poll() is None:
            try:
                _ = q.get_nowait() # or q.get(timeout=.1)
            except Empty:
                pass

            with open(progressFileName) as f:
                f.seek(last_pos)
                for line in f:
                    key, value = string.split(line, "=", 2)
                    if key == "out_time":
                        valueTime = self.translate_time(value)
                        donePart =  1.0 * valueTime / duration
                        elapsedTime = time.clock() - startTime
                        totalTime = elapsedTime / donePart
                        remainTime = totalTime - elapsedTime
                        self.builder.get_object("labelElapsedTime").set_text(str(int(elapsedTime)))
                        self.builder.get_object("labelRemainingTime").set_text(str(int(remainTime)))
                        self.builder.get_object("labelTotalTime").set_text(str(int(totalTime)))
                        self.builder.get_object("progressbar1").set_fraction(donePart)
                        self.builder.get_object("progressbar1").set_text(str(int(donePart * 100))+" %")
                last_pos = f.tell()

            # request GTK to come back for another round
            yield True

        # we're finished here
        self.builder.get_object("ProgressWindow").hide()
        self.finishAction()
        yield False


    def startAction(self):
        # avoid console window appearing on subprocess, based on:
        # https://github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        quality =  self.qualities[self.builder.get_object("hscale1").get_value()]
        progressFile = tempfile.NamedTemporaryFile().name

        ON_POSIX = 'posix' in sys.builtin_module_names

        # The Core Of The Program:

        # progressFile = "progress.txt"
        self.proc = subprocess.Popen(
            [resource_path('ffmpeg.exe'),
             '-i', self.origFileName.encode(sys.getfilesystemencoding()),
             '-b:a', quality,
             '-progress', progressFile,
             '-nostats',
             # '-loglevel', '5',
             # '-codec:a', 'libmp3lame',
             self.newFileName.encode(sys.getfilesystemencoding())
            ],
            bufsize=1, close_fds=ON_POSIX,
            startupinfo=si,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # update GUI
        self.set_oks_sensitivies(False)
        statusBar = self.builder.get_object("statusbar1")
        self.context_id = statusBar.get_context_id("Waiting")
        statusBar.push(self.context_id, "עובד, נא להמתין...")

        # make progress bar updating
        task = self.update_progress_bar(progressFile)
        gtk.idle_add(task.next)


    def finishAction(self):
        # restore GUI
        self.set_oks_sensitivies(True)
        self.builder.get_object("statusbar1").pop(self.context_id)

        # notify user how it finished
        if self.proc.returncode == 0:
            md = gtk.MessageDialog(self.builder.get_object("MainWindow"),
                gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO,
                gtk.BUTTONS_CLOSE, "%s\n%s %s %s" % ("סיימנו :)", "הקובץ", self.newFileName, "מוכן."))
        else:
            print self.proc.returncode
            md = gtk.MessageDialog(self.builder.get_object("MainWindow"),
                gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR,
                gtk.BUTTONS_CLOSE, "%s\n%s %s %s" % ("הפעולה נכשלה!", "יתכן שהקובץ", self.origFileName, "אינו קובץ קול חוקי."))
        md.run()
        md.destroy()

        # avoid overwriting the samefile - if runs again
        self.setFileName(self.origFileName)

    ###############
    # GUI signals
    ###############
    def showDialog(self, name):
        dialog = self.builder.get_object(name)
        dialog.run()
        dialog.hide()

    def on_backToDefaultQualityButton_clicked(self, widget):
        self.builder.get_object("hscale1").set_value(self.defaultQuality)

    def on_hscale1_value_changed(self, widget):
        if self.builder.get_object("hscale1").get_value() == self.defaultQuality:
            self.builder.get_object("backToDefaultQualityButton").set_sensitive(False)
        else:
            self.builder.get_object("backToDefaultQualityButton").set_sensitive(True)

    def on_okButton_clicked(self, widget):
        self.startAction()

    def on_filechooserbutton1_file_set(self, widget):
        fileName = widget.get_filename()
        if fileName:
            self.setFileName(fileName)
            self.set_oks_sensitivies(True)

    ###################
    # Menu Actions
    ###################
    def on_openImagemenuitem_activate(self, widget):
        print self.builder.get_object("filechooserbutton1").activate()
        print widget

    def on_doImagemenuitem_activate(self, widget):
        self.startAction()

    def on_quitImagemenuitem_activate(self, widget):
        self.quit()

    def on_infoImagemenuitem_activate(self, widget):
        with open(resource_path("explainDialog.txt")) as file:
            text = file.read()
            self.builder.get_object("explainTextBuffer").set_text(text)
            self.showDialog("infoDialog")

    def on_bugImagemenuitem_activate(self, widget):
        webbrowser.open("mailto:haramaty.zvika@gmail.com?Subject=שיעור%20כזית:%20תקלה".encode(sys.getfilesystemencoding())
                        , new=2)

    def on_updateImagemenuitem_activate(self, widget):
        self.updater.check_for_updates()
        finished = self.updater.finished.wait(10)
        if finished:
            self.updater_finished(auto_started=False)


    def on_aboutImagemenuitem_activate(self, widget):
        self.showDialog("aboutdialog1")


    def set_oks_sensitivies(self, s):
        self.builder.get_object("okButton").set_sensitive(s)
        self.builder.get_object("doImagemenuitem").set_sensitive(s)

    def destroy(self, widget, data=None):
        self.quit()

    def quit(self):
        # self.saveConfig()
        gtk.main_quit()

    def auto_updater_on_init(self):
        while not self.updater.finished.is_set():
            time.sleep(0.001)
            # request GTK to come back for another round
            yield True

        # we're finished here
        self.updater_finished(auto_started=True)
        yield False

    def updater_finished(self, auto_started):
        md = None
        if self.updater.ok:
            if self.updater.need_update:
                self.builder.get_object("update_version_label").set_text(str(self.updater.latest_version))
                self.showDialog("update_dialog")
            else:
                if not auto_started:
                    md = gtk.MessageDialog(self.builder.get_object("MainWindow"),
                        gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO,
                        gtk.BUTTONS_CLOSE, "הגרסה המותקנת עדכנית")
        else:
            if not auto_started:
                md = gtk.MessageDialog(self.builder.get_object("MainWindow"),
                    gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR,
                    gtk.BUTTONS_CLOSE, "לא הצלחנו לבדוק האם יש עדכון זמין"+"\n\n"+str(self.updater.error_message))

        if md:
            md.run()
            md.destroy()

    def on_update_dialog_response(self, dialog, response_id):
        if response_id == gtk.RESPONSE_YES:
            webbrowser.open(self.updater.download_url)


    ###################
    # Drag And Drop
    ###################

    # Trying, unsuccessfully so far, to make DranAndDrop change button appearance
    def on_label1_drag_motion(self, widget, context, x, y, timestamp):
        print "motion Label"

    # Trying, unsuccessfully so far, to make DranAndDrop change button appearance
    def on_filechooserbutton1_drag_motion(self, widget, context, x, y, timestamp):
        print "motion Button"

    def on_filechooserbutton1_drag_data_received(self, widget, context, x, y, selection, target_type, timestamp):
        self.handle_dnd(selection)

    def on_label1_drag_data_received(self, widget, context, x, y, selection, target_type, timestamp):
        fileName = self.handle_dnd(selection)
        if fileName:
            self.builder.get_object("filechooserbutton1").set_filename(fileName)

    # based on http://faq.pygtk.org/index.py?req=show&file=faq23.031.htp
    def handle_dnd(self, selection):
        uri = selection.data.strip('\r\n\x00')
        uri_splitted = uri.split()
        # we may have more than one file dropped
        # but in our case, we handle just the first 1
        path = self.get_file_path_from_dnd_dropped_uri(uri_splitted[0])
        if os.path.isfile(path.encode(sys.getfilesystemencoding())): # is it file?
            self.setFileName(path)
            self.set_oks_sensitivies(True)
            return path

    def get_file_path_from_dnd_dropped_uri(self, uri):
        # get the path to file
        path = ""
        if uri.startswith('file:\\\\\\'): # windows
            path = uri[8:] # 8 is len('file:///')
        elif uri.startswith('file://'): # nautilus, rox
            path = uri[7:] # 7 is len('file://')
        elif uri.startswith('file:'): # xffm
            path = uri[5:] # 5 is len('file:')

        path = urllib.url2pathname(path) # escape special chars
        path = path.strip('\r\n\x00') # remove \r\n and NULL

        return path


    ###################
    # Init
    ###################
    def uri_hook_func(self, ignore1, url, ignore2):
        webbrowser.open(url, new=2)

    def __init__(self):
        gobject.threads_init()
        self.defaultQuality = 3
        self.proc = None
        self.updater = updater.Updater("https://api.github.com/repos/ZvikaZ/KaZait")
        self.showWindow()

    def my_init(self):
        # TARGET_TYPE_URI_LIST = 80
        # dnd_list = [ ( 'text/uri-list', 0, TARGET_TYPE_URI_LIST ) ]
        # self.builder.get_object("label1").drag_dest_set(
        #     gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP,
        #     dnd_list, gtk.gdk.ACTION_COPY)
        #
        #
        self.builder.get_object("label1").drag_dest_set(
            gtk.DEST_DEFAULT_ALL,
            [ ( "text/uri-list", 0, 80 ) ],
            gtk.gdk.ACTION_DEFAULT)


        #######################
        ## About Dialog Init ##
        #######################
        gtk.about_dialog_set_url_hook(self.uri_hook_func, data=None)
        aboutDialog = self.builder.get_object("aboutdialog1")
        aboutDialog.set_comments(aboutDialog.get_comments()+self.updater.current_version)


        #######################
        ## File Chooser Init ##
        #######################
        chooser = self.builder.get_object("filechooserbutton1")
        # chooser.drag_dest_set_track_motion(gtk.DEST_DEFAULT_MOTION)

        filter = gtk.FileFilter()
        filter.add_mime_type("audio/wav")
        filter.add_mime_type("audio/mpeg")
        filter.add_mime_type("audio/x-ms-wma")
        filter.add_mime_type("audio/amr")
        filter.add_mime_type("audio/3gpp")
        filter.set_name("קבצי קול")
        chooser.add_filter(filter)

        filter = gtk.FileFilter()
        filter.add_pattern("*")
        filter.set_name("כל הקבצים")
        chooser.add_filter(filter)

        my_documents = get_win_my_documents()
        chooser.set_current_folder(my_documents)
        chooser.add_shortcut_folder(my_documents)
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if os.path.isdir(downloads):
            chooser.add_shortcut_folder(downloads)

        #######################
        ## Status Bar Init   ##
        #######################
        bar = self.builder.get_object("statusbar1")
        context_id = bar.get_context_id("Initial Message")
        bar.push(context_id, "מוקדש באהבה לכל הלומדים. לבעיות: haramaty.zvika@gmail.com")

        #######################
        ## Scale Init        ##
        #######################
        scale = self.builder.get_object("hscale1")
        scale.set_digits(0)
        scale.set_range(1, 10)
        scale.set_value(self.defaultQuality)

        #######################
        ## Auto Updater      ##
        #######################
        updater_task = self.auto_updater_on_init()
        gtk.idle_add(updater_task.next)

    def showWindow(self):
        # self.readConfig()

        gtk.rc_add_default_file(resource_path("gtkrc"))
        gtk.widget_set_default_direction(gtk.TEXT_DIR_RTL)

        #Set the Glade file
        self.builder = gtk.Builder()

        translated_glade = resource_path("main.glade")
        self.builder.add_from_file(translated_glade)

        #Get the Main Window, and connect the "destroy" event
        self.window = self.builder.get_object("MainWindow")

        if (self.window):
            self.window.connect("destroy", self.destroy)

        self.window.set_border_width(1)

        # self.builder.get_object("notebook1").set_current_page(1)

        # self.add_methods_tree()


        self.builder.connect_signals(self)

        self.my_init()

        self.window.show_all()


if __name__ == "__main__":
    GladeGTK()
    gtk.main()
