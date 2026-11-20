# ArchitectOS — fixed Windows packaging build script.
#
# This file is REVIEWED and STATIC. It is copied into the sandbox unchanged and
# is never generated from user or model input. It runs only inside Windows
# Sandbox, with networking disabled and read-only toolchain mappings.
#
# Inputs  (C:\pkg\in, read-only):  job.json, source.py, build_sandbox.ps1
# Python  (C:\pkg\py, read-only):  full CPython with tkinter
# Modules (C:\pkg\sp, read-only):  PyInstaller and its dependencies
# Output  (C:\pkg\out, writable):  manifest.json, build.log, dist\

$ErrorActionPreference = 'Stop'

$In  = 'C:\pkg\in'
$Out = 'C:\pkg\out'
$Log = Join-Path $Out 'build.log'

$Job = $null

function Write-Manifest {
    param(
        [string] $Status,
        [int]    $Code,
        [string] $ExeSha,
        [long]   $ExeSize
    )
    $manifest = [ordered]@{
        contract      = 'ArchitectOSSandboxBuildV1'
        job_id        = if ($Job) { [string]$Job.job_id } else { '' }
        source_sha256 = if ($Job) { [string]$Job.source_sha256 } else { '' }
        exe_name      = if ($Job) { [string]$Job.exe_name } else { '' }
        status        = $Status
        exit_code     = $Code
        exe_sha256    = $ExeSha
        exe_size      = $ExeSize
        finished_at   = (Get-Date).ToUniversalTime().ToString('o')
    }
    $manifest | ConvertTo-Json -Compress |
        Set-Content -LiteralPath (Join-Path $Out 'manifest.json') -Encoding utf8
}

try {
    $Job = Get-Content -LiteralPath (Join-Path $In 'job.json') -Raw | ConvertFrom-Json

    $sourcePath = Join-Path $In 'source.py'
    $actual = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLower()

    "ArchitectOS sandbox build"          | Out-File -FilePath $Log -Encoding utf8
    "job_id=$($Job.job_id)"              | Out-File -FilePath $Log -Append -Encoding utf8
    "source_sha256_expected=$($Job.source_sha256)" | Out-File -FilePath $Log -Append -Encoding utf8
    "source_sha256_actual=$actual"       | Out-File -FilePath $Log -Append -Encoding utf8

    if ($actual -ne [string]$Job.source_sha256) {
        'SOURCE_DIGEST_MISMATCH' | Out-File -FilePath $Log -Append -Encoding utf8
        Write-Manifest -Status 'source_digest_mismatch' -Code -1 -ExeSha '' -ExeSize 0
        exit 2
    }

    $env:PYTHONPATH = 'C:\pkg\sp'
    Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue

    $python = 'C:\pkg\py\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        'PYTHON_MISSING' | Out-File -FilePath $Log -Append -Encoding utf8
        Write-Manifest -Status 'python_missing' -Code -1 -ExeSha '' -ExeSize 0
        exit 5
    }

    $distPath = Join-Path $Out 'dist'
    $workPath = Join-Path $Out 'work'
    $specPath = Join-Path $Out 'spec'

    # The sandbox logon command starts in C:\Windows\system32, and PyInstaller
    # refuses to run from there. Build from the writable output folder instead;
    # every artefact path below still resolves inside that same folder.
    Set-Location -LiteralPath $Out
    "working_directory=$((Get-Location).Path)" |
        Out-File -FilePath $Log -Append -Encoding utf8

    # Windows PowerShell 5.1 promotes a native command's stderr to a terminating
    # error while $ErrorActionPreference is 'Stop'. PyInstaller writes warnings to
    # stderr, so run it with 'Continue' and judge the build on its exit code.
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $python -m PyInstaller --onefile --windowed --noconfirm --clean `
            --log-level WARN `
            --name $Job.exe_name `
            --distpath $distPath `
            --workpath $workPath `
            --specpath $specPath `
            $sourcePath *>&1 | Out-File -FilePath $Log -Append -Encoding utf8
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    "pyinstaller_exit=$code" | Out-File -FilePath $Log -Append -Encoding utf8

    $exePath = Join-Path $distPath ($Job.exe_name + '.exe')

    if ($code -eq 0 -and (Test-Path -LiteralPath $exePath)) {
        $sha  = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLower()
        $size = (Get-Item -LiteralPath $exePath).Length
        "exe_sha256=$sha"    | Out-File -FilePath $Log -Append -Encoding utf8
        "exe_size=$size"     | Out-File -FilePath $Log -Append -Encoding utf8
        Write-Manifest -Status 'ok' -Code $code -ExeSha $sha -ExeSize $size
        exit 0
    }

    Write-Manifest -Status 'build_failed' -Code $code -ExeSha '' -ExeSize 0
    exit 3
}
catch {
    try {
        $_ | Out-String | Out-File -FilePath $Log -Append -Encoding utf8
        Write-Manifest -Status 'error' -Code -1 -ExeSha '' -ExeSize 0
    } catch { }
    exit 4
}
