import asyncio
import json
import os
import subprocess
import tempfile
import time
import uuid
from typing import Tuple
from rymflux.core.logging import get_logger

logger = get_logger(__name__)

class CLIPlayer:
    def __init__(self):
        self.mpv_process = None
        # Use a unique, non-precreated socket path
        self.socket_path = f"/tmp/rymflux-mpv-{uuid.uuid4().hex}.sock"
        self.is_playing = False
        self.volume = 50
        self.position = 0.0
        self.duration = 0.0
        self.paused = False
        # Ensure socket path does not exist
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

    def _send_command(self, command: list) -> None:
        """Sends a command to the mpv socket."""
        try:
            with open(self.socket_path, "w") as sock:
                sock.write(json.dumps({"command": command}) + "\n")
        except (OSError, IOError) as e:
            logger.error(f"Error sending command to mpv: {e}")

    def start(self, initial_url: str, title: str):
        """Starts the mpv process in the background."""
        if self.mpv_process and self.mpv_process.poll() is None:
            self.load_file(initial_url, title)
            return

        try:
            observe_pos = {"command": ["observe_property", 1, "time-pos"]}
            observe_duration = {"command": ["observe_property", 2, "duration"]}
            observe_pause = {"command": ["observe_property", 3, "pause"]}
            observe_volume = {"command": ["observe_property", 4, "volume"]}

            command = [
                "mpv",
                initial_url,
                "--no-video",
                f"--input-ipc-server={self.socket_path}",
                f"--title={title}",
                "--idle=yes",
                "--no-terminal",
                f"--volume={self.volume}",
                "--script-opts=osc-visibility=always",
                "--config-dir=/dev/null",
                "--input-conf=/dev/null"
            ]
            self.mpv_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Wait for MPV to initialize and create the socket
            time.sleep(0.5)
            waited = 0.0
            while self.mpv_process.poll() is None and not os.path.exists(self.socket_path):
                time.sleep(0.1)
                waited += 0.1
                if waited > 5.0:
                    raise RuntimeError(f"MPV socket not created after 5 seconds at {self.socket_path}. Check if mpv is installed and working.")
            if not os.path.exists(self.socket_path):
                raise RuntimeError(f"MPV socket not created at {self.socket_path}. Check if mpv is installed and working.")

            self._send_command(observe_pos["command"])
            self._send_command(observe_duration["command"])
            self._send_command(observe_pause["command"])
            self._send_command(observe_volume["command"])
            
            self.is_playing = True
            asyncio.create_task(self._read_socket())
        except FileNotFoundError:
            logger.error("MPV command not found")
            print("\n[bold red]Error: 'mpv' command not found.[/bold red]")
            print("Please ensure mpv is installed and in your system's PATH.")
            self.mpv_process = None
        except Exception as e:
            logger.error(f"Error starting MPV: {e}")
            print(f"\n[bold red]Error starting MPV: {e}[/bold red]")
            print(f"Socket path attempted: {self.socket_path}")
            self.mpv_process = None

    def stop(self):
        """Stops the mpv process and cleans up."""
        if self.mpv_process and self.mpv_process.poll() is None:
            self.mpv_process.terminate()
            try:
                self.mpv_process.wait(timeout=5)
                if os.path.exists(self.socket_path):
                    os.remove(self.socket_path)
            except Exception as e:
                logger.error(f"Error cleaning up MPV: {e}")
        self.mpv_process = None
        self.is_playing = False

    def play_pause(self):
        """Toggles play/pause state."""
        if self.mpv_process and self.mpv_process.poll() is None:
            self._send_command(["cycle", "pause"])
            self.paused = not self.paused

    def seek(self, seconds: int):
        """Seeks forward or backward by the given number of seconds."""
        if self.mpv_process and self.mpv_process.poll() is None:
            self._send_command(["seek", seconds])

    def load_file(self, url: str, title: str):
        """Loads a new file into the player."""
        if self.mpv_process and self.mpv_process.poll() is None:
            self._send_command(["loadfile", url])
            self._send_command(["set", "title", title])

    async def _read_socket(self):
        """Reads responses from the mpv socket asynchronously."""
        if not self.mpv_process or self.mpv_process.poll() is not None:
            return
        try:
            while self.mpv_process.poll() is None:
                with open(self.socket_path, "r") as sock:
                    line = sock.readline().strip()
                    if line:
                        data = json.loads(line)
                        if "event" in data:
                            if data["event"] == "property-change" and data["id"] == 1:
                                self.position = float(data.get("data", 0.0))
                            elif data["event"] == "property-change" and data["id"] == 2:
                                self.duration = float(data.get("data", 0.0))
                            elif data["event"] == "property-change" and data["id"] == 3:
                                self.paused = bool(data.get("data", False))
                            elif data["event"] == "property-change" and data["id"] == 4:
                                self.volume = int(data.get("data", 50))
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error reading socket: {e}")

    def set_volume(self, volume: int):
        """Sets the volume level."""
        if self.mpv_process and self.mpv_process.poll() is None:
            self.volume = max(0, min(100, volume))
            self._send_command(["set", "volume", self.volume])

    def get_playback_status(self) -> Tuple[float, float, bool, int]:
        """Returns the current playback status."""
        return (self.position, self.duration, self.paused, self.volume)