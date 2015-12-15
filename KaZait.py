# -*- coding: utf-8 -*-

import gtk
import os
import sys
import subprocess
import time
import datetime
import tempfile
import ctypes.wintypes
import re
import string
from threading import Thread
from Queue import Queue, Empty

# TODO:
# - ? add some waiting on progress bar, to save some cpu cycles...
# - verify that temp file get erased
# - beautify GUI
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
        self.builder.get_object("okButton").set_sensitive(False)
        statusBar = self.builder.get_object("statusbar1")
        self.context_id = statusBar.get_context_id("Waiting")
        statusBar.push(self.context_id, "עובד, נא להמתין...")

        # make progress bar updating
        task = self.update_progress_bar(progressFile)
        gtk.idle_add(task.next)


    def finishAction(self):
        # restore GUI
        self.builder.get_object("okButton").set_sensitive(True)
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
        self.setFileName(widget.get_filename())
        self.builder.get_object("okButton").set_sensitive(True)

    def destroy(self, widget, data=None):
        self.quit()

    def quit(self):
        # self.saveConfig()
        gtk.main_quit()


    def __init__(self):
        self.defaultQuality = 3
        self.proc = None
        self.showWindow()

    def my_init(self):
        #######################
        ## File Chooser Init ##
        #######################
        chooser = self.builder.get_object("filechooserbutton1")

        filter = gtk.FileFilter()
        # filter.add_mime_type("audio/mpeg")
        filter.add_mime_type("audio/wav")
        filter.add_mime_type("audio/mpeg")
        filter.add_mime_type("audio/x-ms-wma")
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
        temp_scale = gtk.Scale
        scale.set_digits(0)
        scale.set_range(1, 10)
        scale.set_value(self.defaultQuality)


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
