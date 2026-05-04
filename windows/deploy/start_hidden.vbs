Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strVBSDir    = objFSO.GetParentFolderName(WScript.ScriptFullName)
strProjDir   = objFSO.GetParentFolderName(strVBSDir)
strPython    = strVBSDir & "\venv\Scripts\python.exe"
strMain      = strProjDir & "\main.py"

objShell.CurrentDirectory = strProjDir
objShell.Run """" & strPython & """ """ & strMain & """ daemon", 0, False
