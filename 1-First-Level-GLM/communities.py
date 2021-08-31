#!/bin/python3

"""
SCP_Sub is a wrapper for first-level analysis in our project
This class allows us to run an analysis with a single function call

Ian Richard Ferguson | Stanford University
"""

import warnings
warnings.filterwarnings('ignore')

import matplotlib.pyplot as plt
import pandas as pd
import os
import json
import pathlib
from tqdm import tqdm

from nicursor import Subject
from nipype.interfaces.base import Bunch


class SCP_Sub(Subject):
      
      def __init__(self, subID, task):
            Subject.__init__(self, subID, task)
            self._nipype_output_directories()
            self.contrasts = self._taskfile_validator()[0]
            self.confound_regressors = self._taskfile_validator()[1]
            self.network_regressors = self._taskfile_validator()[2]
            self.trial_type = self._taskfile_validator()[3]

            self.conditions = self.contrasts[0][2]

            # ---- Output
            self.nipype_level_one = self._nipype_output_directories()[1]
            self.nipype_feat_model = self._nipype_output_directories()[0]

            self.nilearn_first_level_condition = self._nipype_output_directories()[2]
            self.nilearn_first_level_contrasts = self._nipype_output_directories()[3]
            self.nilearn_plotting_condition = self._nipype_output_directories()[4]
            self.nilearn_plotting_contrasts = self._nipype_output_directories()[5]


      # -------- FIRST-LEVEL GLM

      def _taskfile_validator(self):
            """
            Confirms the existence of the following:
                  * scp_subject_information.json
                  * scp_task_information.json

            If it exists, sets the following:
                  * Contrasts
                  * Confound regressors
                  * Network regressors
                  * Condition variable
            """

            import json
            target_files = ['./scp_subject_information.json',
                            './scp_task_information.json']

            for target in target_files:
                  if not os.path.exists(target):
                        raise OSError(f"{target} not found in current directory")

            with open('./scp_task_information.json') as incoming:
                  info = json.load(incoming)                            # Read JSON as dictionary
                  reduced = info[self.task]                             # Reduce to task-specific information

                  return [reduced['contrasts'], reduced['confound_regressors'],
                          reduced['network_regressors'], reduced['trial_type']]


      def _nipype_output_directories(self):
            """
            Runs @ __init__

            Dedicated output directories for Nipype and Nilearn output
            This creates new dirs AND returns list of relative paths
            """

            base_dir = self.first_level_output                          # Base dir in derivatives directory
            subdirs = [
                  # For output from FSL model design
                  'nipype/FEATModel', 'nipype/Level1Design',

                  # For Z-Maps        
                  'nilearn/FirstLevelModel/condition',
                  'nilearn/FirstLevelModel/contrasts', 

                  # For brain maps 
                  'nilearn/plotting/condition',
                  'nilearn/plotting/contrasts']

            keepers = []                                                # Container to return

            for subdir in subdirs:
                  k = os.path.join(base_dir, subdir)                    # Relative path to new dir
                  keepers.append(k)                                     # Add to container
                  pathlib.Path(k).mkdir(parents=True, exist_ok=True)    # Make directory if it doesn't exist

            return keepers

      # NOTE: The two functions below are primarily for development
      # Don't run self._detonate() after your analysis or you'll have to re-run!

      def _detonate(self):
            import shutil
            shutil.rmtree(self.first_level_output)


      def _regen(self):
            self._detonate()
            self._output_1L()
            self._nipype_output_directories()


      def set_contrasts(self, CONTRASTS):
            """
            CONSTRASTS => List of lists

            E..g, ['dorm_member', 'T', ['dorm_member'], [1]]
            """

            self.contrasts = CONTRASTS


      def derive_dummy_scans(self):
            """
            Returns list of binary 1,0 to denote number of dummy scans
            """

            events = self.load_events()                                 # Load event onset TSVs
            dummies = self.dummy_scans                                  # Hard-coded to 2

            if 'run' not in events.columns:                             # Single-run event onsets
                  size = len(events) - dummies                          # Number of non dummy scans
                  scans = ([1] * dummies) + ([0] * size)                # List of binary values

                  return scans

            else:                                                       # Multi-run event onsets
                  container = []                                        # To hold list of lists / run

                  for run in events['run'].unique():

                       # Isolate run + create dummy regressors per run
                        temp = events[events['run'] == run].reset_index(drop=True)
                        size = len(temp) - dummies
                        container.append(([1]*dummies) + ([0] * size))

                  # Concatenate lists into one
                  scans = []
                  for comp in container:
                        scans = scans + comp

                  return scans


      def session_info(self, confound_regressors, network_regressors, target_var, include_dummies=True):
            """
            confound_regressors => List of regressors to pull from fmriprep derivatives
            network_regressors => List of regressors to pull in from Networks data
            target_var => Column denoting social network stimuli presented in scanner
            include_dummies => Default True, determines if binary dummy regressors are included in output


            # NOTE - Before you call this function
                  * Define regressors (these are parameters)
                  * Assign contrasts outside of this function

            This helper needs to kick out a NiPype Bunch object
            Will be ported into first-level model
            """

            # -------- SETUP + SANITY CHECKS
            
            events = self.load_events()
            long_events = self.longform_events(target_column=target_var) 
            confounds = self.load_confounds()   
            trial_type = self.trial_type                        
            
            try:
                  dummy_scans = self.derive_dummy_scans()               # Our events files account for these so we skip
            except:
                  dummy_scans = []                                      # See above

            if len(self.contrasts) > 0:
                 contrasts = self.contrasts                             # Contrasts are outlined in external JSON file
            else:
                 raise ValueError('Contrasts have not been assigned')

            # Sanity check for confound regressors
            for var in confound_regressors:
                 if var not in confounds.columns:
                       raise ValueError(f'{var} not found in confound table')

            conditions = self.conditions                                # Added late, this attribute is now built in

            # -------- CONFOUND REGRESSORS

            regressors_CONFOUND = []

            if include_dummies:
                  regressors_CONFOUND_NAMES = ['dummy_scans'] + confound_regressors
                  regressors_CONFOUND.append(list(dummy_scans))
                  start = 1
            else:
                  regressors_CONFOUND_NAMES = confound_regressors
                  start = 0

            for var in regressors_CONFOUND_NAMES[start:]:
                  # Create a list of lists of confound values / variable
                  regressors_CONFOUND.append(list(confounds[var].fillna(0.)))

            # -------- NETWORK REGRESSORS

            regressors_NETWORK_NAMES = network_regressors
            regressors_NETWORK = []

            for var in regressors_NETWORK_NAMES:
                  # Create a list of lists of network values derived from communities project
                  regressors_NETWORK.append(list(long_events[var]))

            regressor_names = regressors_CONFOUND_NAMES + regressors_NETWORK_NAMES
            regressors = regressors_CONFOUND + regressors_NETWORK

            if len(regressor_names) != len(regressors):
                raise ValueError(
                      'Length mismatch between regressor names and regressor values')

            # -------- ONSETS AND DURATIONS

            onsets, durations = [], []

            # Push values to lists
            for var in conditions:
                  onsets.append(
                        list(events[events[trial_type] == var]['onset']))
                  durations.append(
                        list(events[events[trial_type] == var]['duration']))

            # Store information in Bunch object and return
            info = [Bunch(conditions=conditions,
                          onsets=onsets,
                          durations=durations,
                          regressors=regressors,
                          regressor_names=regressor_names,
                          contrasts=contrasts)]

            # -------- STORE REGRESSOR NAMES
            # We'll use these values later once we create a design matrix

            path = os.path.join(self.nipype_feat_model, "regressor_names.txt")

            with open(path, 'w') as outgoing:
                  for condition in conditions:
                        outgoing.write(condition)
                        outgoing.write('\n')

                  for regressor in regressor_names:
                        outgoing.write(regressor)
                        outgoing.write('\n')

            return info


      def longform_events(self, target_column):
            """
            target_column => Denotes in-scanner network stimulus (e.g., 'target')

            This creates a new events file with values for every TR (rather than every event)

            Perform the following operations:
                  * Match a DataFrame to the length of confound regressors
                  * Reduce events down to key columns and merge with full range of TRs
                  * Merge network regressors from external JSON file
                  * Binarize based on conditon

            Returns Pandas DataFrame object
            """

            base_events = self.load_events()                            # Events-wise TSV file
            tr_total = len(self.load_confounds())                       # Total # of TRs per task

            empty_events = {'onset':list(range(0, tr_total))}           # Single-column DataFrame
            empty_events = pd.DataFrame(empty_events)

            voi = ['onset', 'duration'] + [self.trial_type] + [target_column]
            base_events = base_events.loc[:, voi]                       # Reduce DataFrame to variables of interest

            events = empty_events.merge(base_events, on='onset', how='left')

            for idx, val in enumerate(events['duration']):
                  # Duration == 1, we have single row of values
                  if float(val) == 1.:
                        continue
                        
                  # Duration > 1, we have to copy values into next rows
                  else:
                        end = val - 1
                        
                        while end > 0:
                              events['condition'][idx+end] = events['condition'][idx]
                              events['target'][idx+end] = events['target'][idx]
                              
                              end = end-1

            with open('./scp_subject_information.json') as incoming:
                  networks = json.load(incoming)
                  
                  def iso_value(x, var):
                        """
                        Match target stimuli with their corresponding network values
                        """

                        try:
                              return float(networks[x][var])
                        except:
                              return None
                        
                  for var in self.network_regressors:
                        # Create new column for every network regressor
                        events[var] = events[target_column].apply(lambda x: iso_value(x, var))

            def binarize_condition(x, condition):
                  if x == condition:
                        return 1
                  else:
                        return 0
                  
            for condition in ['nondorm', 'dorm', 'attention_check']:
                  events[condition] = events['condition'].apply(lambda x: binarize_condition(x, condition))

            try:
                  events.drop(columns=['condition', 'target', 'duration'], inplace=True)
            except:
                  print('we gucci')

            for var in self.network_regressors:
                  events[var] = events[var].fillna(0)

            return events


      def firstLevel_design(self):
            """
            Here's the good stuff

            * Compile session information - self.session_info()
            * Specify model information - modelgen.model.SpecifyModel()
            * Feed contrasts to level one design - fsl.model.Level1Design()
            * Populate FSL design matrix - fsl.model.FEATModel()
            * Drive everything back from memory into output directories
            """

            import nipype.algorithms.modelgen as model
            from nipype.interfaces import fsl
            from nipype.caching import Memory
            from time import sleep
            import shutil

            mem = Memory(self.first_level_output)                 # Memory cache (instead of NiPype)
            
            # Bunch object defined above
            run_info = self.session_info(confound_regressors=self.confound_regressors,
                                          network_regressors=self.network_regressors,
                                          # NOTE: Hardcoded - change this
                                          target_var='target',
                                          include_dummies=False)

            sleep(0.5)
            print("--------- Specifying model")
            s = model.SpecifyModel(input_units='secs',
                                   functional_runs=self.preprocessed_bold_only,
                                   time_repetition=1.,
                                   high_pass_filter_cutoff=128.,
                                   subject_info=run_info)

            s_results = s.run()
            s.inputs

            sleep(0.5)
            print("\n--------- Running Level1Design")
            level1_design = mem.cache(fsl.model.Level1Design)
            level1_results = level1_design(interscan_interval=1.,
                                           bases={'dgamma': {'derivs': False}},
                                           session_info=s_results.outputs.session_info,
                                           model_serial_correlations=True,
                                           contrasts=self.contrasts)

            level1_results.outputs

            sleep(0.5)
            print("\n--------- Running FEATModel")
            modelgen = mem.cache(fsl.model.FEATModel)
            modelgen_results = modelgen(fsf_file = level1_results.outputs.fsf_files,
                                        ev_files = level1_results.outputs.ev_files)

            modelgen_results.outputs


            sleep(0.5)
            print("\n--------- Restructuring model output")

            # Landing directories
            target = [self.nipype_level_one, self.nipype_feat_model]

            # Memory caches
            source = ['nipype_mem/nipype-interfaces-fsl-model-Level1Design',
                      'nipype_mem/nipype-interfaces-fsl-model-FEATModel']

            # Join relative paths
            source = [os.path.join(self.first_level_output, x) for x in source]

            for target_x, source_x in zip(target, source):
                  # Iso subdir (different name every time, alas)
                  source_iso = [k.path for k in os.scandir(source_x) if k.is_dir()][0]

                  # Move files from source to target directory
                  for file in os.listdir(source_iso):
                        shutil.move(os.path.join(source_iso, file), target_x)

            # Remove 
            shutil.rmtree(os.path.join(self.first_level_output, 'nipype_mem'))


      def firstLevel_contrasts(self):
            """
            Leverages nilearn.glm.first_level module
            Calculates contrasts
            Saves z-map NifTi's and plots
            """

            from nilearn.glm import first_level
            from nilearn._utils.glm import get_design_from_fslmat
            from nilearn.reporting import make_glm_report
            import nilearn.plotting as nip

            fsl_design = os.path.join(self.nipype_feat_model, 'run0.mat')
            dm = get_design_from_fslmat(fsl_design)

            with open(os.path.join(self.nipype_feat_model, "regressor_names.txt")) as incoming:
                  dm_columns = incoming.read().split('\n')[:-1]

            dm.columns = dm_columns
            nip.plot_design_matrix(dm, output_file=f"{self.first_level_output}/nilearn/plotting/sub-{self.subID}_design-matrix.png")

            model = first_level.FirstLevelModel(t_r=1., smoothing_fwhm=4., hrf_model='spm')

            print("\n--------- Fitting model, please hold...")
            model.fit(self.preprocessed_bold_only, design_matrices=dm)

            print("\n--------- Mapping condition z-scores\n")

            contrasts_of_interest = list(self.conditions) + list(self.network_regressors)

            for contrast in tqdm(contrasts_of_interest):

                  glass_output = f"{self.nilearn_plotting_condition}/sub-{self.subID}_condition-{contrast}_plot-glass-brain.png"
                  stat_output = f"{self.nilearn_plotting_condition}/sub-{self.subID}_condition-{contrast}_plot-stat-map.png"
                  report_output = f"{self.nilearn_plotting_condition}/sub-{self.subID}_condition-{contrast}_summary.html"
                  nifti_output = f"{self.nilearn_first_level_condition}/sub-{self.subID}_condition-{contrast}_z-map.nii.gz"

                  z_map = model.compute_contrast(contrast)

                  nip.plot_glass_brain(z_map, colorbar=False, threshold=3,
                                    plot_abs=False, display_mode='lyrz',
                                    title=contrast, output_file=glass_output)

                  nip.plot_stat_map(z_map, threshold=3, colorbar=False,
                              draw_cross=False, display_mode='ortho',
                              title=contrast, output_file=stat_output)

                  make_glm_report(model=model,
                              contrasts=contrast,
                              plot_type='glass').save_as_html(report_output)

                  z_map.to_filename(os.path.join(nifti_output))

            print("\n--------- Mapping contrast z-scores\n")

            for outer in tqdm(self.conditions):
                  for inner in self.conditions:

                        if (inner == "attention_check" or outer == "attention_check"):
                              continue

                        if outer != inner:

                              z_contrast = f"{outer} - {inner}"
                              contrast = z_contrast.replace(' ', '')
                              glass_output = f"{self.nilearn_plotting_contrasts}/sub-{self.subID}_contrast-{contrast}_plot-glass-brain.png"
                              stat_output = f"{self.nilearn_plotting_contrasts}/sub-{self.subID}_contrast-{contrast}_plot-stat-map.png"
                              report_output = f"{self.nilearn_plotting_contrasts}/sub-{self.subID}_contrast-{contrast}_summary.html"
                              nifti_output = f"{self.nilearn_first_level_contrasts}/sub-{self.subID}_contrast-{contrast}_z-map.nii.gz"

                              z_map = model.compute_contrast(z_contrast)

                              nip.plot_glass_brain(z_map, colorbar=False, threshold=3,
                                                   plot_abs=False, display_mode='lyrz',
                                                   title=z_contrast, output_file=glass_output)

                              nip.plot_stat_map(z_map, threshold=3, colorbar=False,
                                                draw_cross=False, display_mode='ortho',
                                                title=z_contrast, output_file=stat_output)

                              make_glm_report(model=model,
                                          contrasts=z_contrast,
                                          plot_type='glass').save_as_html(report_output)

                              z_map.to_filename(os.path.join(nifti_output))


      def run_first_level_glm(self):
            """
            Wraps everything defined above...

            Let's call it neurochristmas
            """

            # Compute design matrix and regressors
            self.firstLevel_design()

            # Compute contrast z-maps and plots
            self.firstLevel_contrasts()

            print(f"\n\nContrasts computed! subject-{self.subID} has been mapped")

