from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from qtpy.QtCore import Signal, Slot
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
)

from snapred.backend.dao.LiveMetadata import LiveMetadata
from snapred.backend.dao.state.RunNumber import RunNumber
from snapred.backend.log.logger import snapredLogger
from snapred.meta.decorators.Resettable import Resettable
from snapred.meta.decorators.ExceptionToErrLog import ExceptionToErrLog
from snapred.ui.view.BackendRequestView import BackendRequestView
from snapred.ui.widget.Toggle import Toggle

logger = snapredLogger.getLogger(__name__)


class _RequestViewBase(BackendRequestView):

    @abstractmethod
    def useLiteMode(self) -> bool:
        pass

    @abstractmethod
    def keepUnfocused(self) -> bool:
        pass

    @abstractmethod
    def convertUnitsTo(self) -> str:
        pass

    @abstractmethod
    def liveDataMode(self) -> bool:
        pass

    @abstractmethod
    def getRunNumbers(self) -> List[str]:
        pass

    @abstractmethod
    def getPixelMasks(self) -> List[str]:
        pass


class _RequestView(_RequestViewBase):
    liveDataModeChange = Signal(bool)
       
    def __init__(
        self,
        parent=None,
        getCompatibleMasks: Optional[Callable[[List[str], bool], None]] = None,
        validateRunNumbers: Optional[Callable[[List[str]], None]] = None,
        getLiveMetadata: Optional[Callable[[], LiveMetadata]] = None,
    ):
        super(_RequestView, self).__init__(parent=parent)

        self.runNumbers = []
        self.pixelMaskDropdown = self._multiSelectDropDown("Select Pixel Mask(s)", [])
        self.getCompatibleMasks = getCompatibleMasks
        self.validateRunNumbers = validateRunNumbers
        self.getLiveMetadata = getLiveMetadata

        # Horizontal layout for run number input and button
        self.runNumberLayout = QHBoxLayout()
        self.runNumberInput = QLineEdit()
        self.runNumberInput.returnPressed.connect(self.addRunNumber)
        self.enterRunNumberButton = QPushButton("Enter Run Number")
        self.clearButton = QPushButton("Clear")
        self.runNumberButtonLayout = QVBoxLayout()
        self.runNumberButtonLayout.addWidget(self.enterRunNumberButton)
        self.runNumberButtonLayout.addWidget(self.clearButton)

        self.runNumberLayout.addWidget(self.runNumberInput)
        self.runNumberLayout.addLayout(self.runNumberButtonLayout)

        # Run number display
        self.runNumberDisplay = QListWidget()
        self.runNumberDisplay.setSortingEnabled(False)

        # Lite mode toggle, pixel masks dropdown, and retain unfocused data checkbox
        self.liteModeToggle = self._labeledField("Lite Mode", Toggle(parent=self, state=True))

        self.retainUnfocusedDataCheckbox = self._labeledCheckBox("Retain Unfocused Data")
        self.convertUnitsDropdown = self._sampleDropDown(
            "Convert Units", ["TOF", "dSpacing", "Wavelength", "MomentumTransfer"]
        )
        self.convertUnitsDropdown.setCurrentIndex(1)
        
        self.unfocusedDataLayout = QHBoxLayout()
        self.unfocusedDataLayout.addWidget(self.retainUnfocusedDataCheckbox, 1)
        self.unfocusedDataLayout.addWidget(self.convertUnitsDropdown, 2)
        
        # live-data toggle
        self.liveDataToggle = self._labeledField("Live", Toggle(parent=self, state=False))

        # Set field properties
        self.liteModeToggle.setEnabled(False)
        self.pixelMaskDropdown.setEnabled(False)
        self.retainUnfocusedDataCheckbox.setEnabled(False)
        self.convertUnitsDropdown.setEnabled(False)

        # Add widgets to layout
        _layout = self.layout()
        _layout.addLayout(self.runNumberLayout, 0, 0, 1, 2)
        _layout.addWidget(self.runNumberDisplay, 1, 0, 1, 2)
        _layout.addWidget(self.liteModeToggle, 2, 0, 1, 1)
        _layout.addWidget(self.liveDataToggle, 2, 1, 1, 1)
        _layout.addWidget(self.pixelMaskDropdown, 3, 0, 1, 2)
        _layout.addLayout(self.unfocusedDataLayout, 4, 0, 1, 2)

        # Connect buttons to methods
        self.enterRunNumberButton.clicked.connect(self.addRunNumber)
        self.clearButton.clicked.connect(self.clearRunNumbers)
        self.retainUnfocusedDataCheckbox.checkedChanged.connect(self.convertUnitsDropdown.setEnabled)
        self.liveDataToggle.field.connectUpdate(lambda: self.liveDataModeChange.emit(self.liveDataToggle.field.getState()))

    @Slot()
    def addRunNumber(self):
        # TODO: FIX THIS!
        #   We're not inside the SNAPResponseHandler here, so we can't just throw a `ValueError`.
        try:
            runNumberList = self.parseInputRunNumbers()
            if runNumberList is not None:
                # remove duplicates
                noDuplicates = set(self.runNumbers)
                noDuplicates.update(runNumberList)
                noDuplicates = list(noDuplicates)
                if self.validateRunNumbers is not None:
                    self.validateRunNumbers(noDuplicates)
                self.runNumbers = noDuplicates
                self.updateRunNumberList()
                self.runNumberInput.clear()
                self._populatePixelMaskDropdown()
        except ValueError as e:
            QMessageBox.warning(self, "Warning", str(e), buttons=QMessageBox.Ok, defaultButton=QMessageBox.Ok)
            self.runNumberInput.clear()

    @ExceptionToErrLog
    def _populatePixelMaskDropdown(self):
        runNumbers = self.getRunNumbers()
        useLiteMode = self.liteModeToggle.field.getState()

        self.liteModeToggle.setEnabled(False)
        self.pixelMaskDropdown.setEnabled(False)
        self.retainUnfocusedDataCheckbox.setEnabled(False)

        try:
            # Get compatible masks for the current reduction state.
            masks = []
            if self.getCompatibleMasks:
                masks = self.getCompatibleMasks(runNumbers, useLiteMode)

            # Populate the dropdown with the mask names.
            self.pixelMaskDropdown.setItems(masks)
        except Exception as e:  # noqa: BLE001
            print(f"Error retrieving compatible masks: {e}")
            self._reductionRequestView.pixelMaskDropdown.setItems([])
        finally:
            # Re-enable UI elements.
            self.liteModeToggle.setEnabled(True)
            self.pixelMaskDropdown.setEnabled(True)
            self.retainUnfocusedDataCheckbox.setEnabled(True)

    def parseInputRunNumbers(self) -> List[str]:
        # WARNING: run numbers are strings.
        #   For now, it's OK to parse them as integer, but they should not be passed around that way.
        try:
            runs, errors = RunNumber.runsFromIntArrayProperty(self.runNumberInput.text(), False)

            if len(errors) > 0:
                messageBox = QMessageBox(
                    QMessageBox.Warning,
                    "Warning",
                    "There are issues with some run(s)",
                    QMessageBox.Ok,
                    self,
                )
                formattedErrors = "\n\n".join([error[1] for error in errors])
                messageBox.setDetailedText(f"{formattedErrors}")
                messageBox.exec()
        except Exception:  # noqa BLE001
            raise ValueError(
                "Bad input was given for Reduction runs,"
                "please read mantid docs for IntArrayProperty on how to format input"
            )

        return [str(num) for num in runs]

    def updateRunNumberList(self):
        self.runNumberDisplay.clear()
        self.runNumberDisplay.addItems(self.runNumbers)

    def clearRunNumbers(self):
        self.runNumbers.clear()
        self.runNumberDisplay.clear()
        self.pixelMaskDropdown.setItems([])

    ###
    ### Abstract methods:
    ###

    def verify(self):
        runNumbers = self.runNumbers
        if not runNumbers:
            raise ValueError("Please enter at least one run number.")
        if runNumbers != self.runNumbers:
            raise ValueError("Unexpected issue verifying run numbers.  Please clear and re-enter.")
        for runNumber in runNumbers:
            if not runNumber.isdigit():
                raise ValueError(
                    "Please enter a valid run number or list of run numbers. (e.g. 46680, 46685, 46686, etc...)"
                )
        if self.keepUnfocused():
            if self.convertUnitsDropdown.currentIndex() < 0:
                raise ValueError("Please select units to convert to")
        return True
    
    def useLiteMode(self) -> bool:
        return self.liteModeToggle.field.getState()

    def keepUnfocused(self) -> bool:
        return self.retainUnfocusedDataCheckbox.isChecked() 

    def convertUnitsTo(self) -> str:
        return self.convertUnitsDropdown.currentText()

    def liveDataMode(self) -> bool:
        return self.liveDataToggle.field.getState()

    def getRunNumbers(self) -> List[str]:
        return self.runNumbers

    def getPixelMasks(self) -> List[str]:
        return self.pixelMaskDropdown.checkedItems()



class _LiveDataView(_RequestViewBase):
    liveDataModeChange = Signal(bool)
        
    def __init__(
        self,
        parent=None,
        getCompatibleMasks: Optional[Callable[[List[str], bool], None]] = None,
        validateRunNumbers: Optional[Callable[[List[str]], None]] = None,
        getLiveMetadata: Optional[Callable[[], LiveMetadata]] = None,
    ):
        super(_LiveDataView, self).__init__(parent=parent)

        self.runNumbers = []
        self.pixelMaskDropdown = self._multiSelectDropDown("Select Pixel Mask(s)", [])
        self.getCompatibleMasks = getCompatibleMasks
        self.validateRunNumbers = validateRunNumbers
        self.getLiveMetadata = getLiveMetadata

        # Lite mode toggle, pixel masks dropdown, and retain unfocused data checkbox
        self.liteModeToggle = self._labeledField("Lite Mode", Toggle(parent=self, state=True))

        self.retainUnfocusedDataCheckbox = self._labeledCheckBox("Retain Unfocused Data")
        self.convertUnitsDropdown = self._sampleDropDown(
            "Convert Units", ["TOF", "dSpacing", "Wavelength", "MomentumTransfer"]
        )
        self.convertUnitsDropdown.setCurrentIndex(1)
        
        self.unfocusedDataLayout = QHBoxLayout()
        self.unfocusedDataLayout.addWidget(self.retainUnfocusedDataCheckbox, 1)
        self.unfocusedDataLayout.addWidget(self.convertUnitsDropdown, 2)
        
        # live-data toggle
        self.liveDataToggle = self._labeledField("Live", Toggle(parent=self, state=False))

        # Set field properties
        self.liteModeToggle.setEnabled(False)
        self.pixelMaskDropdown.setEnabled(False)
        self.retainUnfocusedDataCheckbox.setEnabled(False)
        self.convertUnitsDropdown.setEnabled(False)

        # Add widgets to layout
        _layout = self.layout()
        _layout.addWidget(self.liteModeToggle, 1, 0, 1, 1)
        _layout.addWidget(self.liveDataToggle, 1, 1, 1, 1)
        _layout.addWidget(self.pixelMaskDropdown, 2, 0, 1, 2)
        _layout.addLayout(self.unfocusedDataLayout, 3, 0, 1, 2)

        # Connect buttons to methods
        self.retainUnfocusedDataCheckbox.checkedChanged.connect(self.convertUnitsDropdown.setEnabled)
        self.liveDataToggle.field.connectUpdate(lambda: self.liveDataModeChange.emit(self.liveDataToggle.field.getState()))

    @Slot()
    def updateLiveMetadata(self):
        self.liveMetadata = self.getLiveMetadata()
        if self.liveMetadata.hasActiveRun():
            liveStateChange = not self.runNumbers or (self.runNumbers[0] != self.liveMetadata.runNumber)
            if liveStateChange:
                self.runNumbers = [self.liveMetadata.runNumber]
                self._populatePixelMaskDropdown()
        else:
            self.runNumbers = []
                
    @ExceptionToErrLog
    def _populatePixelMaskDropdown(self):
        runNumbers = self.getRunNumbers()
        useLiteMode = self.liteModeToggle.field.getState()

        self.liteModeToggle.setEnabled(False)
        self.pixelMaskDropdown.setEnabled(False)
        self.retainUnfocusedDataCheckbox.setEnabled(False)

        try:
            # Get compatible masks for the current reduction state.
            masks = []
            if self.getCompatibleMasks:
                masks = self.getCompatibleMasks(runNumbers, useLiteMode)

            # Populate the dropdown with the mask names.
            self.pixelMaskDropdown.setItems(masks)
        except Exception as e:  # noqa: BLE001
            print(f"Error retrieving compatible masks: {e}")
            self._reductionRequestView.pixelMaskDropdown.setItems([])
        finally:
            # Re-enable UI elements.
            self.liteModeToggle.setEnabled(True)
            self.pixelMaskDropdown.setEnabled(True)
            self.retainUnfocusedDataCheckbox.setEnabled(True)

    ###
    ### Abstract methods:
    ###

    def verify(self):
        if not self.liveMetadata.hasActiveRun():
            raise ValueError("No live-data acquisition is active.")
        for runNumber in self.runNumbers:
            if not runNumber.isdigit():
                raise ValueError("Unexpected run number format")
        if self.keepUnfocused():
            if self.convertUnitsDropdown.currentIndex() < 0:
                raise ValueError("Please select units to convert to")
        return True
    
    def useLiteMode(self) -> bool:
        return self.liteModeToggle.field.getState()

    def keepUnfocused(self) -> bool:
        return self.retainUnfocusedDataCheckbox.isChecked() 

    def convertUnitsTo(self) -> str:
        return self.convertUnitsDropdown.currentText()

    def liveDataMode(self) -> bool:
        return self.liveDataToggle.field.getState()

    def getRunNumbers(self) -> List[str]:
        return self.runNumbers

    def getPixelMasks(self) -> List[str]:
        return self.pixelMaskDropdown.checkedItems()


@Resettable
class ReductionRequestView(_RequestViewBase):

    def __init__(
        self,
        parent=None,
        getCompatibleMasks: Optional[Callable[[List[str], bool], None]] = None,
        validateRunNumbers: Optional[Callable[[List[str]], None]] = None,
        getLiveMetadata: Optional[Callable[[], LiveMetadata]] = None,
    ):
        super(ReductionRequestView, self).__init__(parent=parent)

        self._requestView = _RequestView(
            parent=parent,
            getCompatibleMasks=getCompatibleMasks,
            validateRunNumbers=validateRunNumbers,
            getLiveMetadata=getLiveMetadata
        )
        self._liveDataView = _LiveDataView(
            parent=parent,
            getCompatibleMasks=getCompatibleMasks,
            validateRunNumbers=validateRunNumbers,
            getLiveMetadata=getLiveMetadata
        )

        self._stackedLayout = QStackedLayout()
        self._stackedLayout.addWidget(self._requestView)
        self._stackedLayout.addWidget(self._liveDataView)
        self.layout().addLayout(self._stackedLayout, 0, 0)

        # Connect signals to slots
        self._stackedLayout.currentChanged.connect(self._changeLiveDataMode)
        self._requestView.liveDataModeChange.connect(self._liveDataModeChange)
        self._liveDataView.liveDataModeChange.connect(self._liveDataModeChange)

    @Slot(bool)
    def _liveDataModeChange(self, flag: bool):
        if flag:
            self._stackedLayout.setCurrentWidget(self._liveDataView)  
        else:
            self._stackedLayout.setCurrentWidget(self._requestView)

    @Slot()
    def _changeLiveDataMode(self):
        if self._stackedLayout.currentWidget() == self._requestView:
            self._requestView.liveDataToggle.field.setState(False)
        elif self._stackedLayout.currentWidget() == self._liveDataView:
            self._liveDataView.liveDataToggle.field.setState(True)
            self._liveDataView.updateLiveMetadata()
    
                
    ###
    ### Abstract methods:
    ###
    def verify(self):
        self._stackedLayout.currentWidget().verify()
    
    def useLiteMode(self) -> bool:
        return self._stackedLayout.currentWidget().useLiteMode()

    def keepUnfocused(self) -> bool:
        return self._stackedLayout.currentWidget().keepUnfocused()

    def convertUnitsTo(self) -> str:
        return self._stackedLayout.currentWidget().convertUnitsTo()

    def liveDataMode(self) -> bool:
        return self._stackedLayout.currentWidget().liveDataMode()

    def getRunNumbers(self) -> List[str]:
        return self._stackedLayout.currentWidget().getRunNumbers()

    def getPixelMasks(self) -> List[str]:
        return self._stackedLayout.currentWidget().getPixelMasks()


"""
@Resettable
class ReductionRequestView(_RequestViewBase, BackendRequestView):
        
    def __init__(
        self,
        parent=None,
        getCompatibleMasks: Optional[Callable[[List[str], bool], None]] = None,
        validateRunNumbers: Optional[Callable[[List[str]], None]] = None,
    ):
        super(ReductionRequestView, self).__init__(parent=parent)

        self.runNumbers = []
        self.pixelMaskDropdown = self._multiSelectDropDown("Select Pixel Mask(s)", [])
        self.getCompatibleMasks = getCompatibleMasks
        self.validateRunNumbers = validateRunNumbers

        # Horizontal layout for run number input and button
        self.runNumberLayout = QHBoxLayout()
        self.runNumberInput = QLineEdit()
        self.runNumberInput.returnPressed.connect(self.addRunNumber)
        self.enterRunNumberButton = QPushButton("Enter Run Number")
        self.clearButton = QPushButton("Clear")
        self.runNumberButtonLayout = QVBoxLayout()
        self.runNumberButtonLayout.addWidget(self.enterRunNumberButton)
        self.runNumberButtonLayout.addWidget(self.clearButton)

        self.runNumberLayout.addWidget(self.runNumberInput)
        self.runNumberLayout.addLayout(self.runNumberButtonLayout)

        # Run number display
        self.runNumberDisplay = QListWidget()
        self.runNumberDisplay.setSortingEnabled(False)

        # Lite mode toggle, pixel masks dropdown, and retain unfocused data checkbox
        self.liteModeToggle = self._labeledField("Lite Mode", Toggle(parent=self, state=True))

        self.retainUnfocusedDataCheckbox = self._labeledCheckBox("Retain Unfocused Data")
        self.convertUnitsDropdown = self._sampleDropDown(
            "Convert Units", ["TOF", "dSpacing", "Wavelength", "MomentumTransfer"]
        )
        self.convertUnitsDropdown.setCurrentIndex(1)
        
        self.unfocusedDataLayout = QHBoxLayout()
        self.unfocusedDataLayout.addWidget(self.retainUnfocusedDataCheckbox, 1)
        self.unfocusedDataLayout.addWidget(self.convertUnitsDropdown, 2)
        
        # live-data toggle
        self.liveDataToggle = self._labeledField("Live", Toggle(parent=self, state=False))

        # Set field properties
        self.liteModeToggle.setEnabled(False)
        self.pixelMaskDropdown.setEnabled(False)
        self.retainUnfocusedDataCheckbox.setEnabled(False)
        self.convertUnitsDropdown.setEnabled(False)

        # Add widgets to layout
        _layout = self.layout()
        _layout.addLayout(self.runNumberLayout, 0, 0, 1, 2)
        _layout.addWidget(self.runNumberDisplay, 1, 0, 1, 2)
        _layout.addWidget(self.liteModeToggle, 2, 0, 1, 1)
        _layout.addWidget(self.liveDataToggle, 2, 1, 1, 1)
        _layout.addWidget(self.pixelMaskDropdown, 3, 0, 1, 2)
        _layout.addLayout(self.unfocusedDataLayout, 4, 0, 1, 2)

        # Connect buttons to methods
        self.enterRunNumberButton.clicked.connect(self.addRunNumber)
        self.clearButton.clicked.connect(self.clearRunNumbers)
        self.retainUnfocusedDataCheckbox.checkedChanged.connect(self.convertUnitsDropdown.setEnabled)

    @Slot()
    def addRunNumber(self):
        # TODO: FIX THIS!
        #   We're not inside the SNAPResponseHandler here, so we can't just throw a `ValueError`.
        try:
            runNumberList = self.parseInputRunNumbers()
            if runNumberList is not None:
                # remove duplicates
                noDuplicates = set(self.runNumbers)
                noDuplicates.update(runNumberList)
                noDuplicates = list(noDuplicates)
                if self.validateRunNumbers is not None:
                    self.validateRunNumbers(noDuplicates)
                self.runNumbers = noDuplicates
                self.updateRunNumberList()
                self.runNumberInput.clear()
                self._populatePixelMaskDropdown()
        except ValueError as e:
            QMessageBox.warning(self, "Warning", str(e), buttons=QMessageBox.Ok, defaultButton=QMessageBox.Ok)
            self.runNumberInput.clear()

    @ExceptionToErrLog
    def _populatePixelMaskDropdown(self):
        runNumbers = self.getRunNumbers()
        useLiteMode = self.liteModeToggle.field.getState()

        self.liteModeToggle.setEnabled(False)
        self.pixelMaskDropdown.setEnabled(False)
        self.retainUnfocusedDataCheckbox.setEnabled(False)

        try:
            # Get compatible masks for the current reduction state.
            masks = []
            if self.getCompatibleMasks:
                masks = self.getCompatibleMasks(runNumbers, useLiteMode)

            # Populate the dropdown with the mask names.
            self.pixelMaskDropdown.setItems(masks)
        except Exception as e:  # noqa: BLE001
            print(f"Error retrieving compatible masks: {e}")
            self._reductionRequestView.pixelMaskDropdown.setItems([])
        finally:
            # Re-enable UI elements.
            self.liteModeToggle.setEnabled(True)
            self.pixelMaskDropdown.setEnabled(True)
            self.retainUnfocusedDataCheckbox.setEnabled(True)

    def parseInputRunNumbers(self) -> List[str]:
        # WARNING: run numbers are strings.
        #   For now, it's OK to parse them as integer, but they should not be passed around that way.
        try:
            runs, errors = RunNumber.runsFromIntArrayProperty(self.runNumberInput.text(), False)

            if len(errors) > 0:
                messageBox = QMessageBox(
                    QMessageBox.Warning,
                    "Warning",
                    "There are issues with some run(s)",
                    QMessageBox.Ok,
                    self,
                )
                formattedErrors = "\n\n".join([error[1] for error in errors])
                messageBox.setDetailedText(f"{formattedErrors}")
                messageBox.exec()
        except Exception:  # noqa BLE001
            raise ValueError(
                "Bad input was given for Reduction runs,"
                "please read mantid docs for IntArrayProperty on how to format input"
            )

        return [str(num) for num in runs]

    def updateRunNumberList(self):
        self.runNumberDisplay.clear()
        self.runNumberDisplay.addItems(self.runNumbers)

    def clearRunNumbers(self):
        self.runNumbers.clear()
        self.runNumberDisplay.clear()
        self.pixelMaskDropdown.setItems([])

    def verify(self):
        runNumbers = [self.runNumberDisplay.item(x).text() for x in range(self.runNumberDisplay.count())]
        if not runNumbers:
            raise ValueError("Please enter at least one run number.")
        if runNumbers != self.runNumbers:
            raise ValueError("Unexpected issue verifying run numbers.  Please clear and re-enter.")
        for runNumber in runNumbers:
            if not runNumber.isdigit():
                raise ValueError(
                    "Please enter a valid run number or list of run numbers. (e.g. 46680, 46685, 46686, etc...)"
                )
        if self.retainUnfocusedDataCheckbox.isChecked():
            if self.convertUnitsDropdown.currentIndex() < 0:
                raise ValueError("Please select units to convert to")
        return True

    ###
    ### Abstract methods:
    ###
    
    def useLiteMode(self) -> bool:
        return self.liteModeToggle.field.getState()

    def keepUnfocused(self) -> bool:
        return self.retainUnfocusedDataCheckbox.isChecked() 

    def convertUnitsTo(self) -> str:
        return self.convertUnitsDropdown.currentText()

    def liveDataMode(self) -> bool:
        return self.liveDataToggle.field.getState()

    def getRunNumbers(self) -> List[str]:
        return self.runNumbers

    def getPixelMasks(self) -> List[str]:
        return self.pixelMaskDropdown.checkedItems()
"""
