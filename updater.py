__author__ = 'zharamax'

import os
import sys
import re
import string
import requests
import json
import threading
import time

# add a lof of "try"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS

    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class Updater:
    def get_version_from_file(self, version_file_kind):
        if version_file_kind == "Inno":
            with open(resource_path("version.iss")) as f:
                for line in f:
                    if re.search("MyAppVersion", line):
                        return string.split(line, "\"")[1]
        else:
            print "Not implemented"

    def get_latest_version(self):
        try:
            if self.update_server_kind == "GitHub":
                r = requests.get(self.update_server_url + "/releases/latest")
                if r.ok:
                    repoItem = json.loads(r.text or r.content)
                    return repoItem
            else:
                print "Not implemented"
        except Exception as e:
            self.error_message = e

    def check_for_updates_thread(self, auto_started):
        self.repoItem = self.get_latest_version()

        # time.sleep(4)
        # latest_version = "0.6"

        self.ok = self.repoItem is not None
        if self.ok:
            # currently: u'v0.3'
            self.latest_version = self.repoItem['tag_name'].lstrip('v')
            self.need_update = self.latest_version != self.current_version
            if len(self.repoItem['assets']) == 1:
                self.download_url = self.repoItem['assets'][0]['browser_download_url']

        self.finished.set()

    def check_for_updates(self, auto_started=False):
        # open new thread, only if there isn't active one
        if not any(t.name == 'check_for_updates' for t in threading.enumerate()):
            threading.Thread(name='check_for_updates',
                             target=self.check_for_updates_thread,
                             args=(auto_started,)
                             ).start()

    def __init__(self,
                 update_server_url,
                 auto_check=True,
                 update_server_kind="GitHub",
                 version_file_kind="Inno"):
        self.current_version = self.get_version_from_file(version_file_kind)
        self.update_server_kind = update_server_kind
        self.update_server_url = update_server_url
        # self.callback = callback
        self.finished = threading.Event()
        self.ok = False
        self.need_update = False
        self.latest_version = None
        self.download_url = None
        self.repo_item = None
        self.error_message = None
        if auto_check:
            self.check_for_updates(auto_started=True)



if __name__ == "__main__":
    Updater("https://api.github.com/repos/ZvikaZ/KaZait")
