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
import anytree
from .bbki import Bbki
from .util import Util


class HostInfo:

    def __init__(self, arch, boot_mode, mount_point_list=None, aux_os_list=[], aux_kernel_init_cmdline=""):
        self.arch = None
        self.boot_mode = None
        self.mount_point_list = None
        self.aux_os_list = None
        self.aux_kernel_init_cmdline = None

        # self.arch
        if arch == "native":
            arch = os.uname().machine
        assert Util.isValidKernelArch(arch)
        self.arch = arch

        # self.boot_mode
        if boot_mode == "native":
            if Util.isEfi():
                boot_mode = Bbki.BOOT_MODE_EFI
            else:
                boot_mode = Bbki.BOOT_MODE_BIOS
        else:
            assert boot_mode in [Bbki.BOOT_MODE_EFI, Bbki.BOOT_MODE_BIOS]
        self.boot_mode = boot_mode

        # self.mount_point_list
        if mount_point_list is not None:
            if boot_mode == Bbki.BOOT_MODE_EFI:
                assert len(mount_point_list) >= 2
                assert mount_point_list[0].name == HostMountPoint.NAME_ROOT
                assert mount_point_list[1].name == HostMountPoint.NAME_BOOT
                assert len([x for x in mount_point_list if x.name == HostMountPoint.NAME_ROOT]) == 1
                assert len([x for x in mount_point_list if x.name == HostMountPoint.NAME_BOOT]) == 1
            elif boot_mode == Bbki.BOOT_MODE_BIOS:
                assert mount_point_list[0].name == HostMountPoint.NAME_ROOT
                assert len([x for x in mount_point_list if x.name == HostMountPoint.NAME_ROOT]) == 1
                assert len([x for x in mount_point_list if x.name == HostMountPoint.NAME_BOOT]) == 0
                assert all([x.dev_path is not None for x in mount_point_list])
            else:
                assert False
        self.mount_point_list = mount_point_list

        # self.aux_os_list
        assert len(aux_os_list) >= 0
        self.aux_os_list = aux_os_list

        # self.aux_kernel_init_cmdline
        assert isinstance(aux_kernel_init_cmdline, str)
        self.aux_kernel_init_cmdline = aux_kernel_init_cmdline


class HostMountPoint:

    NAME_ROOT = "root"
    NAME_BOOT = "boot"

    FS_TYPE_VFAT = "vfat"
    FS_TYPE_EXT4 = "ext4"           # deprecated
    FS_TYPE_BTRFS = "btrfs"

    def __init__(self, name, mount_point, dev_path_or_uuid, fs_type, mnt_opt="", underlay_disks=None):
        # self.name
        assert isinstance(name, str)
        self.name = name

        # self.mount_point
        assert os.path.isabs(mount_point)
        if name == self.NAME_ROOT:
            assert mount_point == "/"
        if name == self.NAME_BOOT:
            assert mount_point == "/boot"
        self.mount_point = mount_point

        # self.dev_path_or_uuid
        if dev_path_or_uuid.startswith("/dev/"):
            self.dev_path = dev_path_or_uuid
            self.dev_uuid = Util.getBlkDevUuid(self.dev_path)       # FS-UUID, not PART-UUID
        else:
            self.dev_path = None
            self.dev_uuid = dev_path_or_uuid

        # self.fs_type
        assert fs_type in [self.FS_TYPE_VFAT, self.FS_TYPE_EXT4, self.FS_TYPE_BTRFS]
        self.fs_type = fs_type

        # self.mnt_opt
        assert isinstance(mnt_opt, str)
        self.mnt_opt = mnt_opt

        # self.underlay_disks
        if underlay_disks is not None:
            assert self.dev_path is None                                    # self.dev_path and self.underlay_disks are mutally exclusive
            assert all([isinstance(x, HostDisk) for x in underlay_disks])
            self.underlay_disks = underlay_disks
        else:
            assert self.dev_path is not None
            self.underlay_disks = HostInfoUtil.getUnderlayDisks(self.dev_path)


class HostDisk(anytree.node.nodemixin.NodeMixin):

    def __init__(self, uuid, parent):
        super().__init__(parent=parent)
        self.uuid = uuid

    def ___eq___(self, other):
        return type(self) == type(other) and self.uuid == other.uuid


class HostDiskLvmLv(HostDisk):

    def __init__(self, uuid, vg_name, lv_name, parent=None):
        super().__init__(uuid, parent)
        self.vg_name = vg_name
        self.lv_name = lv_name


class HostDiskBcache(HostDisk):

    def __init__(self, uuid, parent=None):
        super().__init__(uuid, parent)
        self.cache_dev_list = []
        self.backing_dev = None

    def add_cache_dev(self, disk):
        self.cache_dev_list.append(disk)

    def add_backing_dev(self, disk):
        assert self.backing_dev is None
        self.backing_dev = disk


class HostDiskScsiDisk(HostDisk):

    def __init__(self, uuid, host_controller_name, parent=None):
        super().__init__(uuid, parent)
        self.host_controller_name = host_controller_name


class HostDiskNvmeDisk(HostDisk):

    def __init__(self, uuid, parent=None):
        super().__init__(uuid, parent)


class HostDiskXenDisk(HostDisk):

    def __init__(self, uuid, parent=None):
        super().__init__(uuid, parent)


class HostDiskVirtioDisk(HostDisk):

    def __init__(self, uuid, parent=None):
        super().__init__(uuid, parent)


class HostDiskPartition(HostDisk):

    PART_TYPE_MBR = 1
    PART_TYPE_GPT = 2

    def __init__(self, uuid, part_type, parent=None):
        assert self.PART_TYPE_MBR <= part_type <= self.PART_TYPE_GPT

        super().__init__(uuid, parent)
        self.part_type = part_type


class HostAuxOs:

    def __init__(self, name, partition_uuid, chainloader_number):
        self.name = name
        self.partition_uuid = partition_uuid
        self.chainloader_number = chainloader_number


class HostInfoUtil:

    @staticmethod
    def getMountPoint(hostInfo, name):
        assert hostInfo.mount_point_list is not None
        assert name in [HostMountPoint.NAME_ROOT, HostMountPoint.NAME_BOOT]

        for m in hostInfo.mount_point_list:
            if m.name == name:
                return m
        return None

    @staticmethod
    def getMountPointList(hostInfo, name):
        assert hostInfo.mount_point_list is not None
        assert name not in [HostMountPoint.NAME_ROOT, HostMountPoint.NAME_BOOT]

        ret = []
        for m in hostInfo.mount_point_list:
            if m.name == name:
                ret.append(m)
        return re

    @staticmethod
    def getUnderlayDisks(devPath):
        assert False


# def get_disk_stack(self):
#     ret = []
#     ret.append(DiskStackNodeLvmLv(util.rootLvDevPath, util.vgName, util.rootLvName))
#     if self._bSwapLv:
#         ret.append(DiskStackNodeLvmLv(util.swapLvDevPath, util.vgName, util.swapLvName))

#     for node in ret:
#         for d in self._diskList:
#             partNode = DiskStackNodePartition(util.devPathDiskToPartition(d, 1), DiskStackNodePartition.PART_TYPE_MBR, parent=node)
#             DiskStackNodeHarddisk(d, parent=partNode)

#     return ret


# def get_disk_stack(self):
#     partNode = DiskStackNodePartition(self._hddRootParti, DiskStackNodePartition.PART_TYPE_MBR)
#     DiskStackNodeHarddisk(self._hdd, parent=partNode)
#     return [partNode]



# def get_disk_stack(self):
#     ret = []

#     if True:
#         rootNode = DiskStackNodeLvmLv(util.rootLvDevPath, util.vgName, util.rootLvName)
#         for hddDev, bcacheDev in self._hddDict.items():
#             ssdPartList = [self._ssd] if self._ssdCacheParti is not None else []
#             bcacheNode = DiskStackNodeBcache(bcacheDev, ssdPartList, util.devPathDiskToPartition(hddDev, 1), parent=rootNode)
#             for s in ssdPartList:
#                 partNode = DiskStackNodePartition(s, DiskStackNodePartition.PART_TYPE_GPT, parent=bcacheNode)
#                 DiskStackNodeHarddisk(self._ssd, parent=partNode)
#         ret.append(rootNode)

#     for hddDev, bcacheDev in self._hddDict.items():
#         espNode = DiskStackNodePartition(util.devPathDiskToPartition(hddDev, 1), DiskStackNodePartition.PART_TYPE_GPT)
#         DiskStackNodeHarddisk(hddDev, parent=espNode)
#         ret.append(espNode)

#     if self._ssdEspParti is not None:
#         ssdEspNode = DiskStackNodePartition(self._ssdEspParti, DiskStackNodePartition.PART_TYPE_GPT)
#         DiskStackNodeHarddisk(self._ssd, parent=ssdEspNode)
#         ret.append(ssdEspNode)

#     if self._ssdSwapParti is not None:
#         swapNode = DiskStackNodePartition(self._ssdSwapParti, DiskStackNodePartition.PART_TYPE_GPT, parent=bcacheNode)
#         DiskStackNodeHarddisk(self._ssd, parent=swapNode)
#         ret.append(swapNode)

#     return ret



# def get_disk_stack(self):
#     ret = []
#     ret.append(DiskStackNodeLvmLv(util.rootLvDevPath, util.vgName, util.rootLvName))
#     if self._bSwapLv:
#         ret.append(DiskStackNodeLvmLv(util.swapLvDevPath, util.vgName, util.swapLvName))

#     for node in ret:
#         for d in self._diskList:
#             partNode = DiskStackNodePartition(util.devPathDiskToPartition(d, 2), DiskStackNodePartition.PART_TYPE_GPT, parent=node)
#             DiskStackNodeHarddisk(d, parent=partNode)

#     for d in self._diskList:
#         espNode = DiskStackNodePartition(util.devPathDiskToPartition(d, 1), DiskStackNodePartition.PART_TYPE_GPT)
#         DiskStackNodeHarddisk(d, parent=espNode)
#         ret.append(espNode)

#     return ret



# def get_disk_stack(self):
#     partNode = DiskStackNodePartition(self._hddRootParti, DiskStackNodePartition.PART_TYPE_MBR)
#     DiskStackNodeHarddisk(self._hdd, parent=partNode)

#     espNode = DiskStackNodePartition(self._hddEspParti, DiskStackNodePartition.PART_TYPE_GPT)
#     DiskStackNodeHarddisk(self._hdd, parent=espNode)

#     return [partNode, espNode]


# hostDevPath = os.path.join(d.param["scsi_host_path"], "scsi_host", os.path.basename(d.param["scsi_host_path"]))
# with open(os.path.join(hostDevPath, "proc_name")) as f:
#     hostControllerName = f.read().rstrip()


# Util.getBlkDevUuid(cacheDev)
