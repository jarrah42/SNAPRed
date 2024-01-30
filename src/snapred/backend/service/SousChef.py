import json
import time
from datetime import date
from functools import lru_cache
from typing import Dict, List, Tuple

from pydantic import parse_raw_as

from snapred.backend.dao import CrystallographicInfo, GroupPeakList, RunConfig
from snapred.backend.dao.calibration import Calibration
from snapred.backend.dao.ingredients import (
    DiffractionCalibrationIngredients,
    GroceryListItem,
    NormalizationIngredients,
    PeakIngredients,
    PixelGroupingIngredients,
    ReductionIngredients,
)
from snapred.backend.dao.request import FarmFreshIngredients
from snapred.backend.dao.state import FocusGroup, InstrumentState, PixelGroup
from snapred.backend.dao.state.CalibrantSample import CalibrantSamples
from snapred.backend.data.DataFactoryService import DataFactoryService
from snapred.backend.data.GroceryService import GroceryService
from snapred.backend.recipe.GenericRecipe import (
    DetectorPeakPredictorRecipe,
)
from snapred.backend.recipe.PixelGroupingParametersCalculationRecipe import PixelGroupingParametersCalculationRecipe
from snapred.backend.service.CrystallographicInfoService import CrystallographicInfoService
from snapred.backend.service.Service import Service
from snapred.meta.Config import Config
from snapred.meta.decorators.FromString import FromString
from snapred.meta.decorators.Singleton import Singleton
from snapred.meta.redantic import list_to_raw


@Singleton
class SousChef(Service):
    """
    It slices, it dices, and it knows how to make the more complicated ingredients.
    """

    # register the service in ServiceFactory please!
    def __init__(self):
        super().__init__()
        self.groceryService = GroceryService()
        self.groceryClerk = GroceryListItem.builder()
        self.dataFactoryService = DataFactoryService()
        self._pixelGroupCache: Dict[Tuple[str, bool, str], PixelGroup] = {}
        self._calibrationCache: Dict[str, Calibration] = {}
        self._peaksCache: Dict[Tuple[str, bool, str, float], List[GroupPeakList]] = {}
        self._xtalCache: Dict[Tuple[str, float, float], CrystallographicInfo] = {}
        return

    @staticmethod
    def name():
        return "souschef"

    def prepCalibration(self, runNumber: str) -> Calibration:
        if runNumber not in self._calibrationCache:
            self._calibrationCache[runNumber] = self.dataFactoryService.getCalibrationState(runNumber)
        return self._calibrationCache[runNumber]

    def prepInstrumentState(self, runNumber: str) -> InstrumentState:
        return self.prepCalibration(runNumber).instrumentState

    def prepRunConfig(self, runNumber: str) -> RunConfig:
        return self.dataFactoryService.getRunConfig(runNumber)

    def prepCalibrantSample(self, calibrantSamplePath: str) -> CalibrantSamples:
        return self.dataFactoryService.getCalibrantSample(calibrantSamplePath)

    def prepPixelGroup(self, ingredients: FarmFreshIngredients):
        groupingSchema = ingredients.focusGroup.name
        key = (ingredients.runNumber, ingredients.useLiteMode, groupingSchema)
        if key not in self._pixelGroupCache:
            instrumentState = self.prepInstrumentState(ingredients.runNumber)
            pixelIngredients = PixelGroupingIngredients(
                instrumentState=instrumentState,
                nBinsAcrossPeakWidth=ingredients.nBinsAcrossPeakWidth,
            )
            getGrouping = (
                self.groceryClerk.grouping(ingredients.focusGroup.name)
                .useLiteMode(ingredients.useLiteMode)
                .source(InstrumentFilename=self._getInstrumentDefinitionFilename(ingredients.useLiteMode))
                .buildList()
            )
            groupingWS = self.groceryService.fetchGroceryList(getGrouping)[0]
            data = PixelGroupingParametersCalculationRecipe().executeRecipe(pixelIngredients, groupingWS)
            self._pixelGroupCache[key] = PixelGroup(
                focusGroup=ingredients.focusGroup,
                pixelGroupingParameters=data["parameters"],
                timeOfFlight=data["tof"],
                nBinsAcrossPeakWidth=ingredients.nBinsAcrossPeakWidth,
            )
        return self._pixelGroupCache[key]

    def _getInstrumentDefinitionFilename(self, useLiteMode: bool):
        if useLiteMode is True:
            return Config["instrument.lite.definition.file"]
        elif useLiteMode is False:
            return Config["instrument.native.definition.file"]

    def prepCrystallographicInfo(self, ingredients: FarmFreshIngredients):
        if not ingredients.cifPath:
            samplePath = ingredients.calibrantSamplePath.split("/")[-1].split(".")[0]
            ingredients.cifPath = self.dataFactoryService.getCifFilePath(samplePath)
        key = (ingredients.cifPath, ingredients.dBounds.minimum, ingredients.dBounds.maximum)
        if key not in self._xtalCache:
            self._xtalCache[key] = CrystallographicInfoService().ingest(*key)["crystalInfo"]
        return self._xtalCache[key]

    def prepPeakIngredients(self, ingredients: FarmFreshIngredients) -> PeakIngredients:
        return PeakIngredients(
            crystalInfo=self.prepCrystallographicInfo(ingredients),
            instrumentState=self.prepInstrumentState(ingredients.runNumber),
            pixelGroup=self.prepPixelGroup(ingredients),
            peakIntensityThreshold=ingredients.peakIntensityThreshold,
        )

    def prepDetectorPeaks(self, ingredients: FarmFreshIngredients) -> List[GroupPeakList]:
        key = (
            ingredients.runNumber,
            ingredients.useLiteMode,
            ingredients.focusGroup.name,
            ingredients.peakIntensityThreshold,
        )
        if key not in self._peaksCache:
            ingredients = self.prepPeakIngredients(ingredients)
            res = DetectorPeakPredictorRecipe().executeRecipe(
                Ingredients=ingredients,
            )
            self._peaksCache[key] = parse_raw_as(List[GroupPeakList], res)
        return self._peaksCache[key]

    def prepReductionIngredients(self, ingredients: FarmFreshIngredients) -> ReductionIngredients:
        return ReductionIngredients(
            reductionState=self.dataFactoryService.getReductionState(ingredients.runNumber),
            runConfig=self.prepRunConfig(ingredients.runNumber),
            pixelGroup=self.prepPixelGroup(ingredients),
        )

    def prepNormalizationIngredients(self, ingredients: FarmFreshIngredients) -> NormalizationIngredients:
        return NormalizationIngredients(
            pixelGroup=self.prepPixelGroup(ingredients),
            calibrantSample=self.prepCalibrantSample(ingredients.calibrantSamplePath),
            detectorPeaks=self.prepDetectorPeaks(ingredients),
        )

    def prepDiffractionCalibrationIngredients(
        self, ingredients: FarmFreshIngredients
    ) -> DiffractionCalibrationIngredients:
        return DiffractionCalibrationIngredients(
            runConfig=self.prepRunConfig(ingredients.runNumber),
            pixelGroup=self.prepPixelGroup(ingredients),
            groupedPeakLists=self.prepDetectorPeaks(ingredients),
            convergenceThreshold=ingredients.convergenceThreshold,
            maxOffset=ingredients.maxOffset,
        )