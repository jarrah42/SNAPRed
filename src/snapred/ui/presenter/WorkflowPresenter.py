from os import path

from qtpy.QtWidgets import QMainWindow, QMessageBox

from snapred.backend.api.InterfaceController import InterfaceController
from snapred.backend.dao import SNAPRequest
from snapred.backend.dao.request import ClearWorkspaceRequest
from snapred.backend.dao.SNAPResponse import ResponseCode
from snapred.backend.error.RecoverableException import RecoverableException
from snapred.backend.log.logger import snapredLogger
from snapred.ui.model.WorkflowNodeModel import WorkflowNodeModel
from snapred.ui.threading.worker_pool import WorkerPool
from snapred.ui.view.WorkflowView import WorkflowView
from snapred.ui.widget.ActionPrompt import ActionPrompt

logger = snapredLogger.getLogger(__name__)


class WorkflowPresenter(object):
    worker_pool = WorkerPool()

    def __init__(self, model: WorkflowNodeModel, cancelLambda=None, iterateLambda=None, parent=None):
        self.view = WorkflowView(model, parent)
        self._iteration = 1
        self.model = model
        self._cancelLambda = cancelLambda
        self._iterateLambda = iterateLambda
        self.resetLambda = self.resetAndClear
        self._hookupSignals()

    @property
    def widget(self):
        return self.view

    @property
    def nextView(self):
        return self.view.nextTabView

    def show(self):
        # wrap view in QApplication
        self.window = QMainWindow(self.view.parent())
        self.window.setCentralWidget(self.view)
        self.window.show()

    def resetSoft(self):
        self.widget.reset(hard=False)

    def clearWorkspacesRequest(self):
        interfaceController = InterfaceController()
        clearWorkspacesRequest = ClearWorkspaceRequest(cache=True, exclude=[])
        snapRequest = SNAPRequest(path="workspace/clear", payload=clearWorkspacesRequest.json())
        interfaceController.executeRequest(snapRequest)

    def resetHard(self):
        self.widget.reset(hard=True)

    def resetAndClear(self):
        self.resetSoft()
        self.clearWorkspacesRequest()
        self._iteration = 1

    def cancel(self):
        ActionPrompt(
            "Are you sure?",
            "Are you sure you want to cancel the workflow? This will clear all workspaces.",
            self.resetAndClear,
            self.view,
        )

    def iterate(self):
        self._iteration += 1
        self.resetSoft()

    @property
    def iteration(self):
        return self._iteration

    def _hookupSignals(self):
        for i, model in enumerate(self.model):
            widget = self.view.tabWidget.widget(i)
            logger.debug(
                f"Hooking up signals for tab {widget.view} to {widget.model.continueAction} \
                    to continue button {widget.continueButton}"
            )
            if not model.required:
                widget.onSkipButtonClicked(self.handleSkipButtonClicked)
                widget.enableSkip()

            if model.iterate:
                widget.onIterateButtonClicked(self.handleIterateButtonClicked)
                widget.enableIterate()

            widget.onContinueButtonClicked(self.handleContinueButtonClicked)

            if self._cancelLambda:
                widget.onCancelButtonClicked(self._cancelLambda)
            else:
                widget.onCancelButtonClicked(self.cancel)

    def handleIterateButtonClicked(self):
        self._iterateLambda(self)
        self.iterate()

    def handleSkipButtonClicked(self):
        self.advanceWorkflow()

    def advanceWorkflow(self):
        if self.view.currentTab >= self.view.totalNodes - 1:
            ActionPrompt(
                "‧₊Workflow Complete‧₊",
                "‧₊‧₊The workflow has been completed successfully!‧₊‧₊",
                lambda: None,
                self.view,
            )
            self.resetLambda()
        else:
            self.view.advanceWorkflow()

    def setResetLambda(self, resetLambda):
        self.resetLambda = resetLambda

    def handleContinueButtonClicked(self, model):
        self.view.continueButton.setEnabled(False)
        self.view.cancelButton.setEnabled(False)
        self.view.skipButton.setEnabled(False)
        # do action
        self.worker = self.worker_pool.createWorker(target=model.continueAction, args=(self))
        self.worker.finished.connect(lambda: self.view.continueButton.setEnabled(True))
        self.worker.finished.connect(lambda: self.view.cancelButton.setEnabled(True))
        self.worker.finished.connect(lambda: self.view.skipButton.setEnabled(True))
        self.worker.result.connect(self._handleComplications)
        self.worker.success.connect(lambda success: self.advanceWorkflow() if success else None)

        self.worker_pool.submitWorker(self.worker)

    def _isErrorCode(self, code):
        return code >= ResponseCode.ERROR

    def _isRecoverableError(self, code):
        return ResponseCode.RECOVERABLE <= code < ResponseCode.ERROR

    def _handleComplications(self, result):
        if self._isErrorCode(result.code):
            QMessageBox.critical(
                self.view,
                "Error",
                f"Error {result.code}: {result.message}",
                QMessageBox.Ok,
                QMessageBox.Ok,
            )
        elif self._isRecoverableError(result.code):
            if "state" in result.message:
                self.handleStateMessage(self.view)
            else:
                logger.error(f"Unhandled scenario triggered by state message: {result.message}")
                messageBox = QMessageBox(
                    QMessageBox.Warning,
                    "Warning",
                    "Proccess completed successfully with warnings!",
                    QMessageBox.Ok,
                    self.view,
                )
                messageBox.setDetailedText(f"{result.message}")
                messageBox.exec()
        elif result.message:
            messageBox = QMessageBox(
                QMessageBox.Warning,
                "Warning",
                "Proccess completed successfully with warnings!",
                QMessageBox.Ok,
                self.view,
            )
            messageBox.setDetailedText(f"{result.message}")
            messageBox.exec()

    def handleStateMessage(self, view):
        """
        Handles a specific 'state' message.
        """
        from snapred.backend.dao.request.InitializeStateHandler import InitializeStateHandler
        from snapred.ui.view.InitializeStateCheckView import InitializationMenu

        try:
            logger.info("Handling 'state' message.")
            initializationMenu = InitializationMenu(runNumber=InitializeStateHandler.runId, parent=view)
            initializationMenu.finished.connect(lambda: initializationMenu.deleteLater())
            initializationMenu.show()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"The 'state' handling method encountered an error:{str(e)}")
