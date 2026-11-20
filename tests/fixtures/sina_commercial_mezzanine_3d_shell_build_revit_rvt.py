r'''ArchitectOS v52.0 — Automatic IFC4 to Native Revit (.rvt) Converter Launcher'''
import glob, os, subprocess, sys
IFC_PATH = r"\tmp\v62_2_build\tests\fixtures\sina_commercial_mezzanine_3d_shell.ifc"
RVT_PATH = r"\tmp\v62_2_build\tests\fixtures\sina_commercial_mezzanine_3d_shell_revit_model.rvt"
JOURNAL_PATH = r"\tmp\v62_2_build\tests\fixtures\sina_commercial_mezzanine_3d_shell_revit_journal.txt"
def main():
    cands = glob.glob(r"C:\Program Files\Autodesk\Revit *\Revit.exe")
    if cands:
        revit_exe = sorted(cands)[-1]
        subprocess.Popen([revit_exe, JOURNAL_PATH])
        print(f"[+] Launched Autodesk Revit ({revit_exe}) to generate {RVT_PATH}")
    else:
        print(f"[i] In Autodesk Revit, use File -> Open -> IFC and select: {IFC_PATH}")
if __name__ == '__main__':
    main()
