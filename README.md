# AutoVerse

![AutoVerse Logo](https://raw.githubusercontent.com/OLi-pel/AutoVerse/main/assets/logo.png?raw=true)

**AI-Powered Transcription and Speaker Diarization Desktop Application**

[![macOS Build](https://github.com/OLi-pel/AutoVerse/actions/workflows/macos-build.yml/badge.svg)](https://github.com/OLi-pel/AutoVerse/actions/workflows/macos-build.yml)
[![Windows Build](https://github.com/OLi-pel/AutoVerse/actions/workflows/windows-build.yml/badge.svg)](https://github.com/OLi-pel/AutoVerse/actions/workflows/windows-build.yml)
[![Latest Release](https://img.shields.io/github/v/release/OLi-pel/AutoVerse)](https://github.com/OLi-pel/AutoVerse/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AutoVerse is a cross-platform desktop application designed to provide high-quality transcription and speaker diarization (speaker identification) for your audio and video files. Built with Python and powered by state-of-the-art AI models, it features a modern step-by-step workflow, automatic updates, and a powerful post-processing editor to refine transcripts to perfection, all while running locally on your machine.

---

## Features

-   **High-Quality Transcription**: Utilizes OpenAI's **Whisper** models, allowing you to choose between speed and accuracy (from `tiny` to `large`).
-   **Speaker Diarization**: Integrates **Pyannote.audio** to automatically detect and label different speakers in your audio.
-   **Comprehensive Media Support**: Process both audio (`.mp3`, `.wav`, etc.) and video (`.mp4`, `.mov`, etc.) files seamlessly.
-   **Batch Processing**: Handle multiple audio/video files simultaneously for efficient workflow.
-   **Modern Step-by-Step Interface**: 
    -   **Step 1**: Select your audio/video files with drag-and-drop support
    -   **Step 2**: Configure processing options with collapsible, organized sections
    -   **Step 3**: Monitor processing and view results in real-time
-   **Welcome Wizard**: Choose between transcribing new files or editing existing transcripts on startup.
-   **Advanced Correction Editor**:
    -   **Synchronized Playback**: A visual waveform timeline that highlights the text segment being spoken.
    -   **Full Editing Control**: Edit text, re-assign speakers, and correct timestamps with ease.
    -   **Segment Manipulation**: Intuitively merge, split, and delete transcription segments.
    -   **Full Undo/Redo Support**: A robust undo/redo manager ensures a non-destructive editing workflow.
-   **Contextual Tips System**: Built-in help system with status bar tips for all interface elements.
-   **Cross-Platform**: Natively built for both **Windows** and **macOS**.
-   **Auto-Updater**: The application automatically checks for, downloads, and installs new updates from GitHub releases.

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

### First Launch
1.  Launch AutoVerse. A **Welcome Dialog** will appear asking what you'd like to do:
    -   **Transcribe a New Audio/Video File**: Start the transcription workflow
    -   **Edit an Existing Transcript**: Jump directly to the correction editor
2.  Check "Don't show this again" if you prefer to skip this dialog in future launches.

### Transcription Workflow
The main interface uses a modern **3-step workflow**:

**Step 1: Select Audio/Video File(s)**
1.  Click **Browse** or drag-and-drop to select one or more audio/video files.
2.  Multiple files will be processed in batch automatically.

**Step 2: Configure Processing Options**
1.  Choose your desired transcription **Model** (`large` is most accurate).
2.  **Speaker Options**: Check **Enable Speaker Diarization** to identify different speakers.
    -   If prompted, provide a Hugging Face 'read' token (one-time setup).
    -   Advanced options like **Auto-merge** are available in collapsible sections.
3.  **Timestamp Options**: Configure timestamp inclusion and formatting.
4.  Click **Continue to Processing** when ready.

**Step 3: Start Processing & View Output**
1.  Click **Start Processing** to begin transcription.
2.  Monitor real-time progress with detailed status updates.
3.  For single files, the **Head to correction tab** button becomes available when complete.

### Editing Transcripts
1.  In the **Correction tab**, load your transcript and audio files.
2.  Use the visual waveform timeline for synchronized playback and editing.
3.  Edit text, reassign speakers, adjust timestamps, and manipulate segments.
4.  The built-in tips system provides contextual help for all tools.
5.  Click **Save Changes** to export your refined transcript.

### Tips and Help System
AutoVerse includes a comprehensive contextual help system:
-   **Toggle Tips**: Use the help icon (❓) in the top-left to enable/disable status bar tips.
-   **Contextual Help**: Hover over any interface element to see helpful tips in the status bar.
-   **Workflow Guidance**: Each step provides summary text to guide you through the process.

## Using Speaker Diarization

The speaker diarization feature relies on powerful models from Hugging Face and requires a free user access token to function. This ensures you have agreed to the terms of use for the models.

Follow these one-time setup steps to enable this feature:

1.  **Create a Hugging Face Account**
    If you don't have one, [create a free account](https://huggingface.co/join) or [log in](https://huggingface.co/login) to your existing account.

2.  **Accept Model User Agreements**
    The diarization pipeline uses two main models. You must accept the user conditions for both. Visit each link below, read the terms, and click the **"Agree and access repository"** button.
    -   **Segmentation Model:** [huggingface.co/pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
    -   **Diarization Pipeline:** [huggingface.co/pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
    *(You must be logged in to accept the terms).*

3.  **Generate a "Read-Only" Access Token**
    -   Navigate to your [Hugging Face Access Tokens settings](https://huggingface.co/settings/tokens).
    -   Click the **"New token"** button.
    -   Give the token a descriptive **Name** (e.g., `AutoVerseApp`).
    -   Select the **`read`** role. This is the most secure option that will still allow the app to download the models.
    -   Click **"Generate a token"**.

4.  **Copy and Use the Token in AutoVerse**
    -   Your new token will be displayed (it will look like `hf_...`). Click the copy icon next to it.
    -   In AutoVerse, check the **"Enable Speaker Diarization"** box. The token input area will appear.
    -   Paste your token into the field and click the **Save** button. The token will now be saved securely on your machine for all future sessions.

---

## Auto-Updates

AutoVerse includes a built-in auto-update system that keeps your application current with the latest features and bug fixes.

### How It Works
-   **Automatic Checking**: The app checks for updates from the GitHub releases when launched (frozen builds only).
-   **User Control**: You're always prompted before downloading and installing updates.
-   **Seamless Installation**: Updates download in the background and install automatically.
-   **Platform-Specific**: Handles macOS `.app` bundles and Windows executables correctly.

### Update Process
1.  When an update is available, you'll see a notification with release notes.
2.  Choose "Yes" to download and install, or "No" to skip.
3.  The app downloads the update and handles installation automatically.
4.  AutoVerse will restart with the new version.

### Manual Updates
If you prefer manual updates or encounter issues:
1.  Visit the [Releases Page](https://github.com/OLi-pel/AutoVerse/releases/latest)
2.  Download the appropriate installer for your platform
3.  Install following the standard installation process

---

### Why is a Token Required?

An access token acts as a key that proves to Hugging Face that you are an authenticated user who has accepted the license and terms of use for their pre-trained models. This allows the application to download the necessary files on your behalf.

> **Important Security Note**
> Your Hugging Face access token is a personal secret and should be treated like a password. Do not share it publicly or commit it to version control. It identifies your activity to Hugging Face.

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

-   **Application Framework**: Python 3.11+ & PySide6 (Qt6 for Python)
-   **Transcription**: [openai-whisper](https://github.com/openai/whisper)
-   **Speaker Diarization**: [pyannote.audio](https://github.com/pyannote/pyannote-audio)
-   **Audio/Video Handling**: MoviePy, PyAudio, SoundFile, TorchAudio
-   **UI Components**: Custom collapsible widgets, waveform visualization
-   **Auto-Updates**: GitHub Releases API integration
-   **Packaging**: PyInstaller with custom hooks
-   **Installers**: [create-dmg](https://github.com/create-dmg/create-dmg) for macOS, [Inno Setup](https://jrsoftware.org/isinfo.php) for Windows

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
