"""
Use notes: currently supports extract_single only, pending a fix for
argparse for extract_multi et al.

Invoke as:
python pyfx.py path-to-file.extension
"""

import os
import re
import gc
import gzip, shutil
import argparse

import numpy as np
import h5py

import skimage.io
import skimage.transform
from sklearn.feature_extraction.image import extract_patches_2d

from keras.applications import InceptionV3
from keras.applications.imagenet_utils import preprocess_input
from keras.preprocessing import image
from keras.models import Model
from keras.layers import Flatten


def collect_args():
    """
    Collects command line arguments from invocation.
    :return: argparse object containing parsed command line arguments
    """
    # Command line arguments: image in-path, feature out-path, ext for output
    parser = argparse.ArgumentParser(description="""Perform InceptionV3
     feature extraction on images.""")

    # TODO: nargs, document these - explain each type
    """
    # TODO: case-insensitivity changes
    parser.add_argument(nargs='?', type=str, dest='extractor',
                        default='multi', action='store')
    # TODO: -silent (no prompting) w/ default=prompt for args
    parser.add_argument(nargs=1, type=bool, dest='silent',
                        default=True, action='store')
    """
    parser.add_argument(nargs='?', type=str, dest='img_path',
                        default='./images', action='store')

    """
    # Need to figure out how to integrate this with regex.
    parser.add_argument(nargs='?', type=str, dest='img_type',
                        default='png', action='store')
    """

    """
    parser.add_argument(nargs='?', type=str, dest='out_path',
                        default='./output/features', action='store')
    parser.add_argument(nargs='?', type=str, dest='ext',
                        default='hdf5', action='store')
    """

    """
    TODO: figure out why this and other boolean args get set True
    when defaults are False and False is passed to them in xterm.
    """

    """
    parser.add_argument(nargs='?', type=bool, dest='compressed',
                        default=False, action='store')
    parser.add_argument(nargs='?', type=bool, dest='flatten',
                        default=False, action='store')
    """

    argv = parser.parse_args()

    """
    compressed = argv.compressed
    extension = argv.ext

    if extension != ("csv" or "txt"):
        # TODO: string formatting here is bad
        print("""WARNING: non-text compression is experimental.""")
    elif not compressed:
        print("""WARNING: non-compressed csv output is extremely large.
        Recommend re-running with compressed=True.""")
    """

    return argv


def extract_multi():
    """
    extract_multi

    Extracts feature data for each member in a directory containing .png images

    :return: Keras tensor containing extracted features.
    """

    # Load dataset (any image-based dataset)
    # TODO: argv for file types other than png
    matches = [(re.match(r'^(([a-zA-Z]+)\d+\.png)', fname), path)
               for path, dirs, files in os.walk('' + str(args.img_path))
               for fname in files]
    # Resize / regularize image 'patches'
    patches = [skimage.transform.resize(  # resize image to (256, 256)
        skimage.io.imread(os.path.join(path, match.group(1))),  # open each img
        (256, 256)) for match, path in matches if match]

    # Pre-process for InceptionV3
    patches = preprocess_input(np.array(patches))

    # Construct model (using ImageNet weights)
    inception = InceptionV3(weights="imagenet", include_top=False,
                            input_shape=patches[0].shape)

    # Isolate pre-softmax outputs
    x = inception.output

    # Flatten to 1d
    if args.flatten or args.ext == 'csv':
        x = Flatten()(x)
        # TODO: K.reshape(x) to 2d for csv

    # Construct extractor model
    extractor = Model(inputs=[inception.input], outputs=[x])

    # Extract features with Model.predict()
    features = extractor.predict(x=patches, batch_size=2)

    # TODO: get rid of zero-padding

    return features


def extract_single(filename):
    """
    extract_single

    Returns feature data for a single image or patch. Does not concatenate
    output to a 1d array, but instead outputs a full Keras tensor. The
    extraction is identical to extract_multi, but takes features from a
    single file rather than a directory of files.

    Those intending to use this method directly might consider libkeras's
    extract_features.py as an alternative.

    :return: Keras tensor containing extracted features.
    """

    # Load target image (as float32)
    target = skimage.io.imread(filename).astype('float32')

    # Split into patches
    patches = extract_patches_2d(target, (256, 256))

    # Pre-process for InceptionV3
    patches = preprocess_input(np.array(patches))

    # Construct model (using ImageNet weights)
    inception = InceptionV3(weights="imagenet", include_top=False,
                            input_shape=patches[0].shape)

    # Isolate pre-softmax outputs
    x = inception.output

    # Concat to 1d array
    x = Flatten()(x)

    # Construct extractor model
    extractor = Model(inputs=[inception.input], outputs=[x])

    # Extract features with Model.predict()
    features = extractor.predict(x=patches, batch_size=2)

    return features

def save_features():
    """
    Writes extracted feature vectors into a binary or text file, per args.
    :return: none
    """

    extractor = args.extractor
    features = []

    if extractor == 'multi':
        features = extract_multi()
    elif extractor == 'single':
        features = extract_single()

    # print("Output shape: ", features.shape)  # comment out if you don't care to know output shape

    extension = str(args.ext)
    compress = args.compressed
    out_path = str(args.out_path)

    # TODO: get rid of boilerplate code
    outfile = "" + out_path
    out_full = outfile + "." + extension
    if extension == "hdf5":
        # (Recommended, default) save to .hdf5
        f = h5py.File("" + out_path + ".hdf5", "w")
        f.create_dataset(name=str(args.out_path), data=features)
        if compress:
            with open(out_full) as f_in:
                outfile_gz = out_full + ".gz"
                with gzip.open(outfile_gz, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
    elif extension == "npy":  # god please don't actually do this
        # Save to .npy binary (numpy) - incompressible (as of now)
        np.save(file=outfile, allow_pickle=True, arr=features)
        if compress:

            with open(out_full) as f_in:
                outfile_gz = out_full + ".gz"

                with gzip.open(outfile_gz, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

    elif extension == "csv":

        # Save to .csv (or, .csv.gz if args.compressed==True)
        # This option is natively compressible.
        if compress:
            extension += ".gz"
        outfile = "" + out_path + "." + extension

        # TODO: This needs to return a string, no explicit save
        np.savetxt(fname=outfile, X=features, fmt='%1.5f')
        return features
    # TODO: (distant future) npz for the optional list of concat. 1d arrays


def main():
    """
    Execute feature extraction.
    :return: None. Should exit with code 0 on success.
    """
    # Uncomment if you would like to save results to disk:
    # save_features()
    gc.collect()
    exit(0)  # TODO: check - change exit code for failure

args = collect_args()

main()
