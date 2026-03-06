# Create desktop shortcut
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$base = "c:\Users\invy11\mindful-breathing"
$exeFile = Get-ChildItem -Path (Join-Path $base "dist") -Recurse -Filter "*.exe" | Select-Object -First 1
$exePath = $exeFile.FullName
$exeDir = Split-Path $exeFile.FullName -Parent
$icoPath = Join-Path (Join-Path $exeDir "_internal") "shortcut_icon.ico"
if (-not (Test-Path $icoPath)) { $icoPath = Join-Path $base "shortcut_icon.ico" }
$desktop = [Environment]::GetFolderPath('Desktop')
# 用 Unicode 码点避免脚本编码导致的乱码
$name = [char]0x547b + [char]0x5438 + [char]0x6ce1 + [char]0x6ce1
$shortcutPath = Join-Path $desktop "$name.lnk"

if (-not (Test-Path $exePath)) {
    Write-Host "EXE not found: $exePath"
    exit 1
}
if (-not (Test-Path $icoPath)) {
    Write-Host "Icon not found. Run: python create_shortcut_icon.py"
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell
$shortcut = $WshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = Split-Path $exePath
$shortcut.IconLocation = "$icoPath,0"
$shortcut.Description = $name
$shortcut.Save()
Write-Host "Desktop shortcut created: $shortcutPath"
