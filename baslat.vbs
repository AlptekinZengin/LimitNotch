' Limit Cubugu - konsol penceresi acmadan baslatir.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
klasor = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = klasor
sh.Run "pyw -3 """ & klasor & "\limit_cubugu.pyw""", 1, False
