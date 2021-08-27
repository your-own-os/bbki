#!/usr/bin/env python3

# Copyright (c) 2005-2014 Fpemud <fpemud@sina.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import os
from ._util import Util
from ._util import SystemMounts


class BootEntry:

    def __init__(self, bbki, arch, verstr, history_entry=False):
        self._bbki = bbki
        self._arch = arch
        self._verstr = verstr
        if not history_entry:
            self._bootDir = self._bbki._fsLayout.get_boot_dir()
        else:
            self._bootDir = self._bbki._fsLayout.get_boot_history_dir()

    @property
    def postfix(self):
        # string, eg: "x86_64-3.9.11-gentoo-r1"
        return self._arch + "-" + self._verstr

    @property
    def arch(self):
        # string, eg: "x86_64"
        return self._arch

    @property
    def verstr(self):
        # string, eg: "3.9.11-gentoo-r1"
        return self._verstr

    @property
    def ver(self):
        # string, eg: "3.9.11"
        try:
            return self._verstr[:self._verstr.index("-")]
        except ValueError:
            return self._verstr

    @property
    def kernel_filename(self):
        # string, eg: "kernel-x86_64-3.9.11-gentoo-r1"
        return "kernel-" + self.postfix

    @property
    def kernel_filepath(self):
        # string, eg: "/boot/kernel-x86_64-3.9.11-gentoo-r1"
        return os.path.join(self._bootDir, self.kernel_filename)

    @property
    def kernel_config_filename(self):
        # string, eg: "config-x86_64-3.9.11-gentoo-r1"
        return "config-" + self.postfix

    @property
    def kernel_config_filepath(self):
        # string, eg: "/boot/config-x86_64-3.9.11-gentoo-r1"
        return os.path.join(self._bootDir, self.kernel_config_filename)

    @property
    def kernel_config_rules_filename(self):
        # string, eg: "config-x86_64-3.9.11-gentoo-r1.rules"
        return "config-" + self.postfix + ".rules"

    @property
    def kernel_config_rules_filepath(self):
        # string, eg: "/boot/config-x86_64-3.9.11-gentoo-r1.rules"
        return os.path.join(self._bootDir, self.kernel_config_rules_filename)

    @property
    def kernel_modules_dirpath(self):
        # string, eg: "/lib/modules/5.1.14-gentoo-r1"
        return self._bbki._fsLayout.get_kernel_modules_dir(self._verstr)

    @property
    def initrd_filename(self):
        # string, eg: "initramfs-x86_64-3.9.11-gentoo-r1"
        return "initramfs-" + self.postfix

    @property
    def initrd_filepath(self):
        # string, eg: "/boot/initramfs-x86_64-3.9.11-gentoo-r1"
        return os.path.join(self._bootDir, self.initrd_filename)

    @property
    def initrd_tar_filename(self):
        # string, eg: "initramfs-x86_64-3.9.11-gentoo-r1.tar.bz2"
        return "initramfs-files-" + self.postfix + ".tar.bz2"

    @property
    def initrd_tar_filepath(self):
        # string, eg: "/boot/initramfs-x86_64-3.9.11-gentoo-r1.tar.bz2"
        return os.path.join(self._bootDir, self.initrd_tar_filename)

    def is_historical(self):
        return (self._bootDir == self._bbki._fsLayout.get_boot_history_dir())

    def has_kernel_files(self):
        if not os.path.exists(self.kernel_filepath):
            return False
        if not os.path.exists(self.kernel_config_filepath):
            return False
        if not os.path.exists(self.kernel_config_rules_filepath):
            return False
        if not os.path.exists(self._bbki._fsLayout.get_kernel_modules_dir(self._verstr)):
            return False
        if not os.path.exists(self._bbki._fsLayout.get_firmware_dir()):
            return False
        return True

    def has_initrd_files(self):
        if not os.path.exists(self.initrd_filepath):
            return False
        if not os.path.exists(self.initrd_tar_filepath):
            return False
        return True

    def ___eq___(self, other):
        return self._bbki == other._bbki and self._arch == other._arch and self._verstr == other._verstr and self._bootDir == other._bootDir


class BootDirWriter:

    def __init__(self, bbki):
        self._bbki = bbki
        self._refcount = 0              # support nest use
        self._remounted = False

    def start(self):
        while self._refcount == 0:
            # check if remount-boot-rw is allowed
            if not self._bbki.config.get_remount_boot_rw():
                break

            # find and check mount point for /boot
            entry = SystemMounts().find_entry_by_mount_point(self._bbki._fsLayout.get_boot_dir())
            if entry is None or "rw" in entry.mnt_opts:
                break

            # remount as rw
            Util.cmdCall("/bin/mount", self._bbki._fsLayout.get_boot_dir(), "-o", "rw,remount")
            self._remounted = True
            break

        self._refcount += 1

    def end(self):
        assert self._refcount >= 0
        try:
            if self._refcount == 1 and self._remounted:
                # remount as ro
                Util.cmdCall("/bin/mount", self._bbki._fsLayout.get_boot_dir(), "-o", "ro,remount")
                self._remounted = False
        finally:
            self._refcount -= 1

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.end()