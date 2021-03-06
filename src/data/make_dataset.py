import os
import sys

import cv2
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath('./')))

from src.features.build_features import *


def get_valid_cases(path, label):
  """
  Get the valid cases (image with mask) from the given path.
  """
  cases = {
      'patient': [],
      'image_path': [],
      'mask_path': [],
      'flair': [],
      'class': []
  }
  for case in os.listdir(path):
    if 'mask' in case:
      patient_id = case.split('_')[0]
      flair = int(case.split('FLAIR')[1].split('_')[0])
      possible_image_path = []
      if flair < 10:
        possible_image_path.append(f'{patient_id}_FLAIR0{flair}.bmp')
      possible_image_path.append(case.replace('_mask.png', '.bmp'))
      possible_image_path.append(case.replace('_mask.png', '.png'))
      for pp in possible_image_path:
        if pp in os.listdir(path):
          cases['class'].append(label)
          cases['patient'].append(patient_id)
          cases['flair'].append(flair)
          cases['mask_path'].append(os.path.join(path, case))
          cases['image_path'].append(os.path.join(path, pp))
          break
  return pd.DataFrame(cases)


def split_dataset(df, split_ratio):
  """
  Split the dataset into training and validation sets.
  """
  train_df = df.groupby('patient').sample(frac=split_ratio, random_state=42)
  val_df = df.drop(train_df.index)
  return train_df, val_df


def get_dataset(path, split_ratio):
  """
  Get the dataset from the given path.
  """
  datasets = []
  for dataset in os.listdir(path):
    df = get_valid_cases(os.path.join(path, dataset), dataset)
    train_df, val_df = split_dataset(df, split_ratio)
    datasets.append((train_df, val_df))
  train_df = pd.concat([train_df for train_df, _ in datasets])
  val_df = pd.concat([val_df for _, val_df in datasets])
  return train_df, val_df


def make_interim_dataset(path):
  """
  Make the dataset from the given path.
  """
  train_df, val_df = get_dataset(os.path.join(path, 'raw'), 0.8)
  train_df.to_csv(os.path.join(path, 'iterim', 'train.csv'), index=False)
  val_df.to_csv(os.path.join(path, 'iterim', 'val.csv'), index=False)

  x_train, Y_train, z_train = train_df['image_path'], train_df[
      'class'], train_df['mask_path']
  x_val, Y_val, z_val = val_df['image_path'], val_df['class'], val_df[
      'mask_path']
  X_train, X_val, Z_train, Z_val = [], [], [], []

  for im_path in x_train:
    X_train.append(np.array(cv2.imread(im_path, 0)))

  for im_path in z_train:
    im_mask = np.array(cv2.imread(im_path, cv2.IMREAD_UNCHANGED))
    _, im_mask = cv2.threshold(im_mask, 0, 1,
                               cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    Z_train.append(im_mask)

  assert (len(X_train) == len(Z_train) == len(Y_train))

  np.savez(os.path.join(path, 'iterim', 'train.npz'),
           X_train=X_train,
           Y_train=Y_train,
           Z_train=Z_train)

  for im_path in x_val:
    X_val.append(np.array(cv2.imread(im_path, 0)))

  for im_path in z_val:
    im_mask = np.array(cv2.imread(im_path, cv2.IMREAD_UNCHANGED))
    _, im_mask = cv2.threshold(im_mask, 0, 1,
                               cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    Z_val.append(im_mask)

  assert (len(X_val) == len(Z_val) == len(Y_val))

  np.savez(os.path.join(path, 'iterim', 'val.npz'),
           X_val=X_val,
           Y_val=Y_val,
           Z_val=Z_val)


def make_LBP_dataset(path, R):
  """
  Make the dataset from the given path.
  """
  train_npz = np.load(os.path.join(path, 'iterim', 'train.npz'),
                      allow_pickle=True)
  val_npz = np.load(os.path.join(path, 'iterim', 'val.npz'), allow_pickle=True)
  X_train, Y_train, Z_train = train_npz['X_train'], train_npz[
      'Y_train'], train_npz['Z_train']
  X_val, Y_val, Z_val = val_npz['X_val'], val_npz['Y_val'], val_npz['Z_val']

  X_train_lbp = []
  X_train_masked_lbp = []

  X_val_lbp = []
  X_val_masked_lbp = []

  for index, image in enumerate(X_train):
    lbp, hist = LBP_image(get_equalized_hist_image(image), R)
    lbp_masked = lbp * Z_train[index]
    h_lbp_masked, _ = np.histogram(lbp_masked.ravel(),
                                   bins=np.arange(0, (8 * R) + 3),
                                   weights=Z_train[index].ravel())
    h_lbp_masked = h_lbp_masked.astype(float)
    h_lbp_masked = h_lbp_masked / (h_lbp_masked.sum(dtype=float) + 1e-7)
    X_train_lbp.append(hist)
    X_train_masked_lbp.append(h_lbp_masked)

  np.savez(os.path.join(path, 'processed', f'train_lbp_R_{R}.npz'),
           X_train=X_train_lbp,
           Y_train=Y_train)

  np.savez(os.path.join(path, 'processed', f'train_masked_lbp_R_{R}.npz'),
           X_train=X_train_masked_lbp,
           Y_train=Y_train)

  for index, image in enumerate(X_val):
    lbp, hist = LBP_image(get_equalized_hist_image(image), R)
    lbp_masked = lbp * Z_val[index]
    h_lbp_masked, _ = np.histogram(lbp_masked.ravel(),
                                   bins=np.arange(0, (8 * R) + 3),
                                   weights=Z_val[index].ravel())
    h_lbp_masked = h_lbp_masked.astype(float)
    h_lbp_masked = h_lbp_masked / (h_lbp_masked.sum(dtype=float) + 1e-7)
    X_val_lbp.append(hist)
    X_val_masked_lbp.append(h_lbp_masked)

  np.savez(os.path.join(path, 'processed', f'val_lbp_R_{R}.npz'),
           X_val=X_val_lbp,
           Y_val=Y_val)

  np.savez(os.path.join(path, 'processed', f'val_masked_lbp_R_{R}.npz'),
           X_val=X_val_masked_lbp,
           Y_val=Y_val)


def make_dataset_test(path, R):
  df = get_valid_cases(os.path.join(path, 'test'), None)
  x_test, z_test = df['image_path'], df['mask_path']
  patient = df['patient']
  X_test, X_test_lbp, X_test_masked_lbp = [], [], []
  Z_test = []

  for im_path in x_test:
    X_test.append(np.array(cv2.imread(im_path, 0)))

  for im_path in z_test:
    im_mask = np.array(cv2.imread(im_path, cv2.IMREAD_UNCHANGED))
    _, im_mask = cv2.threshold(im_mask, 0, 1,
                               cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    Z_test.append(im_mask)

  np.savez(os.path.join(path, 'iterim', 'test.npz'),
           X_test=X_test,
           patient=patient,
           Z_test=Z_test)

  for index, image in enumerate(X_test):
    lbp, hist = LBP_image(get_equalized_hist_image(image), R)
    lbp_masked = lbp * Z_test[index]
    h_lbp_masked, _ = np.histogram(lbp_masked.ravel(),
                                   bins=np.arange(0, (8 * R) + 3),
                                   weights=Z_test[index].ravel())
    h_lbp_masked = h_lbp_masked.astype(float)
    h_lbp_masked = h_lbp_masked / (h_lbp_masked.sum(dtype=float) + 1e-7)
    X_test_lbp.append(hist)
    X_test_masked_lbp.append(h_lbp_masked)

  np.savez(os.path.join(path, 'processed', f'test_lbp_R_{R}.npz'),
           X_test=X_test_lbp,
           patient=patient,
           Z_test=Z_test)

  np.savez(os.path.join(path, 'processed', f'test_masked_lbp_R_{R}.npz'),
           X_test=X_test_masked_lbp,
           patient=patient,
           Z_test=Z_test)
