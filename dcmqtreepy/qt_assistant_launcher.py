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
                # Try to activate the window if it's already running
                self.activate_assistant_window()
                return True
            else:
                self.assistant_process = None

        try:
            self.assistant_process = QProcess()

            # Set up process to capture output
            self.assistant_process.readyReadStandardOutput.connect(self.handle_assistant_stdout)
            self.assistant_process.readyReadStandardError.connect(self.handle_assistant_stderr)

            # Get absolute path to the help collection file for PyInstaller compatibility
            help_collection_path = self.help_collection
            if hasattr(sys, "_MEIPASS"):
                # If inside PyInstaller bundle, ensure we have an absolute path from the bundle
                if not os.path.isabs(self.help_collection):
                    help_collection_path = os.path.join(sys._MEIPASS, self.help_collection)

            if not os.path.exists(help_collection_path):
                logger.error(f"Help collection file not found: {help_collection_path}")
                QMessageBox.critical(None, "Error", f"Help collection file not found: {help_collection_path}")
                return False

            assistant_path = None
            # Determine the assistant executable path based on platform
            if sys.platform == "darwin":
                try:
                    # First check if we're running from a PyInstaller package
                    base_path = sys._MEIPASS
                    assistant_path = os.path.join(base_path, "assistant")
                    if os.path.exists(assistant_path):
                        logger.info(f"Using bundled Assistant at: {assistant_path}")
                    else:
                        # If we're in PyInstaller but assistant isn't in the base directory,
                        # check if it's in the app bundle
                        if getattr(sys, "frozen", False):
                            # Check in the app bundle Resources
                            bundle_path = os.path.normpath(os.path.join(os.path.dirname(sys.executable), "..", "Resources"))
                            possible_assistant = os.path.join(bundle_path, "assistant")
                            if os.path.exists(possible_assistant):
                                assistant_path = possible_assistant
                                logger.info(f"Found Assistant in app bundle: {assistant_path}")

                        # If still not found, fall back to system paths
                        if assistant_path is None or not os.path.exists(assistant_path):
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
                except Exception as e:
                    logger.warning(f"Error while looking for bundled Assistant: {str(e)}")
                    # Fall back to the existing system path search logic
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
                        logger.debug(f"Using system Assistant: {assistant_path}")
            elif sys.platform.startswith("win"):
                try:
                    # First check if we're running from a PyInstaller package
                    base_path = sys._MEIPASS
                    assistant_path = os.path.join(base_path, "assistant.exe")
                    if os.path.exists(assistant_path):
                        logger.info(f"Using bundled Assistant at: {assistant_path}")
                    else:  # Handles both win32 and win64
                        assistant_path = "assistant.exe"
                        logger.info(f"Using system Assistant: {assistant_path}")
                except Exception:
                    assistant_path = "assistant.exe"
                logger.debug(f"Windows platform detected, using: {assistant_path}")
            else:  # Linux and others
                try:
                    # Check for PyInstaller bundle first
                    base_path = sys._MEIPASS
                    assistant_path = os.path.join(base_path, "assistant")
                    if os.path.exists(assistant_path):
                        logger.info(f"Using bundled Assistant at: {assistant_path}")
                    else:
                        assistant_path = "assistant"
                except Exception:
                    assistant_path = "assistant"
                logger.debug(f"Unix-like platform detected, using: {assistant_path}")

            # Force show window (these are the key parameters that ensure the window appears)
            args = [
                "-collectionFile",
                help_collection_path,
                "-enableRemoteControl",
                "-show",
                "contents",  # Show contents widget
            ]

            # Set working directory to PyInstaller directory if applicable
            if hasattr(sys, "_MEIPASS"):
                self.assistant_process.setWorkingDirectory(sys._MEIPASS)
                logger.debug(f"Setting working directory to: {sys._MEIPASS}")

            # Set environment variables to help with window visibility
            env = self.assistant_process.processEnvironment()
            if sys.platform == "darwin":
                # These can help with macOS visibility issues
                env.insert("QT_MAC_WANTS_LAYER", "1")
                env.insert("QT_DEBUG_PLUGINS", "1")  # Helps with debugging
            self.assistant_process.setProcessEnvironment(env)

            # Start the Assistant process
            if assistant_path is None:
                logger.error("Assistant path not found, unable to provide QtAssistant based help")
                QMessageBox.critical(None, "Error", "Assistant path not found. Help system unavailable.")
                return False
            else:
                logger.debug(f"Starting Assistant: {assistant_path} with args: {args}")
                self.assistant_process.start(assistant_path, args)

            # Wait for the process to start and check for errors
            if not self.assistant_process.waitForStarted(5000):  # 5 second timeout
                error = self.assistant_process.errorString()
                logger.error(f"Failed to start Qt Assistant: {error}")
                QMessageBox.critical(None, "Error", f"Failed to start Qt Assistant: {error}")
                return False

            # Check if process immediately terminated with error
            if self.assistant_process.state() == QProcess.ProcessState.NotRunning:
                exit_code = self.assistant_process.exitCode()
                error = self.assistant_process.errorString()
                logger.error(f"Assistant exited immediately with code {exit_code}: {error}")
                QMessageBox.critical(
                    None, "Error", f"Qt Assistant started but exited immediately with code {exit_code}. Error: {error}"
                )
                return False

            # Wait a moment for the window to appear
            import time

            time.sleep(1)  # Give the process a moment to initialize

            # Check process again to make sure it's still running
            if self.assistant_process.state() != QProcess.ProcessState.Running:
                logger.error("Assistant process is not running after initialization")
                # Try to check if there was any error output
                stderr_data = self.assistant_process.readAllStandardError()
                if stderr_data:
                    error_text = bytes(stderr_data).decode("utf-8", errors="replace")
                    logger.error(f"Assistant stderr: {error_text}")
                    QMessageBox.critical(None, "Error", f"QtAssistant failed to start properly. Error: {error_text}")
                return False

            # Try to activate the window
            self.activate_assistant_window()

            logger.info("Qt Assistant started successfully")
            return True

        except Exception as e:
            logger.error(f"Error launching Qt Assistant: {str(e)}")
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

        # Format the help identifier correctly
        # Try multiple approaches to activate the correct page
        try:
            # Try to activate by identifier first
            self.assistant_process.write(f"activateIdentifier {help_id}\n".encode())

            # Also try with the full URL format
            self.assistant_process.write(f"setSource qthelp://dcmqtreepy/doc/{help_id}.html\n".encode())

            # Try direct file access if the above fails
            if help_id == "dicom":
                self.assistant_process.write("setSource qthelp://dcmqtreepy/doc/index.html\n".encode())
            elif help_id == "file_operations":
                self.assistant_process.write("setSource qthelp://dcmqtreepy/doc/file-operations-help.html\n".encode())
            elif help_id == "add_element" or help_id == "delete_element":
                self.assistant_process.write("setSource qthelp://dcmqtreepy/doc/editing-elements-help.html\n".encode())
            elif help_id == "add_private_element":
                self.assistant_process.write("setSource qthelp://dcmqtreepy/doc/private-elements-help.html\n".encode())
            elif help_id == "dicom_tree" or help_id == "file_list":
                self.assistant_process.write("setSource qthelp://dcmqtreepy/doc/interface-help.html\n".encode())

            # Also try activating the window again
            self.activate_assistant_window()

            logger.debug(f"Sent help navigation commands for topic: {help_id}")
        except Exception as e:
            QMessageBox.warning(None, "Warning", f"Failed to navigate to help topic: {str(e)}")

    def handle_assistant_stdout(self):
        """Handle standard output from the assistant process"""
        data = self.assistant_process.readAllStandardOutput()
        output = bytes(data).decode("utf-8", errors="replace")
        if output.strip():  # Only log if there's actual content
            logger.debug(f"Assistant stdout: {output.strip()}")

    def handle_assistant_stderr(self):
        """Handle standard error from the assistant process"""
        data = self.assistant_process.readAllStandardError()
        output = bytes(data).decode("utf-8", errors="replace")
        if output.strip():  # Only log if there's actual content
            logger.warning(f"Assistant stderr: {output.strip()}")

    def activate_assistant_window(self):
        """Attempt to activate the assistant window"""
        if self.assistant_process and self.assistant_process.state() == QProcess.ProcessState.Running:
            # Try to bring the window to the front
            try:
                if sys.platform == "darwin":
                    # On macOS, try to use AppleScript to activate the window
                    import subprocess

                    try:
                        # Try both app names that might be used
                        subprocess.run(
                            ["osascript", "-e", 'tell application "QtAssistant" to activate'], capture_output=True, text=True
                        )
                    except Exception:
                        try:
                            subprocess.run(
                                ["osascript", "-e", 'tell application "Assistant" to activate'], capture_output=True, text=True
                            )
                        except Exception as e2:
                            # If both fail, try to find the process
                            try:
                                subprocess.run(
                                    [
                                        "osascript",
                                        "-e",
                                        f'tell application "System Events" to set frontmost of every process whose name contains "assistant" to true',
                                    ],
                                    capture_output=True,
                                    text=True,
                                )
                            except Exception as e3:
                                logger.warning(f"All attempts to activate Assistant window failed: {str(e3)}")

                logger.debug("Sent window activation commands to Assistant")
            except Exception as e:
                logger.warning(f"Failed to activate Assistant window: {str(e)}")

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
