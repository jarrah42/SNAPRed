# import mantid algorithms, numpy and matplotlib
import snapred.backend.recipe.algorithm
from mantid.simpleapi import *
import matplotlib.pyplot as plt
import numpy as np
import json
## for creating ingredients
from snapred.backend.dao.request.FarmFreshIngredients import FarmFreshIngredients
from snapred.backend.service.SousChef import SousChef

## for loading data
from snapred.backend.dao.ingredients.GroceryListItem import GroceryListItem
from snapred.backend.data.GroceryService import GroceryService

from snapred.meta.Config import Config
from snapred.meta.pointer import create_pointer, access_pointer

#User input ###########################
runNumber = "58882"
groupingScheme = "Bank"
# cifPath = "diamond.cif"
calibrantSamplePath = "Silicon_NIST_640D_001.json"
peakThreshold = 0.05
offsetConvergenceLimit = 0.1
isLite = True
Config._config["cis_mode"] = False
#######################################

### PREP INGREDIENTS ################
farmFresh = FarmFreshIngredients(
    runNumber=runNumber,
    useLiteMode=isLite,
    focusGroups=[{"name": groupingScheme, "definition": ""}],
    # cifPath=cifPath,
    calibrantSamplePath=calibrantSamplePath,
    peakIntensityThreshold=peakThreshold,
    convergenceThreshold=offsetConvergenceLimit,
    maxOffset=100.0,
)
pixelGroup = SousChef().prepPixelGroup(farmFresh)
detectorPeaks = SousChef().prepDetectorPeaks(farmFresh)

total = "peak_and_background"
background = "bkg_foc"
peaks = "peaks_foc"
ref = "end_foc"

### FETCH GROCERIES ##################

clerk = GroceryListItem.builder()
clerk.name("inputWorkspace").neutron(runNumber).useLiteMode(isLite).add()
clerk.name("groupingWorkspace").fromRun(runNumber).grouping(groupingScheme).useLiteMode(isLite).add()
groceries = GroceryService().fetchGroceryDict(clerk.buildDict())

inputWorkspace = groceries["inputWorkspace"]
focusWorkspace = groceries["groupingWorkspace"]

Rebin(
    InputWorkspace=inputWorkspace,
    OutputWorkspace=inputWorkspace,
    Params=pixelGroup.timeOfFlight.params,
)
ScaleX(
    InputWorkspace=inputWorkspace,
    OutputWorkspace=inputWorkspace,
    Factor=1.02,
    IndexMin=1,
)


### NO BACKGROUND REMOVAL ##

ConvertUnits(
    InputWorkspace=inputWorkspace,
    OutputWorkspace=total,
    Target="dSpacing",
)
DiffractionFocussing(
    InputWorkspace=total,
    GroupingWorkspace=focusWorkspace,
    OutputWorkspace=total,
)
CrossCorrelate(
    InputWorkspace=total,
    OutputWorkspace="no_removal",
    WorkspaceIndexList=[1],
    XMin = 0.4,
    XMax = 4.0,
)
GetDetectorOffsets(
    InputWorkspace="no_removal",
    OutputWorkspace="no_removal_offset",
    Xmin=-10,
    Xmax=10,
)

### REMOVE EVENT BACKGROUND BY BLANKS ##

"""
    Logic notes:
    Given event data, and a list of know peak windows, remove all events not in a peak window.
    The events can be removed with masking.
    The peak windows are usually given in d-spacing, so requries first converting units to d-space.
    The peak windoews are specific to a grouping, so need to act by-group.
    On each group, remove non-peak events from all detectors in that group.
"""

# perform the steps of the prototype algo
blanks = {}
groupIDs = []
for peakList in detectorPeaks:
    groupIDs.append(peakList.groupID)
    blanks[peakList.groupID] = [(0, peakList.peaks[0].minimum)]
    for i in range(len(peakList.peaks) - 1):
        blanks[peakList.groupID].append((peakList.peaks[i].maximum, peakList.peaks[i+1].minimum))
    blanks[peakList.groupID].append((peakList.peaks[-1].maximum, 10.0))
groupDetectorIDs = access_pointer(GroupedDetectorIDs(focusWorkspace))

ConvertUnits(
    InputWorkspace=inputWorkspace,
    OutputWorkspace=ref,
    Target="dSpacing",
)

ws = mtd[ref]
for groupID in groupIDs:
    for detid in groupDetectorIDs[groupID]:
        event_list = ws.getEventList(detid)
        for blank in blanks[groupID]:
            event_list.maskTof(blank[0], blank[1])

ConvertUnits(
    InputWorkspace=ref,
    OutputWorkspace=ref,
    Target="TOF",
)
#

ConvertUnits(
    InputWorkspace=ref,
    OutputWorkspace=ref,
    Target="dSpacing",
)
DiffractionFocussing(
    InputWorkspace=ref,
    GroupingWorkspace=focusWorkspace,
    OutputWorkspace=ref,
)
CrossCorrelate(
    InputWorkspace=ref,
    OutputWorkspace="event_blank",
    WorkspaceIndexList=[1],
    XMin = 0.4,
    XMax = 4.0,
)
GetDetectorOffsets(
    InputWorkspace="event_blank",
    OutputWorkspace="event_blank_offset",
    Xmin=-10,
    Xmax=10,
)

### REMOVE EVENT BACKGROUND BY SMOOTHING ##

ConvertUnits(
    InputWorkspace=inputWorkspace,
    OutputWorkspace=background,
    Target="dSpacing",
)
DiffractionFocussing(
    InputWorkspace=background,
    GroupingWorkspace=focusWorkspace,
    OutputWorkspace=background,
)
SmoothDataExcludingPeaksAlgo(
    InputWorkspace=background,
    OutputWorkspace=background,
    DetectorPeaks = create_pointer(detectorPeaks),
    SmoothingParameter=0.5,
)
ws = Divide(
    LHSWorkspace=total,
    RHSWorkspace=background,
    OutputWorkspace=peaks,
)
ws.setDistribution(False)
ReplaceSpecialValues(
    InputWorkspace=peaks,
    OutputWorkspace=peaks,
    SmallNumberThreshold=0,
    SmallNumberValue=0,
    UseAbsolute=False,
)
CrossCorrelate(
    InputWorkspace=peaks,
    OutputWorkspace="smoothing",
    WorkspaceIndexList=[1],
    XMin = 0.4,
    XMax = 4.0,
)
GetDetectorOffsets(
    InputWorkspace="smoothing",
    OutputWorkspace="smoothing_offset",
    Xmin=-10,
    Xmax=10,
)

### PLOT PEAK RESULTS #################################
fig, ax = plt.subplots(subplot_kw={'projection':'mantid'})
ax.plot(mtd[total], wkspIndex=0, label="Total Data", normalize_by_bin_width=True)
ax.plot(mtd[ref], wkspIndex=0, label="Event Blanking", normalize_by_bin_width=True)
ax.plot(mtd[peaks], wkspIndex=0, label="Smoothing Subtraction", normalize_by_bin_width=True)
ax.legend()
fig.show()


### PLOT CC RESULTS #################################
fig, ax = plt.subplots(subplot_kw={'projection':'mantid'})
ax.plot(mtd["no_removal"], wkspIndex=0, label="Total Data", normalize_by_bin_width=True)
ax.plot(mtd["event_blank"], wkspIndex=0, label="Event Blanking", normalize_by_bin_width=True)
ax.plot(mtd["smoothing"], wkspIndex=0, label="Smoothing Subtraction", normalize_by_bin_width=True)
ax.legend()
fig.show()