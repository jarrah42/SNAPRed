# Use this script to test Pixel Diffraction Background Subtraction
from mantid.simpleapi import *
import matplotlib.pyplot as plt
import numpy as np
import json
from typing import List


## for creating ingredients
from snapred.backend.dao.request.FarmFreshIngredients import FarmFreshIngredients
from snapred.backend.service.SousChef import SousChef

## for loading data
from snapred.backend.dao.ingredients.GroceryListItem import GroceryListItem
from snapred.backend.data.GroceryService import GroceryService

## the code to test
from snapred.backend.recipe.PixelDiffCalRecipe import PixelDiffCalRecipe as PixelRx

from snapred.meta.Config import Config

#User input ###########################
runNumber = "58882"
groupingScheme = "Column"
cifPath = "/SNS/SNAP/shared/Calibration/CalibrantSamples/cif/Silicon_NIST_640d.cif"
calibrantSamplePath = "Silicon_NIST_640D_001.json"
peakThreshold = 0.05
offsetConvergenceLimit = 0.1
isLite = True
removeBackground = True
Config._config["cis_mode"] = True
Config._config["diffraction.smoothingParameter"] = 0.01  #This is the smoothing parameter to be set.
#######################################

### PREP INGREDIENTS ################
farmFresh = FarmFreshIngredients(
    runNumber=runNumber,
    useLiteMode=isLite,
    focusGroups=[{"name": groupingScheme, "definition": ""}],
    cifPath=cifPath,
    calibrantSamplePath=calibrantSamplePath,
    convergenceThreshold=offsetConvergenceLimit,
    maxOffset=100.0,
)
ingredients = SousChef().prepDiffractionCalibrationIngredients(farmFresh)

# HERE IS THE BACKGROUND REMOVAL TOGGLE!
ingredients.removeBackground = removeBackground 

### FETCH GROCERIES ##################

clerk = GroceryListItem.builder()
clerk.name("inputWorkspace").neutron(runNumber).useLiteMode(isLite).add()
clerk.name("groupingWorkspace").fromRun(runNumber).grouping(groupingScheme).useLiteMode(isLite).add()
groceries = GroceryService().fetchGroceryDict(
    clerk.buildDict(),
    outputWorkspace="_out_",
    diagnosticWorkspace="_diag",
    maskWorkspace="_mask_",
    calibrationTable="_DIFC_",    
)

### RUN PIXEL CALIBRATION ##########

pixelRx = PixelRx()
pixelRx.prep(ingredients, groceries)
pixelRes = pixelRx.execute()

### PREPARE OUTPUTS ################
DiffractionFocussing(
    InputWorkspace=f"dsp_0{runNumber}_raw_startOfPixelDiffCal",
    OutputWorkspace="BEFORE_REMOVAL",
    GroupingWorkspace=groceries["groupingWorkspace"],
)
DiffractionFocussing(
    InputWorkspace=f"dsp_0{runNumber}_raw_withoutBackground",
    OutputWorkspace="AFTER_REMOVAL",
    GroupingWorkspace=groceries["groupingWorkspace"],
)
DiffractionFocussing(
    InputWorkspace="tof_all_lite_copy1_058882",
    OutputWorkspace="FINAL",
    GroupingWorkspace=groceries["groupingWorkspace"],
)
 
