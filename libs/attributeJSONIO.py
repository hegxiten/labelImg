#!/usr/bin/env python
# -*- coding: utf8 -*-
import json
from pathlib import Path

from libs.constants import DEFAULT_ENCODING
from libs.attributeFile import ATTRIBUTE_KEYS
import os

JSON_EXT = '.json'
ENCODE_METHOD = DEFAULT_ENCODING


class AttributeJSONWriter:
    def __init__(self, jsonPath, attributeDict):
        self.imagePath = None
        self.imageData = None
        self.jsonPath = jsonPath
        self.imgFolderPath = os.path.dirname(jsonPath)
        self.imgFolderName = os.path.split(jsonPath)[-2]
        self.jsonFilePath = os.path.basename(jsonPath)
        self.imgFileNameWithoutExt = os.path.splitext(self.jsonFilePath)[0]
        self.verified = False

        self.attributeDict = attributeDict

    def write(self):
        if os.path.isfile(self.jsonPath):
            print(self.jsonPath)
            with open(self.jsonPath, "r") as file:
                input_data = file.read()
                outputDict = json.loads(input_data) if len(input_data) else {}
                outputDict.update(self.attributeDict)
                Path(self.jsonPath).write_text(json.dumps(outputDict), ENCODE_METHOD)
        else:
            with open(self.jsonPath, "w") as file:
                outputDict = {key: "" for key in ATTRIBUTE_KEYS}
                outputDict["image"] = self.imgFileNameWithoutExt
                Path(self.jsonPath).write_text(json.dumps(outputDict), ENCODE_METHOD)
                print("created one")


class AttributeJSONReader:
    def __init__(self, jsonPath):
        self.jsonPath = jsonPath
        self.attributeDict = {}
        self.verified = False
        self.jsonFilename = os.path.basename(jsonPath)
        self.filenameWithoutExt = os.path.splitext(self.jsonFilename)[0]
        try:
            self.parseJSON()
        except ValueError:
            print("JSON decoding failed")

    def parseJSON(self):
        with open(self.jsonPath, "r") as file:
            jsonFileData = file.read()
            loadedJSONDict = json.loads(jsonFileData) if len(jsonFileData) else {}
            # self.verified = True

        if loadedJSONDict.get("image", "") == self.filenameWithoutExt:
            self.attributeDict = loadedJSONDict
