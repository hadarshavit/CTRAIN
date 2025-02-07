import os
import argparse


def create_val_img_folder(data_dir):
    '''
    This method is responsible for separating validation images into separate sub folders
    From https://github.com/DennisHanyuanXu/Tiny-ImageNet/blob/master/src/data_prep.py
    '''
    val_dir = os.path.join(data_dir, 'val')
    img_dir = os.path.join(val_dir, 'images')

    fp = open(os.path.join(val_dir, 'val_annotations.txt'), 'r')
    data = fp.readlines()
    val_img_dict = {}
    for line in data:
        words = line.split('\t')
        val_img_dict[words[0]] = words[1]
    fp.close()

    # Create folder if not present and move images into proper folders
    for img, folder in val_img_dict.items():
        newpath = (os.path.join(img_dir, folder))
        if not os.path.exists(newpath):
            os.makedirs(newpath)
        if os.path.exists(os.path.join(img_dir, img)):
            os.rename(os.path.join(img_dir, img), os.path.join(newpath, img))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('data_dir', type=str)
    args = parser.parse_args()
    create_val_img_folder(args.data_dir)