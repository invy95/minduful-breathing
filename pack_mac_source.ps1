# 打包 Mac 待构建源码（发给朋友在 Mac 上 build）
# 排除 dist/build/__pycache__/.git 等，确保包含必要文件

$base = $PSScriptRoot
$tempName = "mindful-breathing-mac-source"
$temp = Join-Path (Split-Path $base -Parent) $tempName
$zipName = Join-Path (Split-Path $base -Parent) "$tempName.zip"

if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
New-Item -ItemType Directory -Path $temp -Force | Out-Null

# 复制项目（排除构建产物和不需要的文件）
robocopy $base $temp /E /XD dist build __pycache__ .git venv .venv BreathingBall_Local backend node_modules /XF .env *.spec.bak *.zip /NFL /NDL /NJH /NJS | Out-Null

# 确保 .env.dist 存在
$envDist = Join-Path $base ".env.dist"
if (-not (Test-Path (Join-Path $temp ".env.dist"))) {
    if (Test-Path $envDist) {
        Copy-Item $envDist (Join-Path $temp ".env.dist")
        Write-Host "[OK] .env.dist"
    } else {
        Write-Host "[WARN] .env.dist not found"
    }
}

# 删除不需要的文件
$unnecessary = @(
    "build_release.py",
    "MindfulBreathing.spec",
    "MindfulBreathing_onefile.spec",
    "BreathingBallLocal.spec",
    "pack_mac_source.ps1"
)
foreach ($f in $unnecessary) {
    $fp = Join-Path $temp $f
    if (Test-Path $fp) { Remove-Item $fp -Force }
}

# 打包
if (Test-Path $zipName) { Remove-Item $zipName -Force }
Compress-Archive -Path "$temp\*" -DestinationPath $zipName -Force
Remove-Item $temp -Recurse -Force

Write-Host ""
Write-Host "=== Done ==="
Write-Host "Output: $zipName"
Write-Host "Send this zip to your friend, they just need to follow BUILD_MAC.md"
