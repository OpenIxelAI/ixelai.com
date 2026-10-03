# Installs Ixel MAT and Handoff on Windows, and adds Ixel to the Start Menu.
#
#   irm https://ixelai.com/install.ps1 | iex
#
# For each tool it gets the source with git, into the folder that tool's own installer uses
# (%LOCALAPPDATA%\IxelMAT\repo and %LOCALAPPDATA%\Handoff\repo), then runs that installer
# (install.ps1 in the repo) in its own PowerShell. Nothing here needs administrator rights.
# Run it again any time to update both.
#
# It runs inside your PowerShell window (that's what iex does), so it never calls exit, which would
# close the window: everything is in one script block, and a problem ends it with a message.
# Keep this file ASCII: Windows PowerShell may read it without knowing it's UTF-8.

& {
    $ErrorActionPreference = 'Stop'

    function Say([string]$Text, [string]$Color = 'Gray') { Write-Host $Text -ForegroundColor $Color }

    # PowerShell doesn't stop on a failing native command, so check its exit code. A warning git
    # writes to stderr isn't a failure, though Windows PowerShell can turn one into an error under 'Stop'.
    function Invoke-Checked([string]$What, [scriptblock]$Command, [string]$Hint = '') {
        $ErrorActionPreference = 'Continue'
        $global:LASTEXITCODE = -1  # stays -1 if the program can't be started at all
        & $Command
        if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE).$Hint" }
    }

    # Programs installed a moment ago (by winget, or by the first tool's installer) are on the PATH
    # saved in the registry, not yet on this window's. Add what's missing, at the end, so nothing
    # already on this window's PATH changes order.
    function Update-SessionPath {
        $have = @($env:Path -split ';' | Where-Object { $_ })
        $saved = @(([Environment]::GetEnvironmentVariable('Path', 'Machine'),
                    [Environment]::GetEnvironmentVariable('Path', 'User')) -join ';' -split ';' | Where-Object { $_ })
        $new = @($saved | Where-Object { $have -notcontains $_ } | Select-Object -Unique)
        if ($new.Count) { $env:Path = (@($have) + $new) -join ';' }
    }

    function Find-Git {
        if (Get-Command git -ErrorAction SilentlyContinue) { return $true }
        Update-SessionPath
        foreach ($dir in @("$env:ProgramFiles\Git\cmd", "$env:LOCALAPPDATA\Programs\Git\cmd")) {
            if (Test-Path (Join-Path $dir 'git.exe')) { $env:Path = "$dir;$env:Path" }
        }
        return [bool](Get-Command git -ErrorAction SilentlyContinue)
    }

    function Get-Source([string]$Url, [string]$Branch, [string]$RepoDir) {
        if (Test-Path (Join-Path $RepoDir '.git')) {
            Invoke-Checked 'git fetch' { git -C $RepoDir fetch --quiet origin $Branch }
            Invoke-Checked 'git checkout' { git -C $RepoDir checkout --quiet $Branch }
            Invoke-Checked 'git pull' { git -C $RepoDir pull --quiet --ff-only origin $Branch }
        } else {
            if (Test-Path $RepoDir) { Remove-Item -Recurse -Force $RepoDir }
            New-Item -ItemType Directory -Force -Path (Split-Path $RepoDir) | Out-Null
            Invoke-Checked 'git clone' { git clone --quiet --branch $Branch $Url $RepoDir }
        }
    }

    function Pick([string]$Setting, [string]$Default) { if ($Setting) { return $Setting } else { return $Default } }

    if ($env:OS -ne 'Windows_NT') {
        Say 'This installer is for Windows. On a Mac or Linux, run:' Yellow
        Say '  curl -fsSL https://ixelai.com/install.sh | sh'
        return
    }

    # The same settings each tool's own installer reads, so both agree on where things go
    $tools = @(
        [pscustomobject]@{
            Name = 'Ixel MAT'
            Url = (Pick $env:IXEL_REPO_URL 'https://github.com/OpenIxelAI/ixel-mat.git')
            Branch = (Pick $env:IXEL_BRANCH 'main')
            Root = (Pick $env:IXEL_INSTALL_ROOT (Join-Path $env:LOCALAPPDATA 'IxelMAT'))
        },
        [pscustomobject]@{
            Name = 'Handoff'
            Url = (Pick $env:HANDOFF_REPO_URL 'https://github.com/OpenIxelAI/Handoff-by-IxelAI.git')
            Branch = (Pick $env:HANDOFF_BRANCH 'main')
            Root = (Pick $env:HANDOFF_INSTALL_ROOT (Join-Path $env:LOCALAPPDATA 'Handoff'))
        }
    )

    try {
        Say 'Installing Ixel MAT and Handoff.' Cyan

        if (-not (Find-Git)) {
            $installed = $false
            if (Get-Command winget -ErrorAction SilentlyContinue) {
                $answer = Read-Host 'Git is needed to download the tools. Install Git now with winget? [Y/n]'
                if ($answer -notmatch '^\s*[nN]') {
                    # winget's exit code isn't a verdict ("already installed" isn't 0), so look again instead
                    & winget install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements
                    $installed = Find-Git
                }
            }
            if (-not $installed) {
                throw 'Git is needed to download the tools. Install it with:  winget install Git.Git   and open a new window.'
            }
        }

        foreach ($tool in $tools) {
            $repo = Join-Path $tool.Root 'repo'
            Say ''
            Say "== $($tool.Name)" Cyan
            Say "Getting the source into $repo"
            Get-Source $tool.Url $tool.Branch $repo
            $installer = Join-Path $repo 'install.ps1'
            Invoke-Checked "$($tool.Name)'s installer" {
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
            } ' The lines above say why.'
            Update-SessionPath
        }
    } catch {
        Say ''
        Say "Install stopped: $($_.Exception.Message)" Red
        Say 'Once that is fixed, run the same command again.'
        return
    }

    Say ''
    Say 'Ixel MAT and Handoff are installed.' Green
    $programs = [Environment]::GetFolderPath('Programs')
    if ($programs -and (Test-Path (Join-Path $programs 'Ixel.lnk'))) { Say 'Open Ixel from the Start Menu.' }
    Say 'Open a new terminal window first, so it finds the new commands. Then:'
    Say '  ixel setup               add your models and keys'
    Say '  handoff setup --write    in a project folder: connect Claude Code, Codex and Claude Desktop'
    Say 'To update both later, run the same install command again.'
}
