Option Explicit
Dim fs, shell, root, quote, command
Set fs = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fs.GetParentFolderName(WScript.ScriptFullName)
quote = Chr(34)
command = quote & root & "\windows_runtime\pythonw.exe" & quote & " -B -I -S " & quote & root & "\initial_test_launcher.py" & quote
shell.CurrentDirectory = root
shell.Run command, 0, False
