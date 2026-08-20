[CmdletBinding()]
param(
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$specPath = Join-Path $projectRoot "packaging\Reckonsolve.spec"
$workPath = Join-Path $projectRoot "build\pyinstaller"
$distPath = Join-Path $projectRoot "dist"

Push-Location $projectRoot
try {
    uv sync --locked --group packaging
    if ($LASTEXITCODE -ne 0) {
        throw "uv sync failed with exit code $LASTEXITCODE."
    }

    uv run --group packaging pyinstaller `
        --clean `
        --noconfirm `
        --workpath $workPath `
        --distpath $distPath `
        $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $executable = Join-Path $distPath "Reckonsolve\Reckonsolve.exe"
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "The expected private executable was not produced: $executable"
    }

    if (-not $SkipSmoke) {
        $smokeRoot = Join-Path $projectRoot (
            "build\private-smoke\" + (Get-Date -Format "yyyyMMdd-HHmmss") +
            "-" + [Guid]::NewGuid().ToString("N")
        )
        New-Item -ItemType Directory -Path $smokeRoot | Out-Null
        $smokeBundle = Join-Path $smokeRoot "Reckonsolve"
        Copy-Item `
            -LiteralPath (Join-Path $distPath "Reckonsolve") `
            -Destination $smokeBundle `
            -Recurse
        $smokeExecutable = Join-Path $smokeBundle "Reckonsolve.exe"
        $databasePath = Join-Path $smokeRoot "reckonsolve-smoke.sqlite3"
        $backupPath = Join-Path $smokeRoot "reckonsolve-smoke-backup.sqlite3"

        $priorQtPlatform = $env:QT_QPA_PLATFORM
        $env:QT_QPA_PLATFORM = "offscreen"
        try {
            $process = Start-Process `
                -FilePath $smokeExecutable `
                -ArgumentList @(
                    "--private-build-smoke",
                    $databasePath,
                    $backupPath
                ) `
                -WorkingDirectory $smokeRoot `
                -Wait `
                -PassThru `
                -WindowStyle Hidden
        }
        finally {
            $env:QT_QPA_PLATFORM = $priorQtPlatform
        }

        if ($process.ExitCode -ne 0) {
            $diagnosticPath = [IO.Path]::ChangeExtension($databasePath, ".error.txt")
            throw "Private frozen smoke failed. See $diagnosticPath"
        }
        foreach ($path in @($databasePath, $backupPath)) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
                throw "Private frozen smoke did not create $path"
            }
        }
        Write-Host "Private frozen smoke passed: $smokeRoot"
    }

    Write-Host "Private onedir build ready: $executable"
}
finally {
    Pop-Location
}
