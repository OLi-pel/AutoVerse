# updater.py
import sys
import os
import time
import zipfile
import shutil
import subprocess

def log(message):
    """A simple logger for the updater."""
    log_file = os.path.join(os.path.expanduser("~"), "AutoVerse_updater.log")
    with open(log_file, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def main():
    if len(sys.argv) < 4:
        log("Error: Not enough arguments. Expected zip_path, install_dir, main_executable_name.")
        return
        
    log("Updater started.")
    try:
        zip_path = sys.argv[1]
        install_dir = sys.argv[2]
        main_executable_name = sys.argv[3] 
        
        log(f"Zip path: {zip_path}")
        log(f"Install dir: {install_dir}")
        log(f"Main executable: {main_executable_name}")

        log("Waiting 3 seconds for main app to close...")
        time.sleep(3)
        
        target_path = os.path.join(install_dir, main_executable_name)

        if os.path.exists(target_path):
            log(f"Removing old version at: {target_path}")
            if sys.platform == 'darwin':
                # Remove the entire .app bundle (which is a directory)
                shutil.rmtree(target_path)
            else:
                # On Windows, the main executable is AutoVerse.exe but it's inside
                # a folder created by PyInstaller. The `install_dir` points to
                # this folder. So, we delete the contents of the directory.
                for filename in os.listdir(install_dir):
                    file_path = os.path.join(install_dir, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        log(f'Failed to delete {file_path}. Reason: {e}')

        log(f"Extracting {zip_path} to {install_dir}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # On macOS, this directly extracts 'AutoVerse.app'
            # On Windows, this extracts the 'AutoVerse_App' folder's contents.
            zip_ref.extractall(install_dir)
        log("Extraction complete.")
        
        # --- [THE FIX FOR WINDOWS FOLDER STRUCTURE] ---
        # On Windows, the zip contains a root folder (e.g., AutoVerse_App).
        # We need to move the contents of this folder up one level.
        if sys.platform == 'win32':
            # PyInstaller creates a folder called 'AutoVerse_App'
            source_folder = os.path.join(install_dir, "AutoVerse_App")
            if os.path.isdir(source_folder):
                log(f"Moving contents from {source_folder} to {install_dir}")
                for item in os.listdir(source_folder):
                    shutil.move(os.path.join(source_folder, item), os.path.join(install_dir, item))
                # Remove the now-empty source folder
                shutil.rmtree(source_folder)
            else:
                log(f"Warning: Expected source folder '{source_folder}' not found after extraction.")

        log(f"Cleaning up temporary zip file: {zip_path}")
        os.remove(zip_path)
        
        relaunch_path = os.path.join(install_dir, main_executable_name)
        log(f"Relaunching application at: {relaunch_path}")
        
        if sys.platform == 'darwin':
            subprocess.Popen(['open', relaunch_path])
        else:
             # On Windows, the executable is now directly in the install_dir
             win_exe_path = os.path.join(install_dir, main_executable_name)
             log(f"Full path for relaunch on Windows: {win_exe_path}")
             subprocess.Popen([win_exe_path])

        log("Updater finished successfully.")
    except Exception as e:
        log(f"An error occurred in updater: {str(e)}")
        log(f"Traceback: {traceback.format_exc()}")
        
if __name__ == '__main__':
    # Add a traceback import for better error logging in the updater itself
    import traceback
    main()