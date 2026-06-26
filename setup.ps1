$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

function Find-Python {
    $knownPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
    )
    foreach ($path in $knownPaths) {
        if (Test-Path $path) {
            try {
                & $path --version | Out-Null
                return $path
            }
            catch {
            }
        }
    }

    $commands = @("py", "python", "python3")
    foreach ($command in $commands) {
        $resolved = Get-Command $command -ErrorAction SilentlyContinue
        if ($resolved) {
            try {
                & $command --version | Out-Null
                return $command
            }
            catch {
            }
        }
    }

    return $null
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string] $FilePath,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

$python = Find-Python
if (-not $python) {
    Write-Host "Python was not found or cannot start."
    Write-Host "Install Python 3.11+ from https://www.python.org/downloads/windows/ and enable 'Add python.exe to PATH'."
    exit 1
}

if (Test-Path ".venv") {
    Get-ChildItem -Path ".venv" -Recurse -Force | ForEach-Object {
        try {
            $_.Attributes = "Normal"
        }
        catch {
        }
    }
    Remove-Item ".venv" -Recurse -Force
}

Invoke-Native -FilePath $python -Arguments @("-m", "venv", ".venv")
$venvPython = ".\.venv\Scripts\python.exe"
$pipOptions = @("--trusted-host", "pypi.org", "--trusted-host", "files.pythonhosted.org", "--trusted-host", "download.pytorch.org")
Invoke-Native -FilePath $venvPython -Arguments (@("-m", "pip", "install") + $pipOptions + @("--upgrade", "pip"))
Invoke-Native -FilePath $venvPython -Arguments (@("-m", "pip", "install") + $pipOptions + @("-r", "requirements.txt"))

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $env:Path = "$userPath;$machinePath"
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
}

if (-not $ffmpeg) {
    Write-Host ""
    Write-Host "ffmpeg is not available in PATH."
    Write-Host "Install it with: winget install --id Gyan.FFmpeg -e --source winget"
}

Write-Host ""
Write-Host "Setup complete. Run with:"
Write-Host ".\.venv\Scripts\python.exe .\youtube_to_midi.py"
