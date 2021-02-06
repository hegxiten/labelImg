# Copyright (c) 2016 Tzutalin
# Create by Zezhou Wang <wangzezai@hotmail.com>

try:
    from PyQt5.QtGui import QImage
except ImportError:
    from PyQt4.QtGui import QImage

from base64 import b64encode, b64decode
from enum import Enum
import os.path
import sys


ATTRIBUTE_KEYS = ["image", "year", "month", "day", "train(s)", "locomotive(s)", "year range", "month range", "day range",
                  "region", "area", "geo coordinates", "geo range", "railway line", "perspective angle", "perspective angle rough",
                  "people", "tag",
                  "general comments", "comments"
                  ]

class AttributeFileFormat(Enum):
    JSON = 3


class AttributeFileError(Exception):
    pass


class AttributeFile(object):
    # It might be changed as window creates. By default, using XML ext
    # suffix = '.lif'
    suffix = '.json'

    def __init__(self, imgFilename=None):
        self.imagePath = None
        self.imageData = None
        self.imgFolderPath = os.path.dirname(imgFilename)
        self.imgFolderName = os.path.split(imgFilename)[-2]
        self.imgFileName = os.path.basename(imgFilename)
        self.imgFileNameWithoutExt = os.path.splitext(self.imgFileName)[0]
        self.jsonFilePath = os.path.join(self.imgFolderPath, self.imgFileNameWithoutExt+'.json')

        self.verified = False

    def toggleVerify(self):
        self.verified = not self.verified

    @staticmethod
    def isAttributeFile(filename):
        fileSuffix = os.path.splitext(filename)[1].lower()
        return fileSuffix == AttributeFile.suffix
