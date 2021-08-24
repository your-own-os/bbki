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
import re
import configparser
from ._util import Util
from ._po import KernelType
from ._po import SystemInit
from ._po import SystemInitInfo
from ._exception import ConfigError


class Config:

    @property
    def data_repo_dir(self):
        raise NotImplementedError()

    @property
    def cache_distfiles_dir(self):
        raise NotImplementedError()

    @property
    def cache_distfiles_ro_dir_list(self):
        raise NotImplementedError()

    @property
    def tmp_dir(self):
        raise NotImplementedError()

    def get_build_variable(self, var_name):
        raise NotImplementedError()

    def get_kernel_type(self):
        raise NotImplementedError()

    def get_kernel_addon_names(self):
        raise NotImplementedError()

    def get_system_init_info(self):
        raise NotImplementedError()

    def get_bootloader_extra_time(self):
        raise NotImplementedError()

    def get_kernel_extra_init_cmdline(self):
        raise NotImplementedError()

    def check_version_mask(self, item_fullname, item_verstr):
        raise NotImplementedError()


class EtcDirConfig(Config):

    DEFAULT_CONFIG_DIR = "/etc/bbki"

    DEFAULT_DATA_DIR = "/var/lib/bbki"

    DEFAULT_CACHE_DIR = "/var/cache/bbki"

    DEFAULT_TMP_DIR = "/var/tmp/bbki"

    def __init__(self, cfgdir=DEFAULT_CONFIG_DIR):
        self._makeConf = os.path.join(cfgdir, "make.conf")

        self._profileDir = os.path.join(cfgdir, "profile")
        self._profileKernelTypeFile = os.path.join(self._profileDir, "bbki.kernel_type")
        self._profileKernelAddonDir = os.path.join(self._profileDir, "bbki.kernel_addon")
        self._profileOptionsFile = os.path.join(self._profileDir, "bbki.options")
        self._profileMaskDir = os.path.join(self._profileDir, "bbki.mask")

        self._cfgKernelTypeFile = os.path.join(cfgdir, "bbki.kernel_type")
        self._cfgKernelAddonDir = os.path.join(cfgdir, "bbki.kernel_addon")
        self._cfgOptionsFile = os.path.join(cfgdir, "bbki.options")
        self._cfgMaskDir = os.path.join(cfgdir, "bbki.mask")

        self._dataDir = self.DEFAULT_DATA_DIR
        self._dataRepoDir = os.path.join(self._dataDir, "repo")

        self._cacheDir = self.DEFAULT_CACHE_DIR
        self._cacheDistfilesDir = os.path.join(self._cacheDir, "distfiles")
        self._cacheDistfilesRoDirList = []

        self._tmpDir = self.DEFAULT_TMP_DIR

        self._tKernelType = None
        self._tKernelAddonNameList = None
        self._tOptions = None
        self._tMaskBufList = None

    @property
    def data_repo_dir(self):
        return self._dataRepoDir

    @property
    def cache_distfiles_dir(self):
        return self._cacheDistfilesDir

    @property
    def cache_distfiles_ro_dir_list(self):
        return self._cacheDistfilesRoDirList

    @property
    def tmp_dir(self):
        return self._tmpDir

    def get_build_variable(self, var_name):
        return self._getMakeConfVariable(var_name)

    def get_kernel_type(self):
        # fill cache
        self._filltKernelType()

        if self._tKernelType is None:
            raise ConfigError("no kernel type specified")
        if self._tKernelType not in [KernelType.LINUX]:
            raise ConfigError("invalid kernel type \"%s\" specified" % (self._tKernelType))
        return self._tKernelType

    def get_kernel_addon_names(self):
        # fill cache
        self._filltKernelAddonNameList()

        return self._tKernelAddonNameList

    def get_system_init_info(self):
        # fill cache
        self._filltOptions()

        if self._tOptions["system"]["init"] == "auto-detect":
            if os.path.exists("/sbin/openrc-init"):
                return SystemInitInfo(SystemInit.OPENRC, "/sbin/openrc-init")
            if os.path.exists("/usr/lib/systemd/systemd"):
                return SystemInitInfo(SystemInit.SYSTEMD, "/usr/lib/systemd/systemd")
            else:
                raise ConfigError("auto detect system init failed")

        if self._tOptions["system"]["init"] == SystemInit.SYSVINIT:
            return SystemInitInfo(SystemInit.SYSVINIT, "")

        if self._tOptions["system"]["init"] == SystemInit.OPENRC:
            return SystemInitInfo(SystemInit.OPENRC, "/sbin/openrc-init")

        if self._tOptions["system"]["init"] == SystemInit.SYSTEMD:
            return SystemInitInfo(SystemInit.SYSTEMD, "/usr/lib/systemd/systemd")

        if self._tOptions["system"]["init"].startswith("/"):
            return SystemInitInfo(SystemInit.CUSTOM, self._tOptions["system"]["init"])

        raise ConfigError("invalid system init configuration")

    def get_bootloader_extra_time(self):
        # fill cache
        self._filltOptions()

        return self._tOptions["bootloader"]["wait-time"]

    def get_kernel_extra_init_cmdline(self):
        # fill cache
        self._filltOptions()

        return self._tOptions["kernel"]["init-cmdline"]

    def check_version_mask(self, item_fullname, item_verstr):
        # fill cache
        self._filltMaskBufList()

        for buf in self._tMaskBufList:
            m = re.search("^>%s-(.*)$" % (item_fullname), buf, re.M)
            if m is not None:
                if Util.compareVerstr(item_verstr, m.group(1)) > 0:
                    return False
        return True

    def _filltKernelType(self):
        if self._tKernelType is not None:
            return

        def _myParse(path):
            if os.path.exists(path):
                ret = Util.readListFile(path)
                if len(ret) > 0:
                    self._tKernelType = ret[0]

        _myParse(self._profileKernelTypeFile)       # step1: use /etc/bbki/profile/bbki.*
        _myParse(self._cfgKernelTypeFile)           # step2: use /etc/bbki/bbki.*

    def _filltKernelAddonNameList(self):
        if self._tKernelAddonNameList is not None:
            return

        def _myParse(path):
            if os.path.exists(path):
                for fn in os.listdir(path):
                    for line in Util.readListFile(os.path.join(path, fn)):
                        if not line.startswith("-"):
                            self._tKernelAddonNameList.add(line)
                        else:
                            line = line[1:]
                            self._tKernelAddonNameList.remove(line)

        self._tKernelAddonNameList = set()
        _myParse(self._profileKernelAddonDir)                           # step1: use /etc/bbki/profile/bbki.*
        _myParse(self._cfgKernelAddonDir)                               # step2: use /etc/bbki/bbki.*
        self._tKernelAddonNameList = list(self._tKernelAddonNameList)
        self._tKernelAddonNameList.sort()

    def _filltOptions(self):
        if self._tOptions is not None:
            return

        def _myParse(path):
            if os.path.exists(path):
                cfg = configparser.ConfigParser()
                cfg.read(path)
                if cfg.has_option("bootloader", "wait-time"):
                    self._tOptions["bootloader"]["wait-time"] = cfg.get("bootloader", "wait-time")
                if cfg.has_option("kernel", "init-cmdline"):
                    self._tOptions["kernel"]["init-cmdline"] = cfg.get("kernel", "init-cmdline")
                if cfg.has_option("system", "init"):
                    self._tOptions["system"]["init"] = cfg.get("system", "init")

        self._tOptions = {
            "bootloader": {
                "wait-time": 0,
            },
            "kernel": {
                "init-cmdline": "",
            },
            "system": {
                "init": "auto-detect",
            },
        }
        _myParse(self._profileOptionsFile)      # step1: use /etc/bbki/profile/bbki.*
        _myParse(self._cfgOptionsFile)          # step2: use /etc/bbki/bbki.*

    def _filltMaskBufList(self):
        if self._tMaskBufList is not None:
            return

        def _myParse(path):
            if os.path.exists(path):
                for fn in os.listdir(path):
                    with open(os.path.join(path, fn), "r") as f:
                        self._tMaskBufList.append(f.read())

        self._tMaskBufList = []
        _myParse(self._profileMaskDir)      # step1: use /etc/bbki/profile/bbki.*
        _myParse(self._cfgMaskDir)          # step2: use /etc/bbki/bbki.*

    def _getMakeConfVariable(self, varName):
        # Returns variable value, returns "" when not found
        # Multiline variable definition is not supported yet

        buf = ""
        with open(self._makeConf, 'r') as f:
            buf = f.read()

        m = re.search("^%s=\"(.*)\"$" % varName, buf, re.MULTILINE)
        if m is None:
            return ""
        varVal = m.group(1)

        while True:
            m = re.search("\\${(\\S+)?}", varVal)
            if m is None:
                break
            varName2 = m.group(1)
            varVal2 = self._getMakeConfVariable(self._makeConf, varName2)
            if varVal2 is None:
                varVal2 = ""

            varVal = varVal.replace(m.group(0), varVal2)

        return varVal