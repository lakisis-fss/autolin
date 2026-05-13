import os
import sys
import subprocess
import site
import shutil

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    print("=== LabelImg Auto-Patcher ===")
    print("[1] Installing labelImg and setuptools...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "labelImg", "setuptools"])
        print("Installation successful.")
    except Exception as e:
        print(f"Error during installation: {e}")
        input("Press Enter to exit...")
        return

    print("\n[2] Locating site-packages...")
    # Get all possible site-packages directories
    site_packages_dirs = site.getsitepackages()
    if hasattr(site, 'getusersitepackages'):
        site_packages_dirs.append(site.getusersitepackages())
        
    target_dir = None
    for d in site_packages_dirs:
        if os.path.exists(os.path.join(d, "labelImg")):
            target_dir = d
            break

    if target_dir is None:
        print("Error: Could not locate labelImg installation directory.")
        print("Searched paths:", site_packages_dirs)
        input("Press Enter to exit...")
        return

    print(f"Found labelImg at: {target_dir}")

    print("\n[3] Applying patches...")
    labelimg_patch_src = resource_path(os.path.join("patches", "labelImg.py"))
    canvas_patch_src = resource_path(os.path.join("patches", "canvas.py"))

    labelimg_target = os.path.join(target_dir, "labelImg", "labelImg.py")
    canvas_target = os.path.join(target_dir, "libs", "canvas.py")

    try:
        if os.path.exists(labelimg_patch_src):
            shutil.copy2(labelimg_patch_src, labelimg_target)
            print(f"Patched: {labelimg_target}")
        else:
            print("Error: labelImg.py patch file not found in executable.")

        if os.path.exists(canvas_patch_src):
            shutil.copy2(canvas_patch_src, canvas_target)
            print(f"Patched: {canvas_target}")
        else:
            print("Error: canvas.py patch file not found in executable.")
    except Exception as e:
        print(f"Error applying patches: {e}")
        input("Press Enter to exit...")
        return

    print("\n=== All tasks completed successfully! ===")
    print("You can now run 'labelImg' from your terminal.")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
