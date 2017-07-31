import datetime
import os, errno
from PIL.ExifTags import TAGS, GPSTAGS
from io import BytesIO
import piexif
import cv2
import numpy

def opencv_test():
    # open a hi-res file
    # read our test file
    ft = open('../photos/TEST4.JPG', 'rb')
    assert (ft is not None)

    binary_image = ft.read()
    ft.close()

    # we have a binary image, time to scale it.
    numpy_array = numpy.fromstring(binary_image, dtype='uint8')
    img = cv2.imdecode(numpy_array, flags=cv2.IMREAD_COLOR)
    exif_dict = piexif.load(binary_image)

    fn = '/mnt/image_files/opencv_test_hires.JPEG'
    status = cv2.imwrite(fn, img)
    assert(status)


    (height, width) = img.shape[:2]
    sx = 720/width
    sy = 720/height

    th_img = rotate_flip_scale(img, 0, False, sx)
    fn = '/mnt/image_files/openvcv_test_thumbnail-0.JPEG'
    status = cv2.imwrite(fn, th_img)
    assert(status)

    th_img = rotate_flip_scale(img, 90, False, sx)
    fn = '/mnt/image_files/openvcv_test_thumbnail-90.JPEG'
    status = cv2.imwrite(fn, th_img)
    assert(status)

    th_img = rotate_flip_scale(img, 180, False, sx)
    fn = '/mnt/image_files/openvcv_test_thumbnail-180.JPEG'
    status = cv2.imwrite(fn, th_img)

    th_img = rotate_flip_scale(img, 270, False, sx)
    fn = '/mnt/image_files/openvcv_test_thumbnail-270.JPEG'
    status = cv2.imwrite(fn, th_img)
    assert(status)

    th_img = rotate_flip_scale(img, 0, True, sx)
    fn = '/mnt/image_files/openvcv_test_thumbnail-0-flipped.JPEG'
    status = cv2.imwrite(fn, th_img)
    assert (status)

    th_img = rotate_flip_scale(img, 90, True, sx)
    fn = '/mnt/image_files/openvcv_test_thumbnail-90-flipped.JPEG'
    status = cv2.imwrite(fn, th_img)
    assert (status)

    th_img = rotate_flip_scale(img, 180, True, sx)
    fn = '/mnt/image_files/openvcv_test_thumbnail-180-flipped.JPEG'
    status = cv2.imwrite(fn, th_img)

    th_img = rotate_flip_scale(img, 270, True, sx)
    fn = '/mnt/image_files/openvcv_test_thumbnail-270-flipped.JPEG'
    status = cv2.imwrite(fn, th_img)
    assert (status)


def rotate_flip_scale(img, rotate_cw: int, flip: bool, scale: int):
    '''
    :param img: hi-res image
    :param rotate_cw: 0,90,180,270 degrees
    :param flip: True -> flip X-axis
    :param scale: scale factor to scale down by
    :return: scaled, rotated & flipped image

    Note: OpenCV flip routine takes the following flag:
       0 - flip X-axis
       1 - flip Y-axis
       -1 - flip both axis
    '''
    ret_img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    if rotate_cw == 0:
        if flip:
            return cv2.flip(ret_img, 0)
        else:
            return ret_img

    if rotate_cw == 90:
        cv2.transpose(ret_img, ret_img)
        if flip:
            ret_img = cv2.flip(ret_img, 1)
        else:
            ret_img = cv2.flip(ret_img, -1)
        return ret_img

    if rotate_cw == 270:
        cv2.transpose(ret_img, ret_img)
        if not flip:
            ret_img = cv2.flip(ret_img, 0)
        return ret_img

    if rotate_cw == 180:
        if flip:
            ret_img = cv2.flip(ret_img, 1)
        else:
            ret_img = cv2.flip(ret_img, -1)
        return ret_img

    return ret_img
