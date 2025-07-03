# updater.py
import sys
import os
import time
import zipfile
import shutil
import subprocess
import traceback

def log(message):
    """A simple logger for the updater."""
    log_file = os.path.join(os.path.expanduser("~"), "AutoVerse_updater.log")
    with open(log_file, "a", encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def main():
    log("="*20 + " Updater Session Started " + "="*20)
    
    try:
        # --- [THE FIX] Argument Validation ---
        log(f"Updater received arguments: {sys.argv}")
        if len(sys.argv) < 4:
            log(f"CRITICAL ERROR: Invalid arguments. Expected 4, got {len(sys.argv)}.")
            log("Usage: updater.exe <zip_path> <install_dir> <main_executable_name>")
            log("Updater cannot proceed.")
            return # Exit safely
        # -------------------------------------

        zip_path = sys.argv[1]
        install_dir = sys.argv[2]
        main_executable_name = sys.argv[3]
        
        log(f"Zip path: {zip_path}")
        log(f"Install directory: {install_dir}")
        log(f"Main executable to relaunch: {main_executable_name}")

        log("Waiting 3 seconds for main app to fully close...")
        time.sleep(3)
        
        target_path = os.path.join(install_dir, main_executable_name)
        log(f"Full path to old installation: {target_path}")

        if os.path.exists(target_path):
            log(f"Removing old version at: {target_path}")
            # The .app on macOS is a directory, as is the build folder on Windows.
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else: # Just in case it's a single file
                os.unlink(target_path)

        log(f"Extracting '{zip_path}' to '{install_dir}'")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(install_dir)
        log("Extraction complete.")

        # On Windows, the zip may contain a root folder. We move contents up.
        if sys.platform == 'win32':
            # Note: Assuming the GitHub Action zips the 'AutoVerse_App' folder's contents.
            # If it zips the folder itself, this logic might need adjustment.
            # For now, this is based on the desired build script outcome.
            # Let's check for a common directory name post-extraction
            extracted_items = os.listdir(install_dir)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(install_dir, extracted_items[0])):
                 source_folder = os.path.join(install_dir, extracted_items[0])
                 log(f"Detected single root folder '{source_folder}'. Moving contents up to '{install_dir}'.")
                 for item in os.listdir(source_folder):
                     shutil.move(os.path.join(source_folder, item), os.path.join(install_dir, item))
                 shutil.rmtree(source_folder)

        log(f"Cleaning up temporary zip file: {zip_path}")
        os.remove(zip_path)
        
        relaunch_path = os.path.join(install_dir, main_executable_name)
        log(f"Relaunching application at: {relaunch_path}")
        
        if sys.platform == 'darwin':
            # Use 'open' for .app bundles on macOS
            subprocess.Popen(['open', relaunch_path])
        else:
             # On Windows, the executable is now directly in the install_dir
             log(f"Full path for relaunch on Windows: {relaunch_path}")
             subprocess.Popen([relaunch_path])

        log("Updater finished successfully.")
    except Exception as e:
        log(f"An unhandled error occurred in updater: {str(e)}")
        log(f"Traceback: {traceback.format_exc()}")
        
if __name__ == '__main__':
    main()