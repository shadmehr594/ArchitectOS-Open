# ==========================================================
# ArchitectOS Image Snapshot Manager v1
# Immutable project image snapshots
# ==========================================================

from pathlib import Path
import shutil


BASE_DIR = Path(__file__).resolve().parents[2]


SNAPSHOT_ROOT = (
    BASE_DIR
    /
    "memory"
    /
    "comfy"
    /
    "projects"
    /
    "active_project"
    /
    "versions"
)



class ImageSnapshotManager:


    def __init__(self):

        SNAPSHOT_ROOT.mkdir(
            parents=True,
            exist_ok=True
        )



    def save(
        self,
        image_path,
        version
    ):


        version_dir = (
            SNAPSHOT_ROOT
            /
            version
        )


        version_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        source = Path(
            image_path
        )


        target = (
            version_dir
            /
            "image.png"
        )


        shutil.copy2(
            source,
            target
        )


        return str(target)



snapshot_manager = ImageSnapshotManager()