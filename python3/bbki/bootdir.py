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
from .common import BuildTarget


class BootEntry:

    def __init__(self, build_target):
        self.buildTarget = build_target

    @property
    def kernel_file(self):
        return os.path.join(_bootDir, self.buildTarget.kernel_filename)

    @property
    def kernel_config_file(self):
        return os.path.join(_bootDir, self.buildTarget.kernel_config_filename)

    @property
    def kernel_config_rules_file(self):
        return os.path.join(_bootDir, self.buildTarget.kernel_config_rules_filename)

    @property
    def kernelSrcSignatureFile(self):
        return os.path.join(_bootDir, self.buildTarget.kernelSrcSignatureFile)

    @property
    def kernel_map_file(self):
        return os.path.join(_bootDir, self.buildTarget.kernel_map_filename)

    @property
    def initrd_file(self):
        return os.path.join(_bootDir, self.buildTarget.initrd_filename)

    @property
    def initrd_tar_file(self):
        return os.path.join(_bootDir, self.buildTarget.initrd_tar_filename)

    def has_kernel_files(self):
        if not os.path.exists(self.kernel_file):
            return False
        if not os.path.exists(self.kernel_config_file):
            return False
        if not os.path.exists(self.kernel_config_rules_file):
            return False
        if not os.path.exists(self.kernel_map_file):
            return False
        if not os.path.exists(self.kernelSrcSignatureFile):
            return False
        return True

    def has_initrd_files(self):
        if not os.path.exists(self.initrd_file):
            return False
        if not os.path.exists(self.initrd_tar_file):
            return False
        return True

    @staticmethod
    def find_current(strict=True):
        ret = [x for x in sorted(os.listdir(_bootDir)) if x.startswith("kernel-")]
        if ret == []:
            return None

        buildTarget = BuildTarget.new_from_kernel_filename(ret[-1])
        ret = BootEntry(buildTarget)
        if strict:
            if not ret.has_kernel_files():
                return None
            if not ret.has_initrd_files():
                return None
        return ret


_bootDir = "/boot"
