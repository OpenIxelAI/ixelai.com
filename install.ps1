# Installs Ixel, or one of its tools alone, on Windows. $Only below picks which: '' for everything
# (Ixel MAT, Handoff, and Ixel in the Start Menu), 'mat' for Ixel MAT and its Start Menu entry, or
# 'handoff' for Handoff.
#
#   irm https://ixelai.com/install.ps1 | iex
#
# The site has three copies of this file, made from the one at its root by scripts/make-installers.py:
# install.ps1 (everything), ixel-mat/install.ps1 and handoff/install.ps1. Only $Only and the line above
# differ, so change the root one and run that script.
#
# For each tool it gets the source with git, into the folder that tool's own installer uses
# (%LOCALAPPDATA%\IxelMAT\repo and %LOCALAPPDATA%\Handoff\repo), then runs that installer
# (install.ps1 in the repo) in its own PowerShell. Nothing here needs administrator rights.
# Run it again any time to update.
#
# It runs inside your PowerShell window (that's what iex does), so it never calls exit, which would
# close the window: everything is in one script block, and a problem ends it with a message.
# Keep this file ASCII: Windows PowerShell may read it without knowing it's UTF-8.

& {
    # What to install: '' for everything (Ixel), 'mat' for Ixel MAT alone, 'handoff' for Handoff alone
    $Only = ''

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

    # Where a tool's folder came from ('' if it has no origin). git's complaint on stderr isn't a failure here,
    # though Windows PowerShell can turn one into an error under 'Stop'.
    function Get-Origin([string]$RepoDir) {
        $ErrorActionPreference = 'Continue'
        $url = git -C $RepoDir remote get-url origin 2>$null
        if ($LASTEXITCODE -eq 0) { return "$url".Trim() } else { return '' }
    }

    function Get-Source([string]$Url, [string]$Branch, [string]$RepoDir) {
        # A folder that came from another URL (a fork, say) is cloned again, so what's installed is what was asked for
        if ((Test-Path (Join-Path $RepoDir '.git')) -and ((Get-Origin $RepoDir) -eq $Url)) {
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

    # What's being installed, the same with what's in it, and the folder of this file's copy on the site
    switch ($Only) {
        ''        { $name = 'Ixel'; $parts = 'Ixel: Ixel MAT and Handoff'; $page = '' }
        'mat'     { $name = 'Ixel MAT'; $parts = $name; $page = 'ixel-mat/' }
        'handoff' { $name = 'Handoff'; $parts = $name; $page = 'handoff/' }
        default   { Say "This installer can't install '$Only'. `$Only must be '', 'mat' or 'handoff'." Red; return }
    }

    if ($env:OS -ne 'Windows_NT') {
        Say 'This installer is for Windows. On a Mac or Linux, run:' Yellow
        Say "  curl -fsSL https://ixelai.com/${page}install.sh | sh"
        return
    }

    # The same settings each tool's own installer reads, so both agree on where things go
    $tools = @(
        [pscustomobject]@{
            Key = 'mat'
            Name = 'Ixel MAT'
            Url = (Pick $env:IXEL_REPO_URL 'https://github.com/OpenIxelAI/ixel-mat.git')
            Branch = (Pick $env:IXEL_BRANCH 'main')
            Root = (Pick $env:IXEL_INSTALL_ROOT (Join-Path $env:LOCALAPPDATA 'IxelMAT'))
        },
        [pscustomobject]@{
            Key = 'handoff'
            Name = 'Handoff'
            Url = (Pick $env:HANDOFF_REPO_URL 'https://github.com/OpenIxelAI/Handoff-by-IxelAI.git')
            Branch = (Pick $env:HANDOFF_BRANCH 'main')
            Root = (Pick $env:HANDOFF_INSTALL_ROOT (Join-Path $env:LOCALAPPDATA 'Handoff'))
        }
    )
    $tools = @($tools | Where-Object { -not $Only -or $_.Key -eq $Only })
    $withMat = $Only -ne 'handoff'
    $withHandoff = $Only -ne 'mat'

    try {
        Say "Installing $parts." Cyan

        if (-not (Find-Git)) {
            $installed = $false
            if (Get-Command winget -ErrorAction SilentlyContinue) {
                $answer = Read-Host "Git is needed to download $name. Install Git now with winget? [Y/n]"
                if ($answer -notmatch '^\s*[nN]') {
                    # winget's exit code isn't a verdict ("already installed" isn't 0), so look again instead
                    & winget install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements
                    $installed = Find-Git
                }
            }
            if (-not $installed) {
                throw "Git is needed to download $name. Install it with:  winget install Git.Git   and open a new window."
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
    Say "$name is installed." Green
    $programs = [Environment]::GetFolderPath('Programs')
    if ($withMat -and $programs -and (Test-Path (Join-Path $programs 'Ixel.lnk'))) { Say 'Open Ixel from the Start Menu.' }
    Say 'Open a new terminal window first, so it finds the new commands. Then:'
    if ($withMat) { Say '  ixel setup               add your models and keys' }
    if ($withHandoff) { Say '  handoff setup --write    in a project folder: connect Claude Code, Codex and Claude Desktop' }
    Say "To update $name later, run the same install command again."
}
