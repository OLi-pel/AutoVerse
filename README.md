# AutoVerse

![AutoVerse Logo](https://raw.githubusercontent.com/OLi-pel/AutoVerse/main/assets/logo.png?raw=true)

**AI-Powered Transcription and Speaker Diarization Desktop Application**

[![macOS Build](https://github.com/OLi-pel/AutoVerse/actions/workflows/macos-build.yml/badge.svg)](https://github.com/OLi-pel/AutoVerse/actions/workflows/macos-build.yml)
[![Windows Build](https://github.com/OLi-pel/AutoVerse/actions/workflows/windows-build.yml/badge.svg)](https://github.com/OLi-pel/AutoVerse/actions/workflows/windows-build.yml)
[![Latest Release](https://img.shields.io/github/v/release/OLi-pel/AutoVerse)](https://github.com/OLi-pel/AutoVerse/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AutoVerse is a cross-platform desktop application designed to provide high-quality transcription and speaker diarization (speaker identification) for your audio and video files. Built with Python and powered by state-of-the-art AI models, it offers a powerful post-processing editor to refine transcripts to perfection, all while running locally on your machine.

---

## Features

-   **High-Quality Transcription**: Utilizes OpenAI's **Whisper** models, allowing you to choose between speed and accuracy (from `tiny` to `large`).
-   **Speaker Diarization**: Integrates **Pyannote.audio** to automatically detect and label different speakers in your audio.
-   **Comprehensive Media Support**: Process both audio (`.mp3`, `.wav`, etc.) and video (`.mp4`, `.mov`, etc.) files seamlessly.
-   **Advanced Correction Editor**:
    -   **Synchronized Playback**: A visual waveform timeline that highlights the text segment being spoken.
    -   **Full Editing Control**: Edit text, re-assign speakers, and correct timestamps with ease.
    -   **Segment Manipulation**: Intuitively merge, split, and delete transcription segments.
    -   **Full Undo/Redo Support**: A robust undo/redo manager ensures a non-destructive editing workflow.
-   **Cross-Platform**: Natively built for both **Windows** and **macOS**.
-   **Auto-Updater**: The application can automatically check for, download, and install new updates.

## Installation

Download the latest version for your operating system from the [**Releases Page**](https://github.com/OLi-pel/AutoVerse/releases/latest).

### macOS

1.  Download the `AutoVerse-macOS-Installer.dmg` file.
2.  Open the DMG file. A window will appear.
3.  Drag the `AutoVerse.app` icon into the `Applications` folder icon.
4.  Launch AutoVerse from your Applications folder.

### Windows

1.  Download the `AutoVerse-Setup.exe` file.
2.  Run the installer and follow the on-screen instructions.
3.  Launch AutoVerse from the Start Menu or the desktop shortcut.

## Getting Started

1.  Launch AutoVerse. You will start on the **Transcription** tab.
2.  Click **Browse** to select one or more audio/video files.
3.  Choose your desired transcription **Model**. `large` is the most accurate.
4.  To identify speakers, check **Enable Speaker Diarization** and provide a Hugging Face 'read' token if prompted.
5.  Click **Start Processing**.
6.  When processing is complete for a single file, the **Head to correction tab** button will become enabled. Click it to begin editing.
7.  In the **Correction window**, use the timeline and editing tools to refine the transcript.
8.  Click **Save Changes** to export your final work.

## For Developers (Running from Source)

Interested in contributing or running the development version? Follow these steps.

**Prerequisites:**
-   [Python 3.11+](https://www.python.org/)
-   [Git](https://git-scm.com/)
-   **FFmpeg**:
    -   **macOS**: `brew install ffmpeg`
    -   **Windows**: Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add to your system's PATH.
-   **PortAudio** (for macOS only):
    -   `brew install portaudio`

**Setup:**

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/OLi-pel/AutoVerse.git
    cd AutoVerse
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    python main_pyside.py
    ```

## Technology Stack

-   **Application Framework**: Python 3 & PySide6 (Qt for Python)
-   **Transcription**: [openai-whisper](https://github.com/openai/whisper)
-   **Speaker Diarization**: [pyannote.audio](https://github.com/pyannote/pyannote-audio)
-   **Audio/Video Handling**: MoviePy, PyAudio, SoundFile
-   **Packaging**: PyInstaller
-   **Installers**: [create-dmg](https://github.com/create-dmg/create-dmg) for macOS, [Inno Setup](https://jrsoftware.org/isinfo.php) for Windows

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
