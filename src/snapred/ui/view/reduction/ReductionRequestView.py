from typing import Callable, List, Optional

from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QGridLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget
)
from snapred.backend.log.logger import snapredLogger
from snapred.meta.decorators.Resettable import Resettable
from snapred.ui.view.BackendRequestView import BackendRequestView
from snapred.ui.widget.Toggle import Toggle

logger = snapredLogger.getLogger(__name__)


@Resettable
class ReductionRequestView(BackendRequestView):
    signalRemoveRunNumber = Signal(int)

    def __init__(
        self,
        parent=None,
        populatePixelMaskDropdown: Optional[Callable[[], None]] = None,
        validateRunNumbers: Optional[Callable[[List[str]], None]] = None,
    ):
        super(ReductionRequestView, self).__init__(parent=parent)

        self.runNumbers = []
        self.pixelMaskDropdown = self._multiSelectDropDown("Select Pixel Mask(s)", [])
        self.populatePixelMaskDropdown = populatePixelMaskDropdown
        self.validateRunNumbers = validateRunNumbers

        # Horizontal layout for run number input and button
        self.runNumberLayout = QHBoxLayout()
        self.runNumberInput = QLineEdit()
        self.enterRunNumberButton = QPushButton("Enter Run Number")
        self.clearButton = QPushButton("Clear")
        self.runNumberButtonLayout = QVBoxLayout()

        # Run number display
        self.runNumberDisplay = QTextEdit()
        self.runNumberDisplay.setReadOnly(True)

        # Lite-mode toggle, pixel masks dropdown, and retain unfocused data checkbox
        self.liteModeToggle = self._labeledField("Lite Mode", Toggle(parent=self, state=True))
        self.retainUnfocusedDataCheckbox = self._labeledCheckBox("Retain Unfocused Data")
        self.convertUnitsDropdown = self._sampleDropDown(
            "Convert Units", ["TOF", "dSpacing", "Wavelength", "MomentumTransfer"]
        )

        # Live-data toggle
        liveModeToggleColors = Toggle.Colors(background=(Qt.gray, Qt.darkRed), gradient=(Qt.darkRed, (Qt.gray, Qt.red)), button_face=Qt.lightGray)
        self.liveDataToggle = self._labeledField("Live", Toggle(parent=self, state=False, colors=liveModeToggleColors))
                
        # Set field properties
        self.liteModeToggle.setEnabled(False)
        self.retainUnfocusedDataCheckbox.setEnabled(False)
        self.pixelMaskDropdown.setEnabled(False)
        self.convertUnitsDropdown.setEnabled(False)
 
        # Connect buttons to methods
        self.enterRunNumberButton.clicked.connect(self.addRunNumber)
        self.clearButton.clicked.connect(self.clearRunNumbers)
        self.liveDataToggle.field.state_change.connect(self._setLiveDataMode)

        self.signalRemoveRunNumber.connect(self._removeRunNumber)

        # Set the current live-data mode
        self._setLiveDataMode(False, True)
        
    @Slot(bool)
    def _setLiveDataMode(self, live: bool, init: bool=False):
        self.setUpdatesEnabled(False)
       
        if live:
            if not init:
                # remove everything
                self.layout.removeItem(self.runNumberLayout)
                #
                self.runNumberLayout.removeItem(self.runNumberButtonLayout)
                self.runNumberLayout.removeWidget(self.runNumberInput)
                self.runNumberInput.setVisible(False)
                #
                self.runNumberButtonLayout.removeWidget(self.enterRunNumberButton)
                self.enterRunNumberButton.setVisible(False)
                self.runNumberButtonLayout.removeWidget(self.clearButton)
                self.clearButton.setVisible(False)
                #
                self.layout.removeWidget(self.runNumberDisplay)
                self.runNumberDisplay.setVisible(False)
                self.layout.removeWidget(self.liteModeToggle)
                self.layout.removeWidget(self.pixelMaskDropdown)
                self.layout.removeWidget(self.retainUnfocusedDataCheckbox)
                self.retainUnfocusedDataCheckbox.setVisible(False)
                self.layout.removeWidget(self.convertUnitsDropdown)
                self.convertUnitsDropdown.setVisible(False)
                self.layout.removeWidget(self.liveDataToggle)
            
            # add a few back
            self.layout.addWidget(self.liteModeToggle, 0, 2)
            self.layout.addWidget(self.pixelMaskDropdown)
            self.layout.addWidget(self.liveDataToggle, 2, 2)
        else:
            if not init:
                # remove a few
                self.layout.removeWidget(self.liteModeToggle)
                self.layout.removeWidget(self.pixelMaskDropdown)
                self.layout.removeWidget(self.liveDataToggle)
            
            # add everything back
            self.runNumberButtonLayout.addWidget(self.enterRunNumberButton)
            self.enterRunNumberButton.setVisible(True)
            self.runNumberButtonLayout.addWidget(self.clearButton)
            self.clearButton.setVisible(True)
            #
            self.runNumberLayout.addWidget(self.runNumberInput)
            self.runNumberLayout.addLayout(self.runNumberButtonLayout)
            self.runNumberInput.setVisible(True)
            #
            self.layout.addWidget(self.liteModeToggle, 0, 2)
            self.layout.addLayout(self.runNumberLayout, 1, 0)
            self.layout.addWidget(self.runNumberDisplay, 1, 1)
            self.runNumberDisplay.setVisible(True)
            self.layout.addWidget(self.pixelMaskDropdown, 2, 0)
            self.layout.addWidget(self.retainUnfocusedDataCheckbox, 3, 0)
            self.retainUnfocusedDataCheckbox.setVisible(True)
            self.layout.addWidget(self.convertUnitsDropdown, 3, 1)
            self.convertUnitsDropdown.setVisible(True)
            self.layout.addWidget(self.liveDataToggle, 3, 2)
            
        self.setUpdatesEnabled(True)
    
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
                if self.populatePixelMaskDropdown is not None:
                    self.populatePixelMaskDropdown()
        except ValueError as e:
            QMessageBox.warning(self, "Warning", str(e), buttons=QMessageBox.Ok, defaultButton=QMessageBox.Ok)
            self.runNumberInput.clear()

    def parseInputRunNumbers(self) -> List[str]:
        # WARNING: run numbers are strings.
        #   For now, it's OK to parse them as integer, but they should not be passed around that way.
        runNumberString = self.runNumberInput.text().strip()
        if runNumberString:
            runNumberList = [num.strip() for num in runNumberString.split(",") if num.strip()]
            for runNumber in runNumberList:
                if not runNumber.isdigit():
                    raise ValueError(
                        "Please enter a valid run number or list of run numbers. (e.g. 46680, 46685, 46686, etc...)"
                    )
            return runNumberList

    @Slot()
    def removeRunNumber(self, runNumber):
        self.signalRemoveRunNumber.emit(runNumber)

    @Slot()
    def _removeRunNumber(self, runNumber):
        if runNumber not in self.runNumbers:
            logger.warning(
                f"[ReductionRequestView]: attempting to remove run {runNumber} not in the list {self.runNumbers}"
            )
            return
        self.runNumbers.remove(runNumber)
        self.updateRunNumberList()

    def updateRunNumberList(self):
        self.runNumberDisplay.setText("\n".join(map(str, sorted(self.runNumbers))))

    def clearRunNumbers(self):
        self.runNumbers.clear()
        self.runNumberDisplay.clear()

    def verify(self):
        currentText = self.runNumberDisplay.toPlainText()
        runNumbers = [num.strip() for num in currentText.split("\n") if num.strip()]
        if not runNumbers:
            raise ValueError("Please enter at least one run number.")
        for runNumber in runNumbers:
            if not runNumber.isdigit():
                raise ValueError(
                    "Please enter a valid run number or list of run numbers. (e.g. 46680, 46685, 46686, etc...)"
                )
        # They dont need to select a pixel mask
        # if self.pixelMaskDropdown.currentIndex() < 0:
        #     raise ValueError("Please select a pixel mask.")
        if self.retainUnfocusedDataCheckbox.isChecked():
            if self.convertUnitsDropdown.currentIndex() < 0:
                raise ValueError("Please select units to convert to")
        return True

    def getRunNumbers(self):
        return self.runNumbers

    def getPixelMasks(self):
        return self.pixelMaskDropdown.checkedItems()
