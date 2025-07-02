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
    log("Updater started.")
    try:
        # Arguments passed from the main application
        zip_path = sys.argv[1]
        install_dir = sys.argv[2]
        main_executable_name = sys.argv[3] # e.g., 'AutoVerse' on Win or 'AutoVerse.app' on Mac

        log(f"Zip path: {zip_path}")
        log(f"Install dir: {install_dir}")
        log(f"Main executable: {main_executable_name}")

        log("Waiting for main app to close...")
        time.sleep(3)
        
        target_path = os.path.join(install_dir, main_executable_name)

        if sys.platform == 'darwin':
             if os.path.exists(target_path):
                log(f"Removing old .app bundle at {target_path}")
                shutil.rmtree(target_path)
        else: # For Windows, the executable is inside a folder.
            if os.path.exists(target_path):
                 log(f"Removing old application directory at {target_path}")
                 shutil.rmtree(target_path)

        log(f"Extracting {zip_path} to {install_dir}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # The structure from GitHub Actions will be 'AutoVerse_App/*', so extract to a temp dir first
            temp_extract_dir = os.path.join(install_dir, "autoverse_update_temp")
            zip_ref.extractall(temp_extract_dir)

            # Now move contents from AutoVerse_App folder to the actual install_dir
            source_folder = os.path.join(temp_extract_dir, "AutoVerse_App")
            for item in os.listdir(source_folder):
                 shutil.move(os.path.join(source_folder, item), install_dir)
            shutil.rmtree(temp_extract_dir)
        log("Extraction complete.")

        log(f"Removing temporary file {zip_path}")
        os.remove(zip_path)

        # 4. Relaunch the application
        relaunch_path = os.path.join(install_dir, main_executable_name)
        log(f"Relaunching application at {relaunch_path}")
        
        if sys.platform == 'darwin':
            subprocess.Popen(['open', relaunch_path])
        else:
             win_exe_path = os.path.join(relaunch_path, "AutoVerse.exe") # This path assumes the folder is no longer there. Let's fix.
             win_exe_path = os.path.join(install_dir, "AutoVerse.exe")
             log(f"Full path for relaunch on Windows: {win_exe_path}")
             subprocess.Popen([win_exe_path])

        log("Updater finished successfully.")
    except Exception as e:
        log(f"An error occurred: {str(e)}")

if __name__ == '__main__':
    main()