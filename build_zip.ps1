# build_zip.ps1 - Build a QGIS plugin zip with PEP 8 compliant directory name
# Usage: .\build_zip.ps1
#
# The top-level directory inside the zip MUST be a valid Python identifier
# (letters, digits, underscores only - no hyphens).

$pluginName = "orthogonal_measure"
$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputZip  = Join-Path $scriptDir "$pluginName.zip"

# Files to include in the zip
$includeFiles = @(
    "__init__.py",
    "orthogonal_measure.py",
    "orthogonal_measure_dialog.py",
    "orthogonal_measure_dialog_base.ui",
    "ortho_map_tool.py",
    "resources.py",
    "resources.qrc",
    "metadata.txt",
    "icon.png",
    "icon.svg",
    "LICENSE"
)

# Remove old zip if it exists
if (Test-Path $outputZip) {
    Remove-Item $outputZip -Force
    Write-Host "Removed old $pluginName.zip"
}

# Create a temporary staging directory
$tempDir = Join-Path $env:TEMP "qgis_plugin_build_$(Get-Random)"
$stageDir = Join-Path $tempDir $pluginName
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

# Copy files to staging directory
foreach ($file in $includeFiles) {
    $src = Join-Path $scriptDir $file
    if (Test-Path $src) {
        Copy-Item $src -Destination $stageDir
        Write-Host "  + $file"
    } else {
        Write-Warning "File not found: $file"
    }
}

# Create the zip from the temp directory (so top-level dir = orthogonal_measure)
Compress-Archive -Path $stageDir -DestinationPath $outputZip -CompressionLevel Optimal
Write-Host ""
Write-Host "Created: $outputZip"
Write-Host ""

# Verify zip contents
Write-Host "Zip contents (top-level entries):"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($outputZip)
$zip.Entries | Select-Object -First 20 FullName | Format-Table -AutoSize
$zip.Dispose()

# Clean up temp directory
Remove-Item $tempDir -Recurse -Force

Write-Host "Done! Upload $pluginName.zip to https://plugins.qgis.org/"
