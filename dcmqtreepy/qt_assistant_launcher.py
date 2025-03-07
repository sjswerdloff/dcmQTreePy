import logging
import os
import sys

from PySide6.QtCore import QObject, QProcess
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMessageBox

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class HelpAssistant(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant_process = None
        self.help_collection = None  # Path to .qhc file

    def setup_assistant(self, collection_file):
        """
        Initialize the Qt Assistant with the specified help collection file.

        Args:
            collection_file (str): Path to the .qhc help collection file
        """
        self.help_collection = collection_file
        if not os.path.exists(collection_file):
            raise FileNotFoundError(f"Help collection file not found: {collection_file}")

    def launch_assistant(self):
        """
        Launch Qt Assistant if it's not already running.
        Returns True if successful, False otherwise.
        """
        if self.assistant_process is not None:
            if self.assistant_process.state() == QProcess.ProcessState.Running:
                return True
            else:
                self.assistant_process = None

        try:
            self.assistant_process = QProcess()

            # Determine the assistant executable path based on platform
            if sys.platform == "darwin":
                # Check common MacOS locations
                possible_paths = [
                    "/opt/homebrew/bin/assistant",  # Homebrew installation
                    "/usr/local/bin/assistant",  # Alternative Homebrew location
                    "/Applications/Qt/Tools/QtAssistant.app/Contents/MacOS/QtAssistant",  # Qt installation
                    # PySide6-specific locations
                    os.path.join(os.path.dirname(sys.executable), "assistant"),
                ]
                for path in possible_paths:
                    logger.debug(f"Checking for Assistant at: {path}")
                    if os.path.exists(path):
                        logger.info(f"Found Assistant at: {path}")
                        assistant_path = path
                        break
                else:
                    logger.warning("No Assistant found in common locations, falling back to 'assistant' command")
                    assistant_path = "assistant"
            elif sys.platform.startswith("win"):  # Handles both win32 and win64
                assistant_path = "assistant.exe"
                logger.debug(f"Windows platform detected, using: {assistant_path}")
            else:  # Linux and others
                assistant_path = "assistant"
                logger.debug(f"Unix-like platform detected, using: {assistant_path}")

            args = ["-collectionFile", self.help_collection, "-enableRemoteControl"]

            # Start the Assistant process
            self.assistant_process.start(assistant_path, args)

            # Wait for the process to start
            if not self.assistant_process.waitForStarted(5000):  # 5 second timeout
                QMessageBox.critical(None, "Error", "Failed to start Qt Assistant. Please ensure it is properly installed.")
                return False

            return True

        except Exception as e:
            QMessageBox.critical(None, "Error", f"Error launching Qt Assistant: {str(e)}")
            return False

    def show_help_topic(self, help_id):
        """
        Display a specific help topic in Qt Assistant.

        Args:
            help_id (str): The help identifier or URL to display
        """
        if not self.launch_assistant():
            return

        # Activate the window and show the specific topic
        args = ["activateIdentifier", help_id]

        try:
            self.assistant_process.write((" ".join(args) + "\n").encode())
        except Exception as e:
            QMessageBox.warning(None, "Warning", f"Failed to navigate to help topic: {str(e)}")

    def cleanup(self):
        """
        Clean up the assistant process when the application closes.
        Must be called explicitly, typically in the application's closeEvent handler.
        """
        if self.assistant_process is not None:
            logger.debug("Cleaning up Assistant process...")
            self.assistant_process.terminate()
            if self.assistant_process.waitForFinished(3000):  # Wait up to 3 seconds
                logger.info("Assistant process terminated normally")
            else:
                logger.warning("Assistant process did not terminate, forcing kill")
                self.assistant_process.kill()  # Force quit if still running
                self.assistant_process.waitForFinished(1000)  # Give it a second to die

            if self.assistant_process.state() == QProcess.ProcessState.NotRunning:
                logger.info("Assistant process cleanup completed")
            else:
                logger.error("Failed to clean up Assistant process")


# Example usage:
"""
import atexit

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLineEdit, QApplication
from PySide6.QtCore import QUrl
from PySide6.QtGui import QShortcut, QKeySequence

class ExampleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()

        # Create a button with associated help
        save_button = QPushButton("Save")
        # Help ID can be a registered help tag or a URL to specific documentation
        save_button.setProperty('help_id', 'save-operation')  # Tag in .qhp file
        # Alternative: Direct URL to documentation
        # save_button.setProperty('help_id', 'qthelp://yournamespace/doc/path/to/save-operation.html')
        layout.addWidget(save_button)

        # Create a text field with different help context
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter name")
        name_input.setProperty('help_id', 'name-input-rules')
        layout.addWidget(name_input)

        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.help_assistant = HelpAssistant(self)
        self.help_assistant.setup_assistant('path/to/your.qhc')

        # Register cleanup with atexit
        atexit.register(self.help_assistant.cleanup)

        # Connect F1 key to context-sensitive help
        self.f1_shortcut = QShortcut(QKeySequence("F1"), self)
        self.f1_shortcut.activated.connect(self.show_context_help)

        # Add Command-? shortcut for macOS
        if sys.platform == 'darwin':
            # On macOS, Qt automatically converts Meta (Command) to Control
            self.help_shortcut = QShortcut(QKeySequence("Ctrl+?"), self)
            self.help_shortcut.activated.connect(self.show_context_help)
            logger.debug("Added macOS Command-? help shortcut")

        # Set up the central widget
        self.setCentralWidget(ExampleWidget())

    def show_context_help(self):
        # Determine the current context and show appropriate help
        current_widget = QApplication.focusWidget()
        if current_widget:
            help_id = current_widget.property('help_id')
            if help_id:
                logger.debug(f"Showing help for widget: {current_widget.__class__.__name__}, help_id: {help_id}")
                self.help_assistant.show_help_topic(help_id)
            else:
                logger.debug(f"No help_id found for widget: {current_widget.__class__.__name__}")
                # Fall back to general help if no specific help is defined
                self.help_assistant.show_help_topic('general-help')
        else:
            logger.debug("No widget currently has focus")
            self.help_assistant.show_help_topic('general-help')

    def closeEvent(self, event):
        self.help_assistant.cleanup()
        super().closeEvent(event)
"""
