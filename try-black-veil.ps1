<#
.SYNOPSIS
    Try ENVY BLACK VEIL in a Hyper-V virtual machine on Windows.

.DESCRIPTION
    Creates a Generation 2 Hyper-V VM named "ENVY BLACK VEIL" (UEFI, Secure Boot
    with the Microsoft UEFI Certificate Authority template that AlmaLinux's signed
    boot chain needs, 6 GB of RAM, 4 CPUs, a 40 GB virtual disk and the Default
    Switch for networking), boots it from the ISO and opens its window. Nothing
    else on the PC changes. The live desktop logs in by itself; to install,
    double-click "Install ENVY BLACK VEIL" and pick the 40 GB virtual disk.

    Run it again without an ISO to boot what you installed; -Remove deletes the VM
    and its virtual disk.

    Needs Windows 10/11 Pro, Enterprise or Education with Hyper-V turned on, and an
    administrator PowerShell. On Windows Home, use VirtualBox or VMware Workstation
    instead (docs/try-it.md has the steps).

.EXAMPLE
    .\try-black-veil.ps1 .\envy-black-veil-0.1.0-x86_64.iso

.EXAMPLE
    .\try-black-veil.ps1            # boot the installed system

.EXAMPLE
    .\try-black-veil.ps1 -Remove    # delete the VM and its virtual disk

.NOTES
    If scripts are blocked:  powershell -ExecutionPolicy Bypass -File .\try-black-veil.ps1 <iso>
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $Iso,
    [string] $Name = 'ENVY BLACK VEIL',
    [ValidateRange(2048, 1048576)]
    [int64] $MemoryMB = 6144,
    [ValidateRange(1, 64)]
    [int] $Cpus = 4,
    [ValidateRange(20, 4096)]
    [int64] $DiskGB = 40,
    [switch] $Remove
)

$ErrorActionPreference = 'Stop'

function Write-Step([string] $Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Stop-WithError([string] $Message) {
    Write-Host "try-black-veil: $Message" -ForegroundColor Magenta
    exit 1
}

# --- Hyper-V must be on, and this PowerShell allowed to manage it ---------------
if (-not (Get-Command -Name New-VM -Module Hyper-V -ErrorAction SilentlyContinue)) {
    Stop-WithError ("Hyper-V isn't turned on. On Windows Pro, Enterprise or Education: Settings > System > " +
        "Optional features > More Windows features > tick Hyper-V, restart, then run this again. " +
        "On Windows Home, use VirtualBox or VMware Workstation (see docs/try-it.md).")
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal $identity
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$isHyperVAdmin = $principal.IsInRole((New-Object Security.Principal.SecurityIdentifier 'S-1-5-32-578'))
if (-not ($isAdmin -or $isHyperVAdmin)) {
    Stop-WithError 'run this from an administrator PowerShell (or join the Hyper-V Administrators group).'
}

try {
    $vm = Get-VM -Name $Name -ErrorAction SilentlyContinue
} catch {
    Stop-WithError ("Hyper-V isn't running ($($_.Exception.Message.Trim())). If you just turned it on, " +
        'restart Windows; otherwise check that the Hyper-V Virtual Machine Management service is running.')
}

# --- -Remove: delete the VM and its disk ----------------------------------------
if ($Remove) {
    if (-not $vm) { Write-Step "There's no VM named '$Name'."; exit 0 }
    $disks = @(Get-VMHardDiskDrive -VM $vm | ForEach-Object { $_.Path })
    if ($vm.State -ne 'Off') { Stop-VM -VM $vm -TurnOff -Force }
    Remove-VM -VM $vm -Force
    foreach ($disk in $disks) { if ($disk -and (Test-Path -LiteralPath $disk)) { Remove-Item -LiteralPath $disk } }
    Write-Step "Removed the VM '$Name' and its virtual disk."
    exit 0
}

# --- The ISO must match this PC -------------------------------------------------
$hostArch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'aarch64' } else { 'x86_64' }
if ($Iso) {
    if (-not (Test-Path -LiteralPath $Iso -PathType Leaf)) { Stop-WithError "no such ISO: $Iso" }
    $Iso = (Resolve-Path -LiteralPath $Iso).Path
    $isoArch = if ($Iso -match 'aarch64') { 'aarch64' } elseif ($Iso -match 'x86_64') { 'x86_64' } else { $hostArch }
    if ($isoArch -ne $hostArch) {
        Stop-WithError "this PC needs the $hostArch ISO (envy-black-veil-0.1.0-$hostArch.iso); Hyper-V can't run a $isoArch VM here."
    }
} elseif (-not $vm) {
    Stop-WithError "give the ISO to boot, e.g.: .\try-black-veil.ps1 .\envy-black-veil-0.1.0-$hostArch.iso"
}

# --- Create the VM once -----------------------------------------------------------
if (-not $vm) {
    $folder = (Get-VMHost).VirtualHardDiskPath
    $vhd = Join-Path $folder (($Name -replace '[^A-Za-z0-9]+', '-') + '.vhdx')
    if (Test-Path -LiteralPath $vhd) { Stop-WithError "a virtual disk already exists at $vhd; move it away or pick another -Name." }
    Write-Step "Creating the VM '$Name': Generation 2 (UEFI), $MemoryMB MB, $Cpus CPUs, a $DiskGB GB disk that grows as it's used"
    $settings = @{
        Name               = $Name
        Generation         = 2
        MemoryStartupBytes = $MemoryMB * 1MB
        NewVHDPath         = $vhd
        NewVHDSizeBytes    = $DiskGB * 1GB
    }
    $switch = Get-VMSwitch -Name 'Default Switch' -ErrorAction SilentlyContinue
    if ($switch) { $settings.SwitchName = $switch.Name }
    else { Write-Step "No 'Default Switch' found: the VM starts without networking (add a switch in Hyper-V Manager)." }
    $vm = New-VM @settings
    Set-VM -VM $vm -ProcessorCount $Cpus -StaticMemory -AutomaticCheckpointsEnabled $false
    # AlmaLinux's boot chain is signed through Microsoft's third-party UEFI CA.
    Set-VMFirmware -VM $vm -EnableSecureBoot On -SecureBootTemplate MicrosoftUEFICertificateAuthority
    Add-VMDvdDrive -VM $vm | Out-Null
}

# --- Boot from the ISO, or from the disk when there's none ---------------------------
if ($vm.State -ne 'Off') { Stop-WithError "the VM '$Name' is already running; open it from Hyper-V Manager." }
$dvd = Get-VMDvdDrive -VM $vm | Select-Object -First 1
if (-not $dvd) { $dvd = Add-VMDvdDrive -VM $vm -Passthru }
if ($Iso) {
    Set-VMDvdDrive -VMDvdDrive $dvd -Path $Iso
    Set-VMFirmware -VM $vm -FirstBootDevice (Get-VMDvdDrive -VM $vm | Select-Object -First 1)
    Write-Step "Booting the live system from $(Split-Path -Leaf $Iso). It logs in by itself."
} else {
    Set-VMDvdDrive -VMDvdDrive $dvd -Path $null
    $disk = Get-VMHardDiskDrive -VM $vm | Select-Object -First 1
    if ($disk) { Set-VMFirmware -VM $vm -FirstBootDevice $disk }
    Write-Step 'Booting the installed system.'
}

Start-VM -VM $vm
Start-Process -FilePath vmconnect.exe -ArgumentList 'localhost', "`"$Name`""
Write-Step "The VM's window is opening. Close it any time; stop the VM from Hyper-V Manager or with: Stop-VM -Name '$Name'"
