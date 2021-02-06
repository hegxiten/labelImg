
#!/usr/bin/env python3.8
import os, sys
import datetime as dt
from typing import List, Dict, Tuple, TypedDict, Literal
import json
from PIL import Image
from PIL.ImageQt import ImageQt
from PyQt5 import QtGui, QtCore
from PyQt5.QtGui import QImage

PHOTO_DIR_ROOT = "D:/Users/wangz/OneDrive - Rutgers University/David_Corbitt_China"

class PhotoMetaData(TypedDict):
    filename: str
    year: int
    month: int
    day: int
    year_range: Tuple[int, int]
    month_range: Tuple[int, int]
    day_range: Tuple[int, int]
    train: TypedDict
    region: str     # northeast, northwest, southeast, southwest
    area: str       # name of the specific town/city/county
    geo_coordinates: Tuple[float, float]
    geo_range: int
    perspective_angle_rough: str
    perspective_angle: int
    people: List[str]
    comments: str
    tag: str

class TrainMetaData(TypedDict):
    locomotive_class: str
    locomotive_nbr: str
    locomotive_ownership: str
    train_nbr: str
    train_class: str    # freight, passenger, mixed, work
    comments: str


class LoopLoader():
    def __init__(self):
        pass

if __name__ == "__main__":
    sections = [i for i in os.listdir(PHOTO_DIR_ROOT) if "China" in i]
    cnt = 0
    for sec in sections:
        # --------- Parse the sectional directories ---------
        section_dir = os.path.join(PHOTO_DIR_ROOT, sec)
        contents = os.listdir(section_dir)
        sec_raw_photos = [i for i in contents if i[-4:] == ".jpg"]
        sec_raw_photo_dirs = [os.path.join(section_dir, i) for i in contents if i[-4:] == ".jpg"]
        sec_highlights_dir = os.path.join(section_dir, sec + " Highlights")
        sec_subfolders = [i for i in os.listdir(sec_highlights_dir)]
        cnt += len(sec_raw_photos)
        
        # --------- Include photos outside the root folder ---------
        # --------- Already removed repetitive photos ---------
        # for subf in sec_subfolders:
        #     sec_highlights_subfolder_dir = os.path.join(sec_highlights_dir, subf)
        #     for f in os.listdir(sec_highlights_subfolder_dir):
        #         if f not in sec_raw_photos:
        #             print(sec_highlights_subfolder_dir, f)
        #             sec_raw_photos.append(f)
        for i in range(len(sec_raw_photos)):
            try:
                with open(os.path.join(section_dir, sec_raw_photos[i] + ".json"), 'r') as f:
                    metadata = json.load(f)
                    print(metadata)
            except json.decoder.JSONDecodeError:
                with open(os.path.join(section_dir, sec_raw_photos[i] + ".json"), 'w') as f:
                    im=Image.open(os.path.join(section_dir, sec_raw_photos[i]))
                    image = ImageQt(im)
                    pixmap = QtGui.QPixmap.fromImage(image)
                    for key in PhotoMetaData.__annotations__:
                        print(key)
                    
