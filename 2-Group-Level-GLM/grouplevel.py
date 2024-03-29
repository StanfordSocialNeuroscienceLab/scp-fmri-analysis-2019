#!/bin/python3

"""
GroupLevel class facilitates group-level analyses with first-level brain data
Uncorrected and corrected brain maps are available to run with a single function call

Ian Richard Ferguson | Stanford University
"""

# ----- Imports
import warnings, os, json, pathlib
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import math
from tqdm import tqdm
from nilearn.glm import second_level, threshold_stats_img
import nilearn.plotting as nip
import matplotlib.pyplot as plt
from nilearn import image
from bids.layout import BIDSLayout

# ----- BIDS Directory Specifications
root = './bids'

try:
      layout = BIDSLayout(root)
      all_subjects = layout.get_subjects()
      all_tasks = layout.get_tasks()            
except:
      raise OSError("Check your BIDS root definition")


class GroupLevel:

      def __init__(self, task, complete_BIDS=False, user='ian'):
            """
            task => Corresponds to valid task in BIDS dataset
            complete_BIDS => Boolean, True if all raw data is available (on HPC)

            The following operations are performed:
                  * Output directories are created if they don't exist
                  * A list of all NifTi maps are assigned to object
            """

            self.task = task                                            # Valid BIDS task
            self._output_directory()                                    # Create relevant output dirs

            if complete_BIDS:
                  self.subjects = self._iso_BIDS_subjects(user)
            else:
                  self.subjects = self._iso_subjects(user)

            self.all_brain_data = self._brain_data(user)                # List of ALL NifTi's
            self.available_contrasts = self._available_contrasts()      # List of contrasts available for analysis
            self.task_file = self._taskfile_validator()                 # Confirms presence of JSON info files
            
            self.group_regressors = self.task_file['group-level-regressors']

            # Paths to model and brain map output directories
            self.plotting_output = os.path.join(root, f"derivatives/second-level/task-{self.task}/plotting")
            self.nifti_output = os.path.join(root, f"derivatives/second-level/task-{self.task}/second-level-model")


      def _taskfile_validator(self):
            """
            Confirms the existence of the following files at the same directory level:
                  * subject_information.json
                  * task_information.json
            """

            target_files = ['./subject_information.json',
                            './task_information.json']

            for target in target_files:
                  if not os.path.exists(target):
                        raise OSError(f"{target} not found in current directory")

            with open('./task_information.json') as incoming:
                  info = json.load(incoming)                            # Read JSON as dictionary
                  reduced = info[self.task]                             # Reduce to task-specific information

            return reduced


      def _output_directory(self):
            """
            Creates second-level subdirectories in derivatives if they don't exist
            """

            target = os.path.join(root, f"derivatives/second-level/task-{self.task}")

            if not os.path.exists(target):
                  pathlib.Path(target).mkdir(exist_ok=True, parents=True)

            # Create subdirs for corrected and uncorrected models
            for subdir in ['second-level-model', 'plotting']:
                  for cor in ['corrected', 'uncorrected']:
                        temp = os.path.join(target, subdir, cor)

                        if not os.path.exists(temp):
                              pathlib.Path(temp).mkdir(exist_ok=True, parents=True)


      def _iso_BIDS_subjects(self, user):
            """
            Deployment function - Only works with complete BIDS dataset
            Returns a list of subjects with first-level maps
            """

            # Empty list to append into
            task_subjects = []                                          
            
            # Relative path to first-level maps
            deriv_level = os.path.join(root, f"derivatives/first-level-{user}") 

            # Leverages BIDSLayout to isolate subject ID numbers
            for sub in all_subjects:
                  temp = os.path.join(deriv_level, f"sub-{sub}", f"task-{self.task}")
                  if os.path.isdir(temp):
                        task_subjects.append(f"sub-{sub}")

            return task_subjects


      def _iso_subjects(self, user):
            """
            Development function - Works with isolated derivatives
            Returns a list of subjects with first-level maps
            """

            # Empty list to append into
            task_subjects = []                                          
            
            # Relative path to first-level maps
            deriv_level = os.path.join(root, f"derivatives/first-level-{user}") 
            
            # Complete list of subjects
            subject_level = [x for x in os.listdir(deriv_level) if "sub-" in x]

            for sub in subject_level:
                  # Arbitrarily uses condition-maps subdir to confirm presence of first-level models
                  temp = os.path.join(deriv_level, sub, f"task-{self.task}/first-level-model/condition-maps")

                  if os.path.isdir(temp):
                        if len(os.listdir(temp)) > 0:
                              task_subjects.append(sub)                 # If brain maps are present, add sub to list

            return task_subjects


      def _brain_data(self, user):
            """
            Returns a dictionary of subject:run key-value pairs
            """

            # Dictionary with empty lists for each subject
            data = {k:[] for k in self.subjects}                        

            # Relative path to first-level subdirectory
            base = os.path.join(root, f"derivatives/first-level-{user}")      

            for sub in self.subjects:
                  # Define relative paths to first-level-models per subject
                  sub_directory = os.path.join(base, sub, f"task-{self.task}", "first-level-model")
                  conditions = os.path.join(sub_directory, "condition-maps")
                  contrasts = os.path.join(sub_directory, "contrast-maps")

                  output = []

                  for dir in [conditions, contrasts]:
                        temp = [os.path.join(dir, x) for x in os.listdir(dir)]
                        output += temp

                  if os.path.exists(os.path.join(base, sub, f"task-{self.task}/alt")):
                        alt_dir = os.path.join(base, sub, f"task-{self.task}", "alt/first-level-model")
                        alt_conditions = os.path.join(alt_dir, "condition-maps")
                        alt_contrasts = os.path.join(alt_dir, "contrast-maps")

                        for dir in [alt_conditions, alt_contrasts]:
                              temp = [os.path.join(dir, x) for x in os.listdir(dir)]
                              output += temp

                  data[sub] = output

            return data


      def _available_contrasts(self):
            """
            Returns dictionary of conditions and contrasts derived from first-level output
            """

            output = {'conditions': [], 'contrasts':[]}

            all_data = self.all_brain_data
            iso_id = list(all_data.keys())[0] 
            all_data = [x.split('/')[-1][10:].split('.nii.gz')[0] for x in all_data[iso_id]]

            output['conditions'] = [x.split('condition-')[1] for x in all_data if 'condition' in x]
            output['contrasts'] = [x.split('contrast-')[1] for x in all_data if 'contrast' in x]

            return output      


      # ------- Utility Functions


      def get_brain_data(self, contrast, smoothing="8mm"):
            """
            contrast => Used to isolate relevant NifTi files for group-level analysis
            smoothing => String to match first-level smoothing kernel

            Returns a list of absolute paths to relevant NifTi files
            """

            # Empty list to append into
            output = []

            if smoothing not in ["4mm", "8mm"]:
                  raise ValueError("Smoothing kernel should be 4mm or 8mm")

            try:
                  for sub in self.subjects:                             # Checks list of NifTi's for each subject
                        for scan in self.all_brain_data[sub]:
                              if contrast in scan:
                                    if smoothing in scan:
                                          output.append(scan)           # Add NifTi to list if contrast matches

            except:
                  raise ValueError(
                        f"Your specfied contrast {contrast} not found in functional runs")

            if len(output) == 0:
                  raise ValueError(
                        f"Your specified contrast {contrast} not found in functional runs")

            return output


      def brain_mosaic(self, contrast, smoothing=8., save_local=False):
            """
            
            """

            brains = self.get_brain_data(contrast=contrast, 
                                         smoothing=f"{int(smoothing)}mm")

            rows = int(math.ceil(len(brains) / 5))

            figure, axes = plt.subplots(nrows=rows, ncols=5, figsize=(20,20))

            for x in range(rows):
                  for y in range(5):
                        axes[x,y].axis('off')

            figure.suptitle(f"{contrast}_{int(smoothing)}mm", fontweight='bold')

            for index, brain in enumerate(brains):

                  sub_id = brain.split('/')[-1].split('_')[0].split('-')[1]

                  k = nip.plot_glass_brain(brain, threshold=3.2, display_mode='z',
                                           plot_abs=False, colorbar=False, title=sub_id,
                                           axes=axes[int(index / 5), int(index % 5)])

            if save_local:
                  filename = os.path.join(self.plotting_output, f"{contrast}_{int(smoothing)}mm.jpg")
                  plt.savefig(filename)

            plt.show()


      def subject_contrast_maps(self, contrasts=[], smoothing=8.):
            """
            
            """

            if len(contrasts) == 0:
                  raise ValueError("No contrasts supplied")

            for sub in self.subjects:
                  brain_data = [x for x in self.all_brain_data[sub] if f"{int(smoothing)}mm" in x]
                  keepers = []

                  for brain in brain_data:
                        for contrast in contrasts:
                              if contrast in brain:
                                    keepers.append(brain)

                  figure, axes = plt.subplots(nrows=1, ncols=len(contrasts), figsize=(15,4))

                  for index, brain in enumerate(keepers):
                        title = brain.split('/')[-1].split('-')[2].split('_smoothing')[0]

                        k = nip.plot_glass_brain(brain, threshold=3.2, display_mode='z', 
                                                 colorbar=False, plot_abs=False, title=title,
                                                 axes=axes[index])

                  figure.suptitle(sub, fontweight='bold')
                  plt.show()

                  print('\n\n')


      # ------- Modeling


      def build_design_matrix(self):
            """
            Creates a design matrix with subject-wise regressors

            Work to do
                  * Should accomodate subject demographics
                  * Should accomodate indegree/outdegree/other network regressors

            Returns design matrix as Pandas DF
            """
            from nilearn.glm.second_level import make_second_level_design_matrix

            # Read in subject data from Networks survey
            with open('./subject_information.json') as incoming:
                  scp_subjects = json.load(incoming)

            # Task specific information
            networks = self.task_file

            def change_key(key):
                  iso = str(key)[1:]
                  return f"sub-{iso}"

            # Changes key formatting from sXXXXX to sub-XXXXX
            subject_data = {change_key(k):v for k,v in scp_subjects.items()}

            # Helper function to kick out value for a specific variable / subject
            def network_value(x, var):
                  try:
                        return subject_data[x][var]
                  except:
                        return 'NA'

            subjects_label = self.subjects
            design_matrix = pd.DataFrame({'subject_label': subjects_label})

            for var in networks['group-level-regressors']:
                  # Bring in network variables
                  design_matrix[var] = design_matrix['subject_label'].apply(lambda x: network_value(x, var=var))
                  design_matrix[var] = pd.to_numeric(design_matrix[var])

            return make_second_level_design_matrix(subjects_label, design_matrix)


      def _basic_model(self, contrast, smoothing=8., direction=1, smooth_group=False):
            """
            contrast => String pattern matching first-level model
            smoothing => Float pattern matching first-level model
            direction => 1 or -1, determines which contrast will be considered positive
            smooth_group => Boolean, defaults to False. If True, group-level model is smoothed

            Mostly a developmental function...
            Runs a simple, intercept-only model on the specified contrast
            """

            if direction not in [-1, 1]:
                raise ValueError(
                    f"Invalid input {direction} ... must be 1 or -1")

            # E.g., 8. => "8mm"
            format_smoothing = f"{int(smoothing)}mm"

            # Apply no smoothing kernel to group-level model
            if not smooth_group:
                smoothing = None

            # List of absolute paths to NifTi files for the specified contrast
            brain_data = self.get_brain_data(
                contrast=contrast, smoothing=format_smoothing)

            # Intercept-only design matrix
            dm = pd.DataFrame([direction] * len(brain_data))

            # Instantiate + Fit second level mode
            model = second_level.SecondLevelModel(
                smoothing_fwhm=smoothing).fit(brain_data, design_matrix=dm)

            # Compute contrast on intercept column
            return model.compute_contrast(output_type="z_score")


      def uncorrected_group_model(self, contrast, columns=[], smoothing=4., smooth_group=False):
            """
            contrast => baseline condition or contrast from first-level-model
            columns => regressors of interest to include in design matrix (defaults to ALL)
            smoothing => kernel to smooth brain regions during model fitting
            smooth_group => Boolean, determines if smoothing kernel is applied to group model

            Returns intercept contrast from model
            """

            format_smoothing = f"{int(smoothing)}mm"

            brain_data = self.get_brain_data(contrast=contrast,         # List of relevant NifTi maps
                                             smoothing=format_smoothing) 

            design_matrix = self.build_design_matrix()                  # Define design matrix with helper function

            if len(columns) > 0:
                  if "intercept" not in columns:
                        columns = columns + ['intercept']

                  design_matrix = design_matrix.loc[:, columns]         # Reduce design matrix if desired

            if smooth_group:
                  model_smoothing = smoothing
            else:
                  model_smoothing = None

            # Instantiate and fit a second-level model
            model = second_level.SecondLevelModel(smoothing_fwhm=model_smoothing).fit(brain_data, design_matrix=design_matrix)

            return model.compute_contrast('intercept')


      def contrast_QA(self, contrast, verbose=False, smoothing=8.):
            """
            contrast => Valid first-level contrast

            Returns DataFrame object specifying quantity of contrasts and NifTi shapes for each contrast
            """

            format_smoothing = f"{int(smoothing)}mm"

            # List of relative paths to contrast maps
            data = self.get_brain_data(contrast=contrast, smoothing=format_smoothing)               

            # Emtpy dictionary to append into
            output = {'sub_id':[],                                      
                      'path_to_nifti':[],
                      'shape':[]}

            # For all valid contrasts, add to dictionary object
            for file in tqdm(data):                           
                  output['sub_id'].append(file.split('/')[-1].split('_')[0])
                  output['path_to_nifti'].append(file)
                  output['shape'].append(image.load_img(file).shape)

            # Print message for end user + return Pandas DataFrame object
            print(f"\nYou have {len(output['sub_id'])} valid contrasts eligible for second-level modeling...\n")

            if verbose:
                  return pd.DataFrame(output).sort_values(by="sub_id").reset_index(drop=True)


      # ------- Multiple Comparisons and Analysis Tools


      def one_sample_test(self, nifti, contrast, height_control="fpr", plot_style='ortho', alpha=0.001, cluster_threshold=0, return_map=False):
            """
            nifti => z_map contrast computed from a SecondLevelModel object
            contrast => String used for title on plot
            height_control => False positive rate (FPR / FDR / Bonferroni)
            plot_style => glass or stat
            alpha => Significance level
            cluster_threshold => Groups of connected voxels
            return_map => Kicks out significant voxels if you want to assign to a variable
            """

            if plot_style not in ['ortho', 'glass', 'mosaic']:
                  raise ValueError(f"{plot_style} not in [ ortho, glass, mosaic ]")

            # Threshold map at the specified significance level
            temp_map, temp_thresh = threshold_stats_img(nifti, alpha=alpha, 
                                                        height_control=height_control,
                                                        cluster_threshold=cluster_threshold)

            # Plot output
            title = f"{contrast} @ {alpha}"

            if plot_style == 'glass':
                  nip.plot_glass_brain(temp_map, threshold=temp_thresh, display_mode='lyrz',
                                    plot_abs=False, colorbar=False, title=title)

            elif plot_style == 'mosaic':
                  nip.plot_stat_map(temp_map, threshold=temp_thresh, title=title,
                                    display_mode='mosaic')

            elif plot_style == 'ortho':
                  nip.plot_stat_map(temp_map, threshold=temp_thresh, display_mode='ortho',
                                    draw_cross=False, title=title)

            else:
                  raise ValueError(f"Check your plot_style parameter, {plot_style} not in ['glass', 'stat']")

            if return_map:
                  return temp_map


      def load_PINES_signature(self):
            """
            Helper function to instantiate NifTi object with negative emotion signature
            This should be saved under derivatives/masks/ ... can be found on Tor Wager's GitHub page if need be

            Returns NifTi image of PINES signature for multivariate analysis and masking
            """

            path = os.path.join(root, "derivatives/masks/Rating_Weights_LOSO_2.nii")
            
            try:
                  return image.load_img(path)
            except:
                  raise OSError("No PINES map detected! Make sure it's located under ./$bids_root/derivatives/masks/")


      def resample_to_MNI152(self, target_img):
            """
            target_img => NifTi image that we want to resample

            Helper function to convert target image dimensionality to MNI152 template
            """

            from nilearn.datasets import load_mni152_template  
            template = load_mni152_template()                           

            return image.resample_to_img(target_img, template)


      def estimate_PINES_signature(self, contrast, smoothing=8., group_level=True, sub_id=None):
            """
            contrast => Contrast of interest that we want to compare to PINES signature
            smoothing => Specifies which z-map to grab (we have 4mm and 8mm smoothing kernels)
            group_level => Boolean, determines if you will run PINES estimation on whole sample or single sub
            sub_id => Applicable when not `group_level`

            Vectorizes brain data from a given task and calculates dot product with PINES signature vector
            """

            if group_level:
                  """
                  This method calculates PINES expression on a list of subjects NifTi images
                  """

                  # E.g., 8. => "8mm"
                  format_smoothing = f"{int(smoothing)}mm"

                  # List of relative paths to NifTi files
                  brain_data = self.get_brain_data(contrast=contrast, smoothing=format_smoothing) 

                  # Empty list to append into, will convert to array
                  sub_data = []                                           

                  print("Vectorizing brain maps...\n")

                  for sub in tqdm(brain_data):
                        # Convert Path to NifTi image
                        test_img = image.load_img(sub)               

                        # Resample to MNI152 and vectorize voxels into array
                        test_resample = test_img.get_fdata().flatten()
                        
                        # Add voxels to master array
                        sub_data.append(test_resample)

                  # Convert list to Numpy array
                  brain_vector = np.array(sub_data)                           

                  # Read in PINES map, resample, and vectorize
                  pines = self.load_PINES_signature()
                  pines_flat = pines.get_fdata().flatten()

                  # Return array of dot products - represents negative emotion expression in 
                  return np.dot(brain_vector, pines_flat)

            else:
                  """
                  This method calculates PINES expression on a single subject's NifTi image
                  """

                  # Ensure end user has set value for sub_id parameter
                  if sub_id == None:
                        raise ValueError(f"Subject ID must be set prior to running this function: currently {sub_id}")

                  # List of relative paths to NifTi files (should just be one per subject)
                  brain_data = [x for x in self.get_brain_data(contrast=contrast) if sub_id in x]

                  # Catch any duplicates and alert end user
                  if len(brain_data) > 1:
                        print([x.split('/')[-1] for x in brain_data])
                        raise ValueError("Ack! We should only see one map per subject")

                  # Convert to NifTi image
                  test_img = image.load_img(brain_data[0])

                  # Resample to template and vectorize              
                  test_resample = self.resample_to_MNI152(test_img).get_fdata().flatten()
                  
                  # Vectorize neural data to NP array
                  brain_vector = np.array(test_resample)

                  # Read in PINES map, resample, and vectorize                      
                  pines = self.load_PINES_signature()                         
                  pines_flat = self.resample_to_MNI152(pines).get_fdata().flatten()

                  # Return array of dot products
                  return np.dot(brain_vector, pines_flat)
