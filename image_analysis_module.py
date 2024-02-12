# Module containing the used functions from foreimg.py to be included in the flask api
import numpy as np
import numpy.matlib as npm
import argparse
import json
import pprint
import exifread
import cv2 as cv
import os
import progressbar
import warnings
from scipy import ndimage
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from matplotlib import pyplot as plt
from os.path import basename
import hashlib
from datetime import datetime
import binascii

current_root_path = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(current_root_path, 'assets', 'uploads')

# Classes for the analysis results

class StaticAnalysis:
    def __init__(self, applicable=False, result=None):
        self.applicable = applicable
        self.result = result
    
    def serialize(self):
        return {
            'applicable': self.applicable,
            'result': self.result
        }

class ExifMetadataExtraction:
    def __init__(self, applicable=False, result=None):
        self.applicable = applicable
        self.result = result

    def serialize(self):
        return {
            'applicable': self.applicable,
            'result': self.result
        }

class PreviewExtraction:
    def __init__(self, applicable=False, result=None):
        self.applicable = applicable
        self.result = result

    def serialize(self):
        return {
            'applicable': self.applicable,
            'result': self.result
        }


class Localization:
    def __init__(self, applicable=False, result=None):
        self.applicable = applicable
        self.result = result

    def serialize(self):
        return {
            'applicable': self.applicable,
            'result': self.result
        }

class ErrorLevelAnalysis:
    def __init__(self, applicable=False, result=None,):
        self.applicable = applicable
        self.result = result
    
    def serialize(self):
        return {
            'applicable': self.applicable,
            'result': self.result
        }


def analyze_image(file_stream):
  
    # static analysis
    static_applicable, result = get_image_info(file_stream)
    Static_object = StaticAnalysis(static_applicable, result)

    # EXIF
    EXIF_applicable, tags, exif_code_form = exif_check(file_stream)
    EXIF_object = ExifMetadataExtraction(applicable=EXIF_applicable, result=tags)

    # preview
    preview_applicable, result = extract_thumbnail(file_stream)
    Preview_object = PreviewExtraction(preview_applicable, result)

    # Localization # check EXIF applicable first
    localization_applicable, lat, lng = False, None, None
    if EXIF_applicable:
        localization_applicable, lat, lng = check_gps_location(exif_code_form)
    Localization_object = Localization(localization_applicable, {'lat': lat, 'lng': lng})

    # ELA
    ELA_image = ela(file_stream, 80, 15, flatten=False)
    ELA_file_path = os.path.join(UPLOAD_FOLDER, "temp_ELA.jpg")
    cv.imwrite(ELA_file_path, ELA_image)
    ELA_object = ErrorLevelAnalysis(True, {'ela_file_path':"temp_ELA.jpg"})
    
    return {
        'StaticObject': Static_object.serialize(),
        'ExifObject': EXIF_object.serialize(),
        'PreviewObject': Preview_object.serialize(),
        'LocalizationObject': Localization_object.serialize(),
        'ELAObject': ELA_object.serialize(),
    }

############################################
#### Functions for Error Level Analysis ####
############################################

def ela(file_path, quality=95, multiplier=15, flatten=False):
    # Initialize progress bar
    bar = progressbar.ProgressBar(maxval=20,
                                  widgets=[progressbar.Bar('=', '[', ']'), ' ', progressbar.Percentage()])
    bar.start()

    # Read the original image
    img = cv.imread(file_path)
    bar.update(2)

    # Get the name of the image without extension
    base = os.path.basename(file_path)
    file_name = os.path.splitext(base)[0]
    temp_file_name = file_name + "_temp.jpg"

    # Set the parameters for resaving the image
    encode_param = [int(cv.IMWRITE_JPEG_QUALITY), quality]
    
    # Resave the image with the specified quality
    cv.imwrite(temp_file_name, img, encode_param)
    bar.update(5)

    # Load the resaved image
    img_low = cv.imread(temp_file_name)
    bar.update(8)

    # Calculate the ELA map
    ela_map = np.abs(np.float32(img) - np.float32(img_low)) * multiplier
    bar.update(12)

    # Remove the temporary file
    os.remove(temp_file_name)

    # Flatten the ELA map if specified
    if flatten:
        ela_map = np.average(ela_map, axis=-1)
    bar.update(15)

    # Normalize the ELA map
    ELA_image = cv.normalize(ela_map, None, alpha=0, beta=255, norm_type=cv.NORM_MINMAX, dtype=cv.CV_8U)
    bar.update(18)

    # Finish the progress bar
    bar.finish()
    
    return ELA_image

###############################################
###  Functions for extracting EXIF Metadata ###
###############################################

def exif_check(file_path):
    # Open image file for reading (binary mode)
    f = open(file_path, 'rb')

    # Return Exif tags
    tags = exifread.process_file(f)

    # Get the pure EXIF data of Image
    exif_code_form = extract_pure_exif(file_path)
    if exif_code_form == None:
        print("The EXIF data has been stripped. Photo maybe is taken from facebook, twitter, imgur")
        return False, None, None

    # Check Modify Date
    check_software_modify(exif_code_form)
    check_modify_date(exif_code_form)
    check_original_date(exif_code_form)
    check_camera_information(tags)
    check_gps_location(exif_code_form)
    check_author_copyright(exif_code_form)

    tag_data = ''
    for tag in tags.keys():
        if tag not in ('JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote'):
            tag_data += f"{tag}: {tags[tag]}<br>"
    return True, {'tags': tag_data}, exif_code_form

def extract_pure_exif(file_name):
    img = Image.open(file_name)
    info = img._getexif()
    return info

def decode_exif_data(info):
    exif_data = {}
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            exif_data[decoded] = value
    return exif_data

def get_if_exist(data, key):
    if key in data:
        return data[key]
    return None

def export_json(data):
    with open('data.txt', 'w') as outfile:
        json.dump(data, outfile, ensure_ascii=False)


# List of function check edited image
        
# Check Software Edit
def check_software_modify(info):
    software = get_if_exist(info, 0x0131)
    if software != None:
        print("Image edited with: %s" % software)
        return True
    return False

# Check Modify Date
def check_modify_date(info):
    modify_date = get_if_exist(info, 0x0132)
    if modify_date != None:
        print("Photo has been modified since it was created. Modified: %s" % modify_date)
        return True
    return False

# Check Original date
def check_original_date(info):
    original_date = get_if_exist(info, 0x9003)
    create_date = get_if_exist(info, 0x9004)
    if original_date != None:
        print("The shutter actuation time: %s" % original_date)
    if create_date != None:
        print("Image created at: %s" % create_date)

# Check Camera Information
def check_camera_information_2(info):
    make = get_if_exist(info, 0x010f)
    model = get_if_exist(info, 0x0110)
    exposure = get_if_exist(info, 0x829a)
    aperture = get_if_exist(info, 0x829d)
    focal_length = get_if_exist(info, 0x920a)
    iso_speed = get_if_exist(info, 0x8827)
    flash = get_if_exist(info, 0x9209)

    print("\nCamera Infomation")
    print("Make: \t \t %s" % make)
    print("Model: \t \t %s" % model)
    print("ISO Speed: \t %s" % iso_speed)
    print("Flash: \t \t %s" % flash)


def check_camera_information(info):
    make = get_if_exist(info, 'Image Make')
    model = get_if_exist(info, 'Image Model')
    exposure = get_if_exist(info, 'EXIF ExposureTime')
    aperture = get_if_exist(info, 'EXIF ApertureValue')
    focal_length = get_if_exist(info, 'EXIF FocalLength')
    iso_speed = get_if_exist(info, 'EXIF ISOSpeedRatings')
    flash = get_if_exist(info, 'EXIF Flash')

    print("\nCamera Infomation")
    print("-------------------------------------------------------------- ")
    print("Make: \t \t %s" % make)
    print("Model: \t \t %s" % model)
    print("Exposure: \t %s " % exposure)
    print("Aperture: \t %s" % aperture)
    print("Focal Length: \t %s mm" % focal_length)
    print("ISO Speed: \t %s" % iso_speed)
    print("Flash: \t \t %s" % flash)

# Check GPS Location
def check_gps_location(info):
    gps_info = get_if_exist(info, 0x8825)

    if gps_info == None:
        print("GPS coordinates not found")
        return False, None, None
    # print gps_info
    lat = None
    lng = None
    gps_latitude = get_if_exist(gps_info, 0x0002)
    gps_latitude_ref = get_if_exist(gps_info, 0x0001)
    gps_longitude = get_if_exist(gps_info, 0x0004)
    gps_longitude_ref = get_if_exist(gps_info, 0x0003)
    if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
        lat = convert_to_degress(gps_latitude)
        if gps_latitude_ref != "N":
            lat = 0 - lat
        lng = convert_to_degress(gps_longitude)
        if gps_longitude_ref != "E":
            lng = 0 - lng

    print("Latitude \t %s North" % lat)
    print("Longtitude \t %s East" % lng)

    return True, lat, lng


def convert_to_degress(value):
    """Helper function to convert the GPS coordinates 
    stored in the EXIF to degress in float format"""
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)

def check_author_copyright(info):
    author = get_if_exist(info, 0x9c9d)
    copyright_tag = get_if_exist(info, 0x8298)
    profile_copyright = get_if_exist(info, 0xc6fe)
    print("\nAuthor and Copyright")
    print("-------------------------------------------------------------- ")
    print("Author \t \t %s " % author)
    print("Copyright \t %s " % copyright_tag)
    print("Profile: \t %s" % profile_copyright)



############################################
#### Functions thumbnail extraction ########
############################################
def extract_thumbnail(file_path, thumbnail_size=(100, 100)):
    try:
        # Open the image file
        img = Image.open(file_path)

        # Determine MIME type directly from the opened image
        mime_type = Image.MIME[img.format]

        # Get the thumbnail
        thumbnail = img.copy()
        thumbnail.thumbnail(thumbnail_size)

        # Define the thumbnail path
        thumbnail_path = os.path.join(UPLOAD_FOLDER, "temp_thumbnail.jpg")
        # Save the thumbnail to a file
        thumbnail.save(thumbnail_path)

        size = len(thumbnail.tobytes())
        dimensions = thumbnail.size  # Returns (width, height)

        # Close the image file
        img.close()

        return True, {
            "size": size,
            "mime_type": mime_type,
            "dimensions": dimensions,
            "thumbnail_path": "temp_thumbnail.jpg"
        }
    except Exception as e:
        print(f"Error extracting thumbnail: {e}")
        return False, None
    
def get_image_info(file_path):
    try:
        # Open the image file
        img = Image.open(file_path)

        # Get image dimensions
        dimensions = img.size  # Returns (width, height)

        # Get file analysis timestamp
        analyzed_at = datetime.now().strftime("%b. %d, %Y, %I:%M %p")

        # Get image type
        image_type = img.format.lower()

############################################
############### Functions HASH #############
############################################
        
        # Calculate hash values
        sha1 = hashlib.sha1(img.tobytes()).hexdigest()
        sha224 = hashlib.sha224(img.tobytes()).hexdigest()
        sha256 = hashlib.sha256(img.tobytes()).hexdigest()
        sha384 = hashlib.sha384(img.tobytes()).hexdigest()
        sha512 = hashlib.sha512(img.tobytes()).hexdigest()
        md5 = hashlib.md5(img.tobytes()).hexdigest()
        # Calculate CRC32
        crc32 = binascii.crc32(img.tobytes()) & 0xFFFFFFFF
        crc32_hex = f"{crc32:08X}"

        # Close the image file
        img.close()

        return True, {
            "Dimensions": dimensions,
            "AnalyzedAt": analyzed_at,
            "Type": image_type,
            "SHA1": sha1,
            "SHA224": sha224,
            "SHA256": sha256,
            "SHA384": sha384,
            "CRC32": crc32_hex,
            "SHA512": sha512,
            "MD5": md5
        }
    except Exception as e:
        print(f"Error getting image info: {e}")
        return False, None