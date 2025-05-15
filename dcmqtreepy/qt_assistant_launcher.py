import logging
import os
import sys
from typing import Callable, Optional

from PySide6.QtCore import QObject, QProcess
from PySide6.QtWidgets import QMessageBox

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class HelpAssistant(QObject):
    # Platform-specific assistant executable path candidates
    _PLATFORM_CANDIDATES: dict[str, list[Callable[["HelpAssistant"], str]]] = {
        "darwin": [
            # Packaged first
            lambda self: os.path.join(getattr(sys, "_MEIPASS", ""), "assistant"),
            # App bundle Resources (PyInstaller macOS .app)
            lambda self: os.path.normpath(os.path.join(os.path.dirname(sys.executable), "..", "Resources", "assistant")),
            # Homebrew / QtKit installs
            lambda self: "/opt/homebrew/bin/assistant",
            lambda self: "/usr/local/bin/assistant",
            lambda self: "/Applications/Qt/Tools/QtAssistant.app/Contents/MacOS/QtAssistant",
            # Fallback to PATH
            lambda self: "assistant",
        ],
        "win": [
            lambda self: os.path.join(getattr(sys, "_MEIPASS", ""), "assistant.exe"),
            lambda self: "assistant.exe",
        ],
        "linux": [
            lambda self: os.path.join(getattr(sys, "_MEIPASS", ""), "assistant"),
            lambda self: "assistant",
        ],
    }

    # Help topic to HTML file mapping
    _TOPIC_SUFFIX: dict[str, str] = {
        "dicom": "index.html",
        "file_operations": "file-operations-help.html",
        "add_element": "editing-elements-help.html",
        "delete_element": "editing-elements-help.html",
        "add_private_element": "private-elements-help.html",
        "dicom_tree": "interface-help.html",
        "file_list": "interface-help.html",
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.assistant_process: Optional[QProcess] = None
        self.help_collection: Optional[str] = None  # Path to .qhc file

    def _platform_key(self) -> str:
        """
        Determine the platform key for candidate selection.

        Returns:
            str: Platform identifier ("darwin", "win", or "linux")
        """
        if sys.platform == "darwin":
            return "darwin"
        return "win" if sys.platform.startswith("win") else "linux"

    def _find_assistant_executable(self) -> str:
        """
        Find the appropriate assistant executable for the current platform.

        Returns:
            str: Path to the assistant executable
        """
        platform_key = self._platform_key()
        for candidate_fn in self._PLATFORM_CANDIDATES[platform_key]:
            path = candidate_fn(self)
            logger.debug(f"Trying Assistant candidate: {path}")
            if os.path.exists(path) or path in ("assistant", "assistant.exe"):
                logger.info(f"Found Assistant at: {path}")
                return path

        # As a last resort, use the default fallback
        fallback = self._PLATFORM_CANDIDATES[platform_key][-1](self)
        logger.warning(f"No Assistant found in common locations, falling back to: {fallback}")
        return fallback

    def setup_assistant(self, collection_file: str) -> None:
        """
        Initialize the Qt Assistant with the specified help collection file.

        Args:
            collection_file (str): Path to the .qhc help collection file
        """
        self.help_collection = collection_file
        if not os.path.exists(collection_file):
            raise FileNotFoundError(f"Help collection file not found: {collection_file}")

    def launch_assistant(self) -> bool:
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
            return self._find_and_start_assistant()
        except Exception as e:
            logger.error(f"Error launching Qt Assistant: {str(e)}")
            QMessageBox.critical(None, "Error", f"Error launching Qt Assistant: {str(e)}")
            return False

    def _show_error_message(self, message: str, details: str) -> bool:
        """
        Show an error message and log the error.

        Args:
            message (str): Error message prefix
            details (str): Error details

        Returns:
            bool: Always returns False to indicate failure
        """
        full_message = f"{message}{details}"
        logger.error(full_message)
        QMessageBox.critical(None, "Error", full_message)
        return False

    def _find_and_start_assistant(self) -> bool:
        """
        Find and start the Qt Assistant process.

        Returns:
            bool: True if successful, False otherwise
        """
        self.assistant_process = QProcess()

        # Set up process to capture output
        self.assistant_process.readyReadStandardOutput.connect(self.handle_assistant_stdout)
        self.assistant_process.readyReadStandardError.connect(self.handle_assistant_stderr)

        # Get absolute path to the help collection file for PyInstaller compatibility
        help_collection_path = self.help_collection
        if hasattr(sys, "_MEIPASS") and not os.path.isabs(self.help_collection or ""):
            help_collection_path = os.path.join(sys._MEIPASS, self.help_collection or "")

        if not os.path.exists(help_collection_path or ""):
            return self._show_error_message("Help collection file not found: ", str(help_collection_path))

        # Find the appropriate assistant executable
        assistant_path = self._find_assistant_executable()
        logger.info(f"Using Qt Assistant at: {assistant_path}")

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
            return self._show_error_message("Assistant path not found.", " Help system unavailable.")

        logger.debug(f"Starting Assistant: {assistant_path} with args: {args}")
        self.assistant_process.start(assistant_path, args)

        # Wait for the process to start and check for errors
        if not self.assistant_process.waitForStarted(5000):  # 5 second timeout
            error = self.assistant_process.errorString()
            return self._show_error_message("Failed to start Qt Assistant: ", error)

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
            if stderr_data := self.assistant_process.readAllStandardError():
                error_text = bytes(stderr_data).decode("utf-8", errors="replace")
                logger.error(f"Assistant stderr: {error_text}")
                QMessageBox.critical(None, "Error", f"QtAssistant failed to start properly. Error: {error_text}")
            return False

        # Try to activate the window
        self.activate_assistant_window()

        logger.info("Qt Assistant started successfully")
        return True

    def show_help_topic(self, help_id: str) -> None:
        """
        Display a specific help topic in Qt Assistant.

        Args:
            help_id (str): The help identifier or URL to display
        """
        if not self.launch_assistant():
            return

        # Format commands based on help_id
        try:
            # Always send activateIdentifier first
            commands = [f"activateIdentifier {help_id}"]

            # Then fallback to a URL
            suffix = self._TOPIC_SUFFIX.get(help_id, f"{help_id}.html")
            commands.append(f"setSource qthelp://dcmqtreepy/doc/{suffix}")

            # Send all commands
            for cmd in commands:
                self.assistant_process.write(f"{cmd}\n".encode())

            # Also try activating the window again
            self.activate_assistant_window()

            logger.debug(f"Sent help navigation commands for topic: {help_id}")
        except Exception as e:
            QMessageBox.warning(None, "Warning", f"Failed to navigate to help topic: {str(e)}")

    def handle_assistant_stdout(self) -> None:
        """Handle standard output from the assistant process"""
        data = self.assistant_process.readAllStandardOutput()
        output = bytes(data).decode("utf-8", errors="replace")
        if output.strip():  # Only log if there's actual content
            logger.debug(f"Assistant stdout: {output.strip()}")

    def handle_assistant_stderr(self) -> None:
        """Handle standard error from the assistant process"""
        data = self.assistant_process.readAllStandardError()
        output = bytes(data).decode("utf-8", errors="replace")
        if output.strip():  # Only log if there's actual content
            logger.warning(f"Assistant stderr: {output.strip()}")

    def activate_assistant_window(self) -> None:
        """Attempt to activate the assistant window"""
        if not self.assistant_process or self.assistant_process.state() != QProcess.ProcessState.Running:
            return
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
                        logger.warning(f"Failed to activate Assistant window using AppleScript: {str(e2)}")
                        try:
                            subprocess.run(
                                [
                                    "osascript",
                                    "-e",
                                    'tell application "System Events" '
                                    'to set front-most of every process whose name contains "assistant" to true',
                                ],
                                capture_output=True,
                                text=True,
                            )
                        except Exception as e3:
                            logger.warning(f"All attempts to activate Assistant window failed: {str(e3)}")

            logger.debug("Sent window activation commands to Assistant")
        except Exception as e:
            logger.warning(f"Failed to activate Assistant window: {str(e)}")

    def cleanup(self) -> None:
        """
        Clean up the assistant process when the application closes.
        Must be called explicitly, typically in the application's closeEvent handler.
        """
        if self.assistant_process is None:
            return

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
