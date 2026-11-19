<#
.SYNOPSIS
  Installs Ollama and downloads local AI tutor models for LogicBuilder (Windows).

.DESCRIPTION
  1. Installs Ollama with winget if it is missing.
  2. Starts the Ollama service if it is not running.
  3. Downloads the models for the chosen profile (skips ones you already have).
  4. Tells LogicBuilder which model ids to use.

  Profiles (download sizes are approximate):
    light     ~4 GB   for 8 GB RAM PCs:   qwen2.5-coder:1.5b, gemma3:1b, deepseek-r1:1.5b
    standard  ~13 GB  for 16 GB RAM PCs:  qwen2.5-coder:7b,   gemma3:4b, deepseek-r1:8b
    all       both sets
    none      install Ollama only
  Without -Profile it picks light or standard from your installed RAM.
  Kimi K2 is too large to run locally; use it through OpenRouter (see README).

.EXAMPLE
  .\setup-ai.ps1                      # auto profile, asks before installing
  .\setup-ai.ps1 -Profile standard -Yes
  .\setup-ai.ps1 -DryRun              # show what would happen, change nothing
  .\setup-ai.ps1 -Models "qwen2.5-coder:3b","gemma3:4b"
#>
[CmdletBinding()]
param(
  [ValidateSet("", "light", "standard", "all", "none")] [string]$Profile = "",
  [string[]]$Models = @(),
  [switch]$Yes,
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

$Sets = @{
  light    = [ordered]@{ qwen = "qwen2.5-coder:1.5b"; gemma = "gemma3:1b"; deepseek = "deepseek-r1:1.5b" }
  standard = [ordered]@{ qwen = "qwen2.5-coder:7b";   gemma = "gemma3:4b"; deepseek = "deepseek-r1:8b" }
}

function Say($m)  { Write-Host "  $m" }
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Run($what, [scriptblock]$do) {
  if ($DryRun) { Say "[dry run] would: $what" } else { & $do }
}
function Confirm-Step($q) {
  if ($Yes -or $DryRun) { return $true }
  $a = Read-Host "  $q [Y/n]"
  return ($a -eq "" -or $a -match "^[Yy]")
}
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Find-Ollama {
  Refresh-Path
  $c = Get-Command ollama -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $p = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
  if (Test-Path $p) { return $p }
  return $null
}
function Api-Up {
  try { Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null; return $true } catch { return $false }
}

# ---------------------------------------------------------------- choose models
$ramGb = 0
try { $ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB) } catch { }
if (-not $Profile) {
  if ($ramGb -ge 14) { $Profile = "standard" } else { $Profile = "light" }
  Say "Detected about $ramGb GB RAM, using the '$Profile' profile (override with -Profile)."
}
$wanted = [ordered]@{}   # family -> model id
if ($Models.Count -gt 0) {
  foreach ($m in $Models) { $wanted[$m] = $m }
} elseif ($Profile -eq "all") {
  foreach ($k in "light", "standard") { foreach ($f in $Sets[$k].Keys) { $wanted["$f/$k"] = $Sets[$k][$f] } }
} elseif ($Profile -ne "none") {
  foreach ($f in $Sets[$Profile].Keys) { $wanted[$f] = $Sets[$Profile][$f] }
}

Write-Host "LogicBuilder AI setup" -ForegroundColor Green
Say "Models to download: $(if ($wanted.Count) { ($wanted.Values -join ', ') } else { '(none)' })"
if ($DryRun) { Say "Dry run: nothing will be installed or changed." }

# ---------------------------------------------------------------- 1. Ollama
Step "1/4 Ollama"
$ollama = Find-Ollama
if ($ollama) {
  Say "Ollama is already installed: $ollama"
} else {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Say "winget was not found. Install Ollama manually from https://ollama.com/download/windows and run this script again."
    if (-not $DryRun) { exit 1 }
  }
  if (Confirm-Step "Install Ollama with winget (about 1 GB)?") {
    Run "winget install --id Ollama.Ollama -e --silent" {
      winget install --id Ollama.Ollama -e --silent --accept-package-agreements --accept-source-agreements
      if ($LASTEXITCODE -ne 0) { throw "winget could not install Ollama (exit code $LASTEXITCODE)." }
    }
    $ollama = Find-Ollama
    if (-not $ollama -and -not $DryRun) { throw "Ollama installed but was not found. Open a new terminal and run this script again." }
  } else { Say "Skipped. Install Ollama from https://ollama.com and re-run."; exit 0 }
}

# ---------------------------------------------------------------- 2. service
Step "2/4 Ollama service"
if (Api-Up) {
  Say "Ollama is running."
} else {
  Run "start 'ollama serve' in the background" {
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
    $ok = $false
    for ($i = 0; $i -lt 30; $i++) { Start-Sleep 1; if (Api-Up) { $ok = $true; break } }
    if (-not $ok) { throw "Ollama did not start within 30 seconds. Start it from the Start menu and re-run." }
    Say "Ollama started."
  }
}

# ---------------------------------------------------------------- 3. models
Step "3/4 Models"
$have = @()
if (-not $DryRun -and $ollama) { $have = @(& $ollama list 2>$null | Select-Object -Skip 1 | ForEach-Object { ($_ -split "\s+")[0] }) }
$pulled = [ordered]@{}
foreach ($key in $wanted.Keys) {
  $m = $wanted[$key]
  if ($have -contains $m -or $have -contains "$m`:latest") { Say "$m is already downloaded."; $pulled[$key] = $m; continue }
  Run "ollama pull $m" {
    Say "Downloading $m (this can take a while)..."
    & $ollama pull $m
    if ($LASTEXITCODE -ne 0) { Write-Warning "Could not download $m. Check the name at https://ollama.com/library and your connection." } else { $pulled[$key] = $m }
  }
}

# ---------------------------------------------------------------- 4. tell LogicBuilder
Step "4/4 LogicBuilder settings"
$pairs = @()
if ($Models.Count -eq 0 -and $Profile -ne "all" -and $Profile -ne "none") { foreach ($f in $pulled.Keys) { $pairs += "$f=$($pulled[$f])" } }
if ($pairs.Count -gt 0) {
  Run "python scripts\set_models.py $($pairs -join ' ')" {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { & $py.Source (Join-Path $Root "scripts\set_models.py") @pairs }
    else { Say "Python not found; set the model ids in the AI Tutor settings (gear icon) instead." }
  }
} else {
  Say "Nothing to update. In the AI Tutor panel (gear icon) enter the model ids you want to use."
}

Write-Host "`nDone." -ForegroundColor Green
Say "Start LogicBuilder, open the AI Tutor panel, pick 'Local (Ollama)'."
Say "Models you have:  ollama list"
