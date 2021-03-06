#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 14 11:57:34 2018

@author: ken38
"""

#%% Necessary Dependencies


#  PROCESSING NF GRAINS WITH MISORIENTATION
#==============================================================================
import numpy as np

import matplotlib.pyplot as plt

import multiprocessing as mp

import os

from hexrd.grainmap import nfutil
from hexrd.grainmap import tomoutil
from hexrd.grainmap import vtkutil

#==============================================================================
# %% FILES TO LOAD -CAN BE EDITED
#==============================================================================
#These files are attached, retiga.yml is a detector configuration file
#The near field detector was already calibrated

#A materials file, is a cPickle file which contains material information like lattice
#parameters necessary for the reconstruction

main_dir = '/nfs/chess/user/ken38/Ti7_project/ti7-11-1percent/'

det_file = main_dir + 'retiga.yml'
mat_file= main_dir + 'materials.cpl'

#==============================================================================
# %% OUTPUT INFO -CAN BE EDITED
#==============================================================================

output_dir = main_dir

#==============================================================================

# %% TOMOGRAPHY DATA FILES -CAN BE EDITED - ZERO LOAD SCAN
#==============================================================================

#Locations of tomography bright field images
tbf_data_folder='/nfs/chess/raw/2018-1/f2/miller-774-1/ti7-11/2/nf/'

tbf_img_start=31171 #for this rate, this is the 6th file in the folder
tbf_num_imgs=10

#Locations of tomography images
tomo_data_folder='/nfs/chess/raw/2018-1/f2/miller-774-1/ti7-11/3/nf/'

tomo_img_start=31187#for this rate, this is the 6th file in the folder
tomo_num_imgs=360

#==============================================================================
# %% NEAR FIELD DATA FILES -CAN BE EDITED - ZERO LOAD SCAN
#==============================================================================
#These are the near field data files used for the reconstruction, a grains.out file
#from the far field analaysis is used as orientation guess for the grid that will
grain_out_file = main_dir + 'ti7-05-scan-11/grains.out'

#%%
#Locations of near field images
#Locations of near field images
data_folder='/nfs/chess/raw/2018-1/f2/miller-774-1/ti7-11/7/nf/' #layer 1

#img_start=46501#for 0.25 degree/steps and 5 s exposure, end up with 5 junk frames up front, this is the 6th
img_start=31602#for 0.25 degree/steps and 5 s exposure, end up with 6 junk frames up front, this is the 7th
num_imgs=1440
img_nums=np.arange(img_start,img_start+num_imgs,1)

output_stem='initial_nf_uniform_diffvol_1'
#==============================================================================
# %% USER OPTIONS -CAN BE EDITED
#==============================================================================
x_ray_energy=61.332 #keV

#name of the material for the reconstruction
mat_name='ti7al'

#reconstruction with misorientation included, for many grains, this will quickly
#make the reconstruction size unmanagable
misorientation_bnd=0.0 #degrees
misorientation_spacing=0.25 #degrees

beam_stop_width=0.6#mm, assumed to be in the center of the detector

ome_range_deg=[(0.,359.75)] #degrees

max_tth=-1. #degrees, if a negative number is input, all peaks that will hit the detector are calculated

#image processing
num_for_dark=250#num images to use for median data
threshold=1.5
num_erosions=2 #num iterations of images erosion, don't mess with unless you know what you're doing
num_dilations=3 #num iterations of images erosion, don't mess with unless you know what you're doing
ome_dilation_iter=1 #num iterations of 3d image stack dilations, don't mess with unless you know what you're doing

chunk_size=500#chunksize for multiprocessing, don't mess with unless you know what you're doing

#thresholds for grains in reconstructions
comp_thresh=0.75 #only use orientations from grains with completnesses ABOVE this threshold
chi2_thresh=0.005 #only use orientations from grains BELOW this chi^2

#tomography options
layer_row=1024 # row of layer to use to find the cross sectional specimen shape
recon_thresh=0.00025#usually varies between 0.0001 and 0.0005
#Don't change these unless you know what you are doing, this will close small holes
#and remove noise
noise_obj_size=500
min_hole_size=500

cross_sectional_dim=1.35 #cross sectional to reconstruct (should be at least 20%-30% over sample width)
#voxel spacing for the near field reconstruction
voxel_spacing = 0.005#in mm
##vertical (y) reconstruction voxel bounds in mm
v_bnds=[-0.085,0.085]
#v_bnds=[-0.,0.]
#=======================
#==============================================================================
# %% LOAD GRAIN AND EXPERIMENT DATA
#==============================================================================

experiment, nf_to_ff_id_map  = nfutil.gen_trial_exp_data(grain_out_file,det_file,mat_file, x_ray_energy, mat_name, max_tth, comp_thresh, chi2_thresh, misorientation_bnd, \
                       misorientation_spacing,ome_range_deg, num_imgs, beam_stop_width)

#==============================================================================
# %% TOMO PROCESSING - GENERATE BRIGHT FIELD
#==============================================================================

tbf=tomoutil.gen_bright_field(tbf_data_folder,tbf_img_start,tbf_num_imgs,experiment.nrows,experiment.ncols,num_digits=6)

#==============================================================================
# %% TOMO PROCESSING - BUILD RADIOGRAPHS
#==============================================================================

rad_stack=tomoutil.gen_attenuation_rads(tomo_data_folder,tbf,tomo_img_start,tomo_num_imgs,experiment.nrows,experiment.ncols,num_digits=6)

#==============================================================================
# %% TOMO PROCESSING - INVERT SINOGRAM
#==============================================================================

reconstruction_fbp=tomoutil.tomo_reconstruct_layer(rad_stack,cross_sectional_dim,layer_row=layer_row,\
                                                   start_tomo_ang=ome_range_deg[0][0],end_tomo_ang=ome_range_deg[0][1],\
                                                   tomo_num_imgs=tomo_num_imgs, center=experiment.detector_params[3])

#==============================================================================
# %% TOMO PROCESSING - CLEAN TOMO RECONSTRUCTION
#==============================================================================

binary_recon=tomoutil.threshold_and_clean_tomo_layer(reconstruction_fbp,recon_thresh, noise_obj_size,min_hole_size)

#==============================================================================
# %%  TOMO PROCESSING - RESAMPLE TOMO RECONSTRUCTION
#==============================================================================

tomo_mask=tomoutil.crop_and_rebin_tomo_layer(binary_recon,recon_thresh,voxel_spacing,experiment.pixel_size[0],cross_sectional_dim)

#==============================================================================
# %%  TOMO PROCESSING - CONSTRUCT DATA GRID
#==============================================================================

test_crds, n_crds, Xs, Ys, Zs = nfutil.gen_nf_test_grid_tomo(tomo_mask.shape[1], tomo_mask.shape[0], v_bnds, voxel_spacing)

#==============================================================================
# %% NEAR FIELD - MAKE MEDIAN DARK
#==============================================================================

dark=nfutil.gen_nf_dark(data_folder,img_nums,num_for_dark,experiment.nrows,experiment.ncols,dark_type='median',num_digits=6)

#==============================================================================
# %% NEAR FIELD - LOAD IMAGE DATA AND PROCESS
#==============================================================================

image_stack=gen_nf_image_stack(data_folder,img_nums,dark,ome_dilation_iter,threshold,experiment.nrows,experiment.ncols,num_digits=6)#,grey_bnds=(5,5), gaussian=4.5)

#==============================================================================
# %% INSTANTIATE CONTROLLER - RUN BLOCK NO EDITING
#==============================================================================

progress_handler = nfutil.progressbar_progress_observer()
save_handler=nfutil.forgetful_result_handler()

controller = nfutil.ProcessController(save_handler, progress_handler,
                               ncpus=mp.cpu_count(), chunk_size=chunk_size)

multiprocessing_start_method = 'fork' if hasattr(os, 'fork') else 'spawn'

#==============================================================================
# %% TEST ORIENTATIONS - RUN BLOCK NO EDITING
#==============================================================================

raw_confidence=nfutil.test_orientations(image_stack, experiment, test_crds,
                  controller,multiprocessing_start_method)

#==============================================================================
# %% POST PROCESS W WHEN TOMOGRAPHY HAS BEEN USED
#==============================================================================

grain_map, confidence_map = nfutil.process_raw_confidence(raw_confidence,Xs.shape,tomo_mask=tomo_mask,id_remap=nf_to_ff_id_map)

#==============================================================================
# %% SAVE PROCESSED GRAIN MAP DATA
#==============================================================================

nfutil.save_nf_data(output_dir,output_stem,grain_map,confidence_map,Xs,Ys,Zs,experiment.exp_maps,id_remap=nf_to_ff_id_map)
