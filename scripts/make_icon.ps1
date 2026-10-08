Add-Type -AssemblyName System.Drawing

$outputPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'src\yt_dlp_gui.ico'
$bitmap = [System.Drawing.Bitmap]::new(256, 256)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::FromArgb(31, 41, 55))

$blueBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(59, 130, 246))
$whiteBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
$softBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(219, 234, 254))

$graphics.FillEllipse($blueBrush, 24, 24, 208, 208)
$graphics.FillRectangle($whiteBrush, 112, 61, 32, 92)
$arrow = [System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(72, 132),
    [System.Drawing.Point]::new(184, 132),
    [System.Drawing.Point]::new(128, 188)
)
$graphics.FillPolygon($whiteBrush, $arrow)
$graphics.FillRectangle($softBrush, 68, 199, 120, 13)

$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$stream = [System.IO.File]::Open($outputPath, [System.IO.FileMode]::Create)
$icon.Save($stream)
$stream.Dispose()
$icon.Dispose()
$softBrush.Dispose()
$whiteBrush.Dispose()
$blueBrush.Dispose()
$graphics.Dispose()
$bitmap.Dispose()

Write-Output $outputPath
