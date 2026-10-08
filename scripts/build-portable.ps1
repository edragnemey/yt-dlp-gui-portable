param(
    [string]$Version = '1.1.0'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$srcPath = Join-Path $repoRoot 'src\yt_dlp_gui.py'
$iconPath = Join-Path $repoRoot 'src\yt_dlp_gui.ico'
$buildRoot = Join-Path $repoRoot 'build'
$distRoot = Join-Path $repoRoot 'dist'
$packageName = "YtDlpGUI-v$Version-windows-x64"
$stagePath = Join-Path $distRoot $packageName
$zipPath = Join-Path $distRoot "$packageName.zip"

function Resolve-RequiredTool {
    param([Parameter(Mandatory)][string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required tool not found: $Name. Install it or add it to PATH."
    }
    return $command.Source
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python Launcher (py.exe) was not found. Python 3.10+ is required to build.'
}

& (Join-Path $PSScriptRoot 'make_icon.ps1') | Out-Null
& py -3 -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name YtDlpGUI `
    --icon $iconPath `
    --distpath (Join-Path $buildRoot 'app') `
    --workpath (Join-Path $buildRoot 'pyinstaller') `
    --specpath $buildRoot `
    $srcPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

New-Item -ItemType Directory -Force -Path $distRoot | Out-Null
if (Test-Path -LiteralPath $stagePath) {
    $resolvedDist = [IO.Path]::GetFullPath($distRoot)
    $resolvedStage = [IO.Path]::GetFullPath($stagePath)
    if (-not $resolvedStage.StartsWith($resolvedDist + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to clean a path outside the dist directory.'
    }
    Remove-Item -LiteralPath $stagePath -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

$toolsPath = Join-Path $stagePath 'tools'
$licensesPath = Join-Path $stagePath 'LICENSES'
New-Item -ItemType Directory -Force -Path $toolsPath,$licensesPath | Out-Null

Copy-Item -LiteralPath (Join-Path $buildRoot 'app\YtDlpGUI.exe') -Destination (Join-Path $stagePath 'YtDlpGUI.exe')
Copy-Item -LiteralPath (Join-Path $repoRoot 'PORTABLE_README.txt') -Destination (Join-Path $stagePath 'README.txt')
Copy-Item -LiteralPath (Join-Path $repoRoot 'THIRD_PARTY_NOTICES.md') -Destination (Join-Path $stagePath 'THIRD_PARTY_NOTICES.txt')
Copy-Item -Path (Join-Path $repoRoot 'licenses\*') -Destination $licensesPath

foreach ($tool in 'yt-dlp.exe','ffmpeg.exe','ffprobe.exe','deno.exe') {
    $source = Resolve-RequiredTool $tool
    Copy-Item -LiteralPath $source -Destination (Join-Path $toolsPath $tool)
}

Compress-Archive -LiteralPath $stagePath -DestinationPath $zipPath -CompressionLevel Optimal
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath
Write-Output "Portable package: $zipPath"
Write-Output "SHA256: $($hash.Hash)"
