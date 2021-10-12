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

    def get_kernel_name(self):
        raise NotImplementedError()

    def get_kernel_addon_names(self):
        raise NotImplementedError()

    def get_initramfs_name(self):
        raise NotImplementedError()

    def get_system_init(self):
        raise NotImplementedError()

    def get_bootloader_extra_time(self):
        raise NotImplementedError()

    def get_kernel_extra_init_cmdline(self):
        raise NotImplementedError()

    def test_version_mask(self, item_fullname, item_verstr):
        raise NotImplementedError()

    def do_check(self, autofix, error_callback):
        raise NotImplementedError()


class EtcDirConfig(Config):

    DEFAULT_CONFIG_DIR = "/etc/bbki"

    DEFAULT_DATA_DIR = "/var/lib/bbki"

    DEFAULT_CACHE_DIR = "/var/cache/bbki"

    DEFAULT_TMP_DIR = "/var/tmp/bbki"

    def __init__(self, cfgdir=DEFAULT_CONFIG_DIR):
        self._makeConf = os.path.join(cfgdir, "make.conf")

        self._profileDir = os.path.join(cfgdir, "profile")
        self._profileKernelFile = os.path.join(self._profileDir, "bbki.kernel")
        self._profileKernelAddonDir = os.path.join(self._profileDir, "bbki.kernel_addon")
        self._profileOptionsFile = os.path.join(self._profileDir, "bbki.options")
        self._profileMaskDir = os.path.join(self._profileDir, "bbki.mask")

        self._cfgKernelFile = os.path.join(cfgdir, "bbki.kernel")
        self._cfgKernelAddonDir = os.path.join(cfgdir, "bbki.kernel_addon")
        self._cfgOptionsFile = os.path.join(cfgdir, "bbki.options")
        self._cfgMaskDir = os.path.join(cfgdir, "bbki.mask")

        self._dataDir = self.DEFAULT_DATA_DIR
        self._dataRepoDir = os.path.join(self._dataDir, "repo")

        self._cacheDir = self.DEFAULT_CACHE_DIR
        self._cacheDistfilesDir = os.path.join(self._cacheDir, "distfiles")
        self._cacheDistfilesRoDirList = []

        self._tmpDir = self.DEFAULT_TMP_DIR

        # validate and fill cache
        self._tKernelTypeName = None
        self._filltKernel()

        # validate and fill cache
        self._tKernelAddonNameList = None
        self._filltKernelAddonNameList()

        # validate and fill cache
        self._tOptions = None
        self._filltMaskBufList()

        # validate and fill cache
        self._tMaskBufList = None
        self._filltOptions()

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
        if self._tKernelTypeName is None:
            raise ConfigError("no kernel type and kernel name specified")
        if self._tKernelTypeName[0] not in [KernelType.LINUX]:
            raise ConfigError("invalid kernel type \"%s\" specified" % (self._tKernelTypeName[0]))
        return self._tKernelTypeName[0]

    def get_kernel_name(self):
        if self._tKernelTypeName is None:
            raise ConfigError("no kernel type and kernel name specified")
        return self._tKernelTypeName[1]

    def get_kernel_addon_names(self):
        return self._tKernelAddonNameList

    def get_initramfs_name(self):
        return "minitrd"            # FIXME

    def get_system_init(self):
        if self._tOptions["system"]["init"] == "auto-detect":
            if os.path.exists("/sbin/openrc-init"):
                return SystemInit(SystemInit.TYPE_OPENRC, "/sbin/openrc-init")
            if os.path.exists("/usr/lib/systemd/systemd"):
                return SystemInit(SystemInit.TYPE_SYSTEMD, "/usr/lib/systemd/systemd")
            else:
                raise ConfigError("auto detect system init failed")

        if self._tOptions["system"]["init"] == SystemInit.TYPE_SYSVINIT:
            return SystemInit(SystemInit.TYPE_SYSVINIT, "")

        if self._tOptions["system"]["init"] == SystemInit.TYPE_OPENRC:
            return SystemInit(SystemInit.TYPE_OPENRC, "/sbin/openrc-init")

        if self._tOptions["system"]["init"] == SystemInit.TYPE_SYSTEMD:
            return SystemInit(SystemInit.TYPE_SYSTEMD, "/usr/lib/systemd/systemd")

        if self._tOptions["system"]["init"].startswith("/"):
            return SystemInit(SystemInit.TYPE_CUSTOM, self._tOptions["system"]["init"])

        assert False

    def get_remount_boot_rw(self):
        return self._tOptions["system"]["remount-boot-rw"]

    def get_bootloader_extra_time(self):
        return self._tOptions["bootloader"]["wait-time"]

    def get_kernel_extra_init_cmdline(self):
        return self._tOptions["kernel"]["init-cmdline"]

    def test_version_mask(self, item_fullname, item_verstr):
        for buf in self._tMaskBufList:
            m = re.search("^>%s-(.*)$" % (item_fullname), buf, re.M)
            if m is not None:
                if Util.compareVerstr(item_verstr, m.group(1)) > 0:
                    return False
        return True

    def do_check(self, bbki, autofix, error_callback):
        # check kernel name
        bFound = False
        for repo in bbki.repositories:
            ret = repo.get_atoms_by_type_name(self._tKernelTypeName[0], repo.ATOM_TYPE_KERNEL, self._tKernelTypeName[1])
            if len(ret) > 0:
                bFound = True
        if not bFound:
            # no way to auto fix
            error_callback("%s/%s does not exist." % (self._tKernelTypeName[0], self._tKernelTypeName[1]))

        # check kernel addon names
        dirList = [
            self._profileKernelAddonDir,
            self._cfgKernelAddonDir,
        ]
        for dirPath in dirList:
            if not os.path.exits(dirPath):
                continue
            for fn in os.listdir(dirPath):
                fullfn = os.path.join(dirPath, fn)
                for addonName, bAdd in self.__parseAddonFile(fullfn):
                    bFound = False
                    for repo in bbki.repositories:
                        ret = repo.get_atoms_by_type_name(self._tKernelTypeName[0], repo.ATOM_TYPE_KERNEL_ADDON, addonName)
                        if len(ret) > 0:
                            bFound = True
                    if not bFound:
                        # no way to auto fix
                        error_callback("%s%s/%s in \"%s\" references a non-exist BBKI atom." % ("" if bAdd else "-", self._tKernelTypeName[0], addonName, fullfn))

        # check initramfs name
        bFound = False
        for repo in bbki.repositories:
            ret = repo.get_atoms_by_type_name(self._tKernelTypeName[0], repo.ATOM_TYPE_INITRAMFS, self.get_initramfs_name())
            if len(ret) > 0:
                bFound = True
        if not bFound:
            # no way to auto fix
            error_callback("%s/%s does not exist." % (self._tKernelTypeName[0], self.get_initramfs_name()))

    def _filltKernel(self):
        assert self._tKernelTypeName is None

        def __myParse(path):
            if os.path.exists(path):
                ret = Util.readListFile(path)
                if len(ret) > 0:
                    tlist = ret[0].split("/")
                    if len(tlist) != 2:
                        raise ConfigError("invalid value of kernel atom name")
                    self._tKernelTypeName = (tlist[0], tlist[1])

        __myParse(self._profileKernelFile)       # step1: use /etc/bbki/profile/bbki.*
        __myParse(self._cfgKernelFile)           # step2: use /etc/bbki/bbki.*

    def _filltKernelAddonNameList(self):
        assert self._tKernelAddonNameList is None

        dirList = [
            self._profileKernelAddonDir,   # step1: use /etc/bbki/profile/bbki.*
            self._cfgKernelAddonDir,       # step2: use /etc/bbki/bbki.*
        ]
        for dirPath in dirList:
            if not os.path.exits(dirPath):
                continue
            for fn in os.listdir(dirPath):
                for addonName, bAdd in self.__parseAddonFile(os.path.join(dirPath, fn)):
                    if bAdd:
                        self._tKernelAddonNameList.add(addonName)
                    else:
                        self._tKernelAddonNameList.remove(addonName)
        self._tKernelAddonNameList = list(self._tKernelAddonNameList)
        self._tKernelAddonNameList.sort()

    def _filltOptions(self):
        assert self._tOptions is None

        def __myParse(path):
            if os.path.exists(path):
                cfg = configparser.ConfigParser()
                cfg.read(path)
                if cfg.has_option("bootloader", "wait-time"):
                    v = cfg.get("bootloader", "wait-time")
                    try:
                        v = int(v)
                    except ValueError:
                        raise ConfigError("invalid value of bbki option bootloader/wait-time")
                    if not (0 <= v <= 3600):
                        raise ConfigError("invalid value of bbki option bootloader/wait-time")
                    self._tOptions["bootloader"]["wait-time"] = v
                if cfg.has_option("kernel", "init-cmdline"):
                    self._tOptions["kernel"]["init-cmdline"] = cfg.get("kernel", "init-cmdline")
                if cfg.has_option("system", "init"):
                    v = cfg.get("system", "init")
                    if v != "auto-detect" and v not in [SystemInit.TYPE_SYSVINIT, SystemInit.TYPE_OPENRC, SystemInit.TYPE_SYSTEMD] and not v.startswith("/"):
                        raise ConfigError("invalid value of bbki option system/init")
                    self._tOptions["system"]["init"] = v
                if cfg.has_option("system", "remount-boot-rw"):
                    v = cfg.get("system", "remount-boot-rw")
                    if v == "true":
                        self._tOptions["system"]["remount-boot-rw"] = True
                    elif v == "false":
                        self._tOptions["system"]["remount-boot-rw"] = False
                    else:
                        raise ConfigError("invalid value of bbki option system/remount-boot-rw")

        self._tOptions = {
            "bootloader": {
                "wait-time": 0,
            },
            "kernel": {
                "init-cmdline": "",
            },
            "system": {
                "init": "auto-detect",
                "remount-boot-rw": True,
            },
        }
        __myParse(self._profileOptionsFile)      # step1: use /etc/bbki/profile/bbki.*
        __myParse(self._cfgOptionsFile)          # step2: use /etc/bbki/bbki.*

    def _filltMaskBufList(self):
        assert self._tMaskBufList is None

        def __myParse(path):
            if os.path.exists(path):
                for fn in os.listdir(path):
                    with open(os.path.join(path, fn), "r") as f:
                        self._tMaskBufList.append(f.read())

        self._tMaskBufList = []
        __myParse(self._profileMaskDir)      # step1: use /etc/bbki/profile/bbki.*
        __myParse(self._cfgMaskDir)          # step2: use /etc/bbki/bbki.*

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

    def __parseAddonFile(self, filepath):
        ret = []
        for line in Util.readListFile(filepath):
            bAdd = True
            if line.startswith("-"):
                bAdd = False
                line = line[1:]
            tlist = line.split("/")
            if len(tlist) != 2:
                raise ConfigError("invalid value of kernel addon atom name")
            if tlist[0] != self._tKernelTypeName[0] + "-addon":
                raise ConfigError("invalid value of kernel addon atom name")
            ret.append(tlist[1], bAdd)
        return ret
