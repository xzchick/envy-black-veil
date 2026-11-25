#!/usr/bin/env python3
"""Boot the ENVY BLACK VEIL ISO in VMs and check it, the way a person would use it.

Boot 1, the real path: UEFI firmware -> the ISO's own boot loader -> the live
desktop. Screenshots every few seconds record the boot menu, splash and desktop.

Boot 2, the live system (UEFI, same kernel and initrd) with a serial console, so
this script can log in as the live user and check it from the inside: the desktop
runs, SELinux and the firewall are on, nothing listens on the network, and the
ENVY identity (splash, login theme, colours, wallpaper, installer, envy-tools) is
in place. With --install it then installs BLACK VEIL onto a blank virtual disk,
unattended: UEFI, LUKS2-encrypted, one admin user, using the same installer and
payload as the desktop's "Install ENVY BLACK VEIL" icon (anaconda --liveinst).

Boot 3 (with --install), the installed disk on fresh UEFI firmware, as if the
drive were moved to another PC: it types the disk passphrase into the ENVY splash,
reaches the login screen, logs in over serial and checks the installed system,
then signs in graphically for a desktop screenshot.

Secure Boot (x86_64, where firmware with Microsoft's keys enrolled is available,
as on most PCs and Hyper-V): the ISO boots through its own boot menu with Secure
Boot on, and (with --install) so does the installed disk; each is checked from
the inside for Secure Boot and kernel lockdown.

Writes screenshots, serial logs, results.json and summary.md to --out and exits
non-zero if a required check fails. Needs QEMU (qemu-system-x86_64 or
qemu-system-aarch64) with UEFI firmware, qemu-img and xorriso. It runs at full
speed with KVM (Linux) or Apple's Hypervisor framework (macOS) when the ISO
matches the computer's architecture, and emulated (slower, no install) otherwise.
Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import select
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

# Unix socket paths have a short length limit, so QEMU's sockets live in a short
# temporary folder whatever --out is.
SOCKETS = Path(tempfile.mkdtemp(prefix="envy-bt-"))

# livesys gives the live user an empty password (and wheel membership, but no
# NOPASSWD rule), so live root checks answer sudo's prompt with an empty line.
SUDO = "printf '\\n' | sudo -S -p ''"

# How each architecture's VM is put together. aarch64 is what Apple Silicon Macs
# (UTM, Parallels, VMware Fusion) and ARM PCs run natively. Firmware: Debian/Ubuntu,
# Fedora/EL, then QEMU's own copies (Homebrew on macOS).
QEMU_SHARE = ["/opt/homebrew/share/qemu", "/usr/local/share/qemu", "/usr/share/qemu"]
PLATFORMS = {
    "x86_64": {
        "qemu": "qemu-system-x86_64",
        "machine": ["-machine", "q35"],
        "code": ["/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_CODE.fd",
                 "/usr/share/edk2/ovmf/OVMF_CODE.fd"] + [f"{d}/edk2-x86_64-code.fd" for d in QEMU_SHARE],
        "vars": ["/usr/share/OVMF/OVMF_VARS_4M.fd", "/usr/share/OVMF/OVMF_VARS.fd",
                 "/usr/share/edk2/ovmf/OVMF_VARS.fd"] + [f"{d}/edk2-i386-vars.fd" for d in QEMU_SHARE],
        "display": ["-vga", "none", "-device", "virtio-vga,edid=on,xres=1600,yres=900"],
        "input": [],
        "tty": "ttyS0",
    },
    "aarch64": {
        "qemu": "qemu-system-aarch64",
        "machine": ["-machine", "virt,gic-version=max"],
        "code": ["/usr/share/AAVMF/AAVMF_CODE.fd", "/usr/share/edk2/aarch64/QEMU_EFI-pflash.raw"]
                + [f"{d}/edk2-aarch64-code.fd" for d in QEMU_SHARE],
        "vars": ["/usr/share/AAVMF/AAVMF_VARS.fd", "/usr/share/edk2/aarch64/vars-template-pflash.raw"]
                + [f"{d}/edk2-arm-vars.fd" for d in QEMU_SHARE],
        "display": ["-device", "virtio-gpu-pci,edid=on,xres=1600,yres=900"],
        "input": ["-device", "qemu-xhci", "-device", "usb-kbd", "-device", "usb-tablet"],
        "tty": "ttyAMA0",
    },
}
PLATFORM = PLATFORMS["x86_64"]           # set from --arch in main()
HOST_ARCH = {"arm64": "aarch64", "amd64": "x86_64"}.get(os.uname().machine, os.uname().machine)


def hardware_accel() -> str | None:
    """KVM on Linux, the Hypervisor framework on macOS, or None."""
    if os.access("/dev/kvm", os.R_OK | os.W_OK):
        return "kvm"
    if sys.platform == "darwin":
        hv = subprocess.run(["sysctl", "-n", "kern.hv_support"], capture_output=True, text=True)
        if hv.stdout.strip() == "1":
            return "hvf"
    return None


ACCEL = "tcg"                            # set in main(): kvm, hvf, or tcg (emulated)
SLOW = 1                                 # set in main(): emulated VMs get every wait stretched

# The throwaway identity of the CI install (never used outside these VMs).
TEST_USER = "envytest"
TEST_PASSWORD = "envytest2026"
LUKS_PASSPHRASE = "envyblackveiltest"
TEST_SUDO = f"printf '{TEST_PASSWORD}\\n' | sudo -S -p ''"

# The installer adds "rhgb quiet" (the graphical ENVY splash) only when it runs on a
# screen, as it does from the desktop icon; this test drives it over a serial
# console, so the kickstart adds them itself.
def install_ks(tty: str) -> str:
    return f"""# Unattended BLACK VEIL install for CI: the live system onto a blank disk, UEFI,
# LUKS2-encrypted, one admin user. Same installer and payload as the desktop's
# "Install ENVY BLACK VEIL" icon (anaconda --liveinst), without the GUI.
cmdline
lang en_US.UTF-8
keyboard --vckeymap=us --xlayouts=us
timezone Etc/UTC --utc
network --hostname=black-veil
rootpw --lock
user --name={TEST_USER} --groups=wheel --password={TEST_PASSWORD} --plaintext
firstboot --disable
xconfig --startxonboot
shutdown
ignoredisk --only-use=vda
zerombr
clearpart --all --initlabel --drives=vda
bootloader --boot-drive=vda --append="rhgb quiet console=tty0 console={tty},115200n8 plymouth.ignore-serial-consoles systemd.show_status=1"
autopart --type=lvm --encrypted --passphrase={LUKS_PASSPHRASE} --luks-version=luks2
"""


# Anaconda reads a kickstart in live mode only as interactive defaults: it never marks
# a live install as automated, so in --cmdline mode it stops at the disk selection
# instead of partitioning. This runs the very same installer, payload and kickstart
# with just that switch flipped, as an automated kickstart install sets it. (The
# kickstart's "shutdown" only lets it exit by itself: a live system isn't shut down.)
AUTOMATED_ANACONDA = """import runpy, sys
import pyanaconda.startup_utils as startup_utils
from pyanaconda.flags import flags

find_kickstart = startup_utils.find_kickstart


def automated(options):
    path = find_kickstart(options)
    flags.automatedInstall = True
    flags.eject = False
    return path


startup_utils.find_kickstart = automated
sys.argv = ["/usr/sbin/anaconda"] + sys.argv[1:]
runpy.run_path("/usr/sbin/anaconda", run_name="__main__")
"""


def wait_for(con, pattern: str, timeout: float) -> bool:
    """Wait until the serial output matches, without consuming it (login() reads it next)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if re.search(pattern, con.buf, re.M):
            return True
        con.pump(0.5)
    return False


def first_existing(paths):
    for p in paths:
        if Path(p).exists():
            return p
    raise SystemExit(f"none of these exist: {paths}")


# x86_64 UEFI firmware built for Secure Boot, with NVRAM that has Microsoft's keys
# enrolled and Secure Boot on: what most PCs and Hyper-V's Generation 2 VMs ship with.
SECURE_BOOT = {
    "code": ["/usr/share/OVMF/OVMF_CODE_4M.secboot.fd", "/usr/share/edk2/ovmf/OVMF_CODE.secboot.fd"],
    "vars": ["/usr/share/OVMF/OVMF_VARS_4M.ms.fd", "/usr/share/edk2/ovmf/OVMF_VARS.secboot.fd"],
}
SB_MACHINE = ["-machine", "q35,smm=on", "-global", "driver=cfi.pflash01,property=secure,value=on",
              "-global", "ICH9-LPC.disable_s3=1"]


def secure_boot_firmware(vars_copy: Path) -> list[str] | None:
    """Secure Boot firmware arguments (x86_64 only), or None where there's none."""
    if PLATFORM is not PLATFORMS["x86_64"]:
        return None
    code = next((p for p in SECURE_BOOT["code"] if Path(p).exists()), None)
    nvram = next((p for p in SECURE_BOOT["vars"] if Path(p).exists()), None)
    if not code or not nvram:
        return None
    shutil.copy(nvram, vars_copy)
    return ["-drive", f"if=pflash,format=raw,readonly=on,file={code}",
            "-drive", f"if=pflash,format=raw,file={vars_copy}"]


def secure_boot_checks(res: Results, prefix: str, sudo: str) -> None:
    res.check(f"{prefix}Secure Boot is on",
              "od -An -tu1 /sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c | awk '{print $NF}'",
              ok=lambda rc, o: o == "1")
    res.check(f"{prefix}kernel lockdown (Secure Boot's protection of the running kernel)",
              "cat /sys/kernel/security/lockdown", ok=lambda rc, o: "[integrity]" in o or "[confidentiality]" in o)
    res.check(f"{prefix}kernel log", f"{sudo} dmesg | grep -i -m3 -E 'secure ?boot'", required=False)


def ovmf(vars_copy: Path) -> list[str]:
    """UEFI firmware (OVMF on x86_64, AAVMF on aarch64) with its own NVRAM copy."""
    shutil.copy(first_existing(PLATFORM["vars"]), vars_copy)
    return ["-drive", f"if=pflash,format=raw,readonly=on,file={first_existing(PLATFORM['code'])}",
            "-drive", f"if=pflash,format=raw,file={vars_copy}"]


# ----- images ----------------------------------------------------------------

def ppm_to_png(ppm: Path, png: Path) -> None:
    """Convert QEMU's binary PPM screendump to PNG (fallback for old QEMU)."""
    data = ppm.read_bytes()
    parts = data.split(maxsplit=4)
    w, h, maxval, pixels = int(parts[1]), int(parts[2]), int(parts[3]), parts[4]
    assert parts[0] == b"P6" and maxval == 255
    rows = b"".join(b"\x00" + pixels[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


# ----- QEMU control ------------------------------------------------------------

def png_rows(png: Path) -> tuple[int, int, int, list[bytearray]]:
    """Decode an 8-bit RGB/RGBA PNG (QEMU's screendump) into rows of pixels."""
    data = png.read_bytes()
    pos, idat, width, height, ctype = 8, b"", 0, 0, 2
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, _, ctype = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
    raw, bpp = zlib.decompress(idat), 4 if ctype == 6 else 3
    stride, rows, prev, i = width * bpp, [], bytearray(width * bpp), 0
    for _ in range(height):
        kind, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], (prev[x - bpp] if x >= bpp else 0)
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif kind == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return width, height, bpp, rows


def passphrase_box_visible(png: Path) -> bool:
    """The ENVY splash's passphrase box: a long cyan-to-violet edge below the logo."""
    try:
        width, height, bpp, rows = png_rows(png)
    except (OSError, ValueError, zlib.error, struct.error):
        return False
    for y in range(height // 2, height):
        run = best = 0
        for x in range(width):
            r, g, b = rows[y][x * bpp:x * bpp + 3]
            run = run + 1 if (b > 200 and g > 120 and r < 200) else 0
            best = max(best, run)
        if best >= 300:
            return True
    return False


def grub_theme_visible(png: Path) -> bool:
    """The ENVY GRUB theme on screen: its pink countdown bar near the bottom."""
    try:
        width, height, bpp, rows = png_rows(png)
    except (OSError, ValueError, zlib.error, struct.error):
        return False
    for y in range(int(height * 0.8), height):
        run = 0
        for x in range(width):
            r, g, b = rows[y][x * bpp:x * bpp + 3]
            run = run + 1 if (r > 220 and g < 120 and b > 140) else 0
            if run >= 120:
                return True
    return False


def connect_unix(path: Path, timeout=30.0) -> socket.socket:
    deadline = time.monotonic() + timeout
    while True:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(str(path))
            return s
        except OSError:
            s.close()
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


KEY_NAMES = {" ": ["spc"], "-": ["minus"], ".": ["dot"], "/": ["slash"], "_": ["shift", "minus"],
             "=": ["equal"], ",": ["comma"], ":": ["shift", "semicolon"]}


class QMP:
    def __init__(self, path: Path):
        self.sock = connect_unix(path)
        self.file = self.sock.makefile("rwb")
        json.loads(self.file.readline())            # greeting
        self.cmd("qmp_capabilities")

    def cmd(self, name, **arguments):
        msg = {"execute": name}
        if arguments:
            msg["arguments"] = arguments
        self.file.write(json.dumps(msg).encode() + b"\n")
        self.file.flush()
        while True:
            reply = json.loads(self.file.readline())
            if "return" in reply:
                return reply["return"]
            if "error" in reply:
                raise RuntimeError(f"QMP {name}: {reply['error']}")

    def screenshot(self, png: Path) -> bool:
        try:
            self.cmd("screendump", filename=str(png), format="png")
            return png.exists()
        except (RuntimeError, OSError, ValueError):
            ppm = png.with_suffix(".ppm")
            try:
                self.cmd("screendump", filename=str(ppm))
                ppm_to_png(ppm, png)
                ppm.unlink()
                return True
            except Exception as exc:                     # noqa: BLE001
                print(f"  screenshot failed: {exc}")
                return False

    def type_text(self, text: str, enter=True) -> None:
        """Type on the VM's keyboard (for the disk passphrase and the login screen)."""
        for ch in text:
            if ch.isalpha() and ch.isupper():
                keys = ["shift", ch.lower()]
            elif ch.isalnum():
                keys = [ch]
            else:
                keys = KEY_NAMES[ch]
            self.cmd("send-key", **{"keys": [{"type": "qcode", "data": k} for k in keys], "hold-time": 60})
            time.sleep(0.08)
        if enter:
            self.cmd("send-key", keys=[{"type": "qcode", "data": "ret"}])

    def quit(self):
        try:
            self.cmd("quit")
        except Exception:                                # noqa: BLE001
            pass


def start_qemu(args, out: Path, name: str, extra: list[str], cdrom=True,
               machine: list[str] | None = None) -> tuple[subprocess.Popen, QMP]:
    qmp_path = SOCKETS / f"{name}.qmp"
    qmp_path.unlink(missing_ok=True)
    accel = ["-accel", "tcg,thread=multi", "-cpu", "max"] if ACCEL == "tcg" else ["-accel", ACCEL, "-cpu", "host"]
    cmd = [PLATFORM["qemu"], "-name", f"envy-{name}"] + accel + (machine or PLATFORM["machine"]) + [
           "-m", str(args.mem), "-smp", str(args.cpus)] + PLATFORM["display"] + PLATFORM["input"] + [
           "-display", "none", "-nic", "user,model=virtio-net-pci",
           "-qmp", f"unix:{qmp_path},server=on,wait=off"]
    if cdrom:
        if PLATFORM is PLATFORMS["x86_64"]:
            cmd += ["-drive", f"file={args.iso},media=cdrom,readonly=on"]
        else:                                            # the virt machine has no IDE: use virtio-scsi
            cmd += ["-drive", f"file={args.iso},if=none,id=cd0,media=cdrom,readonly=on",
                    "-device", "virtio-scsi-pci,id=scsi0", "-device", "scsi-cd,drive=cd0"]
    log = open(out / f"{name}-qemu.log", "w")
    proc = subprocess.Popen(cmd + extra, stdout=log, stderr=subprocess.STDOUT)
    return proc, QMP(qmp_path)


def stop_qemu(proc: subprocess.Popen, qmp: QMP) -> None:
    qmp.quit()
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()


# ----- serial console ------------------------------------------------------------

class Serial:
    def __init__(self, path: Path, log: Path):
        self.sock = connect_unix(path)
        self.sock.setblocking(False)
        self.buf = ""
        self.count = 0
        self.log = open(log, "a", encoding="utf-8", errors="replace")

    def pump(self, wait: float) -> None:
        r, _, _ = select.select([self.sock], [], [], wait)
        if r:
            data = self.sock.recv(65536)
            if data:
                text = data.decode("utf-8", "replace").replace("\r", "")
                self.buf += text
                self.log.write(text)
                self.log.flush()

    def expect(self, pattern: str, timeout: float) -> re.Match | None:
        rx = re.compile(pattern, re.M)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            m = rx.search(self.buf)
            if m:
                self.buf = self.buf[m.end():]
                return m
            self.pump(0.5)
        return None

    def send(self, text: str) -> None:
        self.sock.setblocking(True)
        self.sock.sendall(text.encode())
        self.sock.setblocking(False)

    def run(self, command: str, timeout=60) -> tuple[int | None, str]:
        self.count += 1
        tag = f"ENVYRC{self.count}X"
        self.buf = ""
        self.send(f"{command}; echo {tag}=$?\n")
        deadline = time.monotonic() + timeout * SLOW
        rx = re.compile(rf"{tag}=(\d+)")
        while time.monotonic() < deadline:
            m = rx.search(self.buf)
            if m:
                out = self.buf[:m.start()]
                self.buf = self.buf[m.end():]
                self.expect(r"\$\s*$", 10)          # consume the prompt that follows
                return int(m.group(1)), out.strip()
            self.pump(0.5)
        return None, self.buf.strip()

    def login(self, user: str, password: str, first_timeout: float) -> bool:
        for attempt in range(12):
            if not self.expect(r"login:\s*$", first_timeout if attempt == 0 else 90 * SLOW):
                return False
            self.send(user + "\n")
            m = self.expect(r"(Password:\s*$|\$\s*$|Login incorrect)", 30 * SLOW)
            if m and m.group(1).startswith("Password"):
                self.send(password + "\n")
                m = self.expect(r"(\$\s*$|Login incorrect)", 30 * SLOW)
            if m and "$" in m.group(1):
                self.send("export PS1='$ ' TERM=dumb; stty -echo; unset PROMPT_COMMAND\n")
                self.expect(r"\$\s*$", 10 * SLOW)
                self.run("true", 30)                     # soak up the rest of the echo
                return True
            time.sleep(5)                                # e.g. livesys still creating the user
        return False


class Results:
    def __init__(self):
        self.items: list[dict] = []
        self.console: Serial | None = None

    def record(self, name, ok, detail, required=True):
        detail = (detail or "").strip()
        self.items.append({"check": name, "ok": bool(ok), "required": required, "detail": detail[:2000]})
        print(f"  {'PASS' if ok else ('FAIL' if required else 'INFO')}  {name}: {detail[:160]}", flush=True)

    def check(self, name, command, ok=lambda rc, o: rc == 0, required=True, timeout=60):
        rc, output = self.console.run(command, timeout)
        self.record(name, rc is not None and ok(rc, output), output if output else f"exit {rc}", required)
        return rc, output


def no_network_listeners(prefix, sudo):
    return [
        (f"{prefix}SELinux is enforcing", "getenforce", lambda rc, o: o == "Enforcing", True),
        (f"{prefix}firewall is running", f"{sudo} firewall-cmd --state", lambda rc, o: o.endswith("running"), True),
        (f"{prefix}firewall opens no services or ports", f"{sudo} firewall-cmd --list-services; {sudo} firewall-cmd --list-ports",
         lambda rc, o: rc == 0 and set(o.split()) <= {"dhcpv6-client"}, True),
        (f"{prefix}SSH server is off", "systemctl is-enabled sshd 2>&1; systemctl is-active sshd 2>&1",
         lambda rc, o: "enabled" not in o.split() and "active" not in o.split(), True),
        (f"{prefix}nothing listens on the network (TCP)",
         "ss -H -tln | awk '{print $4}' | grep -v -E '^(127\\.|\\[::1\\]|::1)' || true", lambda rc, o: o.strip() == "", True),
        (f"{prefix}UDP sockets beyond loopback (DHCP client etc.)",
         "ss -H -uln | awk '{print $4}' | grep -v -E '^(127\\.|\\[::1\\]|::1)' || true", lambda rc, o: True, False),
    ]


def no_phone_home(prefix, sudo):
    return [
        (f"{prefix}no connectivity check to an outside server",
         f"{sudo} NetworkManager --print-config 2>/dev/null | sed -n '/^\\[connectivity\\]/,/^\\[/p'",
         lambda rc, o: rc == 0 and ("enabled=false" in o or "uri=" not in o), True),
        (f"{prefix}firmware metadata isn't fetched on a timer", "systemctl is-enabled fwupd-refresh.timer 2>&1",
         lambda rc, o: "enabled" not in o.split(), True),
        (f"{prefix}DNF's weekly count (countme) is off", "grep -l '^countme=1' /etc/yum.repos.d/*.repo | wc -l",
         lambda rc, o: o == "0", True),
        (f"{prefix}Firefox: no telemetry, studies or sponsored content",
         "python3 -c \"import json; p = json.load(open('/etc/firefox/policies/policies.json'))['policies']; "
         "print(p['DisableTelemetry'], p['DisableFirefoxStudies'], p['FirefoxHome']['SponsoredTopSites'])\"",
         lambda rc, o: o == "True True False", True),
        (f"{prefix}no remote-desktop, file-sharing or web-console servers installed",
         "rpm -q krfb krdp samba cockpit-ws 2>&1 | grep -c 'is not installed'", lambda rc, o: o == "4", True),
    ]


# ----- boot 1: the real boot path ---------------------------------------------

def boot_real(args, out: Path) -> list[str]:
    print("== Boot 1: UEFI firmware -> the ISO's boot loader -> live desktop", flush=True)
    proc, qmp = start_qemu(args, out, "boot1", ovmf(out / "OVMF_VARS_boot1.fd"))
    shots, start = [], time.monotonic()
    try:
        # Emulated VMs get longer, but not unbounded: boot 2 checks the desktop anyway.
        while time.monotonic() - start < min(args.real_boot_seconds * args.slow, 1200):
            t = int(time.monotonic() - start)
            png = out / f"boot1-{t:03d}s.png"
            if qmp.screenshot(png):
                shots.append(png.name)
            if proc.poll() is not None:
                print("  QEMU exited early")
                break
            time.sleep(args.shot_every * args.slow)
    finally:
        stop_qemu(proc, qmp)
    print(f"  {len(shots)} screenshots", flush=True)
    return shots


def boot_secure_live(args, out: Path, res: Results) -> None:
    """Boot the ISO through its own boot menu with Secure Boot on, and check from inside."""
    firmware = secure_boot_firmware(out / "OVMF_VARS_sb-live.fd")
    if firmware is None:
        print("== Secure Boot (live): skipped; no Secure Boot firmware with Microsoft's keys here", flush=True)
        return
    print("== Secure Boot (live): the ISO's signed boot chain (shim -> GRUB -> kernel) with Secure Boot on", flush=True)
    kernel, initrd, volid = iso_paths(args.iso)
    serial_path = SOCKETS / "serial-sb.sock"
    serial_path.unlink(missing_ok=True)
    proc, qmp = start_qemu(args, out, "sb-live", firmware + [
        "-chardev", f"socket,id=sersb,path={serial_path},server=on,wait=off", "-serial", "chardev:sersb"],
        machine=SB_MACHINE)
    con = Serial(serial_path, out / "serial-secureboot-live.log")
    res.console = con
    try:
        # The firmware mirrors GRUB's text menu to the serial port; wait for it, but well
        # inside the menu's 60-second timeout either way.
        con.expect(r"BLACK VEIL", 40)
        time.sleep(3)
        qmp.screenshot(out / "secureboot-menu.png")
        # From the boot menu, GRUB's own command line boots the live system with a
        # serial console added (GRUB allows this with Secure Boot on; the kernel it
        # loads must still pass shim's signature check).
        qmp.type_text("c", enter=False)
        time.sleep(2)
        qmp.type_text(f"linux {kernel} root=live:CDLABEL={volid} rd.live.image quiet rhgb console=tty0 "
                      f"console={PLATFORM['tty']},115200n8 plymouth.ignore-serial-consoles")
        qmp.type_text(f"initrd {initrd}")
        qmp.screenshot(out / "secureboot-grub-commands.png")
        qmp.type_text("boot")
        ok = con.login("liveuser", "", first_timeout=420)
        res.record("Secure Boot (live): boots to a login with Secure Boot on", ok,
                   "logged in over serial" if ok else "no login; see secureboot-*.png and serial-secureboot-live.log")
        if ok:
            secure_boot_checks(res, "Secure Boot (live): ", SUDO)
    finally:
        stop_qemu(proc, qmp)


# ----- boot 2: the live system, then the install -------------------------------

def iso_paths(iso: Path) -> tuple[str, str, str]:
    """(kernel path, initrd path, volume id) inside the ISO."""
    listing = subprocess.run(["xorriso", "-indev", str(iso), "-find", "/", "-type", "f"],
                             capture_output=True, text=True).stdout
    files = [line.strip().strip("'") for line in listing.splitlines()
             if line.strip().startswith(("'/", "/"))]
    kernels = [f for f in files if re.search(r"/vmlinuz[^/]*$", f)]
    if not kernels:
        raise SystemExit(f"no kernel found in {iso.name}")
    kernel = next((f for f in kernels if "/pxeboot/" in f), kernels[0])
    folder = kernel.rsplit("/", 1)[0]
    initrd = next(f for f in files if f.rsplit("/", 1)[0] == folder and re.search(r"/initrd[^/]*\.img$", f))
    info = subprocess.run(["xorriso", "-indev", str(iso), "-pvd_info"], capture_output=True, text=True)
    volid = re.search(r"Volume Id\s*:\s*(.+)", info.stdout + info.stderr).group(1).strip()
    return kernel, initrd, volid


def live_checks(res: Results, qmp: QMP, args, out: Path) -> None:
    con = res.console
    deadline = time.monotonic() + 420 * args.slow
    while time.monotonic() < deadline:                  # SDDM logs liveuser into Plasma
        rc, _ = con.run("pgrep -u liveuser -x plasmashell >/dev/null", 20)
        if rc == 0:
            break
        time.sleep(5)
    rc, _ = res.check("Plasma desktop is running for the live user", "pgrep -u liveuser -a plasmashell")
    appletsrc = "~/.config/plasma-org.kde.plasma.desktop-appletsrc"
    deadline = time.monotonic() + 120 * args.slow
    while rc == 0 and time.monotonic() < deadline:       # Plasma writes this once the desktop is up
        if con.run(f"test -s {appletsrc}", 20)[0] == 0:
            break
        time.sleep(5)
    res.check("SDDM auto-login config", "grep -rh -A2 '^\\[Autologin\\]' /etc/sddm.conf /etc/sddm.conf.d/ 2>/dev/null",
              required=False)
    if rc != 0:                                          # explain a missing desktop in the same run
        res.check("diagnosis: SDDM log", f"{SUDO} journalctl -b -u sddm -o cat --no-pager | tail -n 40", required=False)
        res.check("diagnosis: live user's session log",
                  f"{SUDO} journalctl -b -o cat --no-pager _UID=$(id -u liveuser) | tail -n 60", required=False)
        res.check("diagnosis: errors this boot", f"{SUDO} journalctl -b -p err -o cat --no-pager | tail -n 40",
                  required=False)
    time.sleep(args.settle * args.slow)
    if qmp.screenshot(out / "desktop.png"):
        print("  saved desktop.png", flush=True)

    res.check("system state", "systemctl is-system-running", ok=lambda rc, o: o in ("running", "degraded"), required=False)
    res.check("failed units", "systemctl --failed --no-legend --plain | head -20", required=False)
    res.check("graphical target reached", "systemctl is-active graphical.target", ok=lambda rc, o: o == "active")
    res.check("SDDM login manager active", "systemctl is-active sddm", ok=lambda rc, o: o == "active")
    res.check("booted with UEFI", "test -d /sys/firmware/efi && echo uefi", ok=lambda rc, o: o == "uefi")
    for name, command, ok, required in no_network_listeners("", SUDO) + no_phone_home("", SUDO):
        res.check(name, command, ok=ok, required=required)
    res.check("ENVY packages installed", "rpm -q envy-black-veil-theme envy-black-veil-release")
    res.check("ENVY release file", "cat /etc/envy-black-veil-release", ok=lambda rc, o: "ENVY BLACK VEIL" in o)
    res.check("ENVY boot splash is the default", "plymouth-set-default-theme", ok=lambda rc, o: o == "envy-black-veil")
    res.check("ENVY login theme selected", "grep -h '^Current=' /etc/sddm.conf.d/*.conf",
              ok=lambda rc, o: "envy-black-veil" in o)
    res.check("ENVY colours on the desktop (window background 10,14,34)",
              "kreadconfig6 --file kdeglobals --group Colors:Window --key BackgroundNormal",
              ok=lambda rc, o: o == "10,14,34")
    res.check("ENVY wallpaper on the desktop",
              "grep -h -A3 'Wallpaper..org.kde.image..General' ~/.config/plasma-org.kde.plasma.desktop-appletsrc",
              ok=lambda rc, o: "EnvyBlackVeil" in o)
    res.check("hostname is black-veil", "hostname", ok=lambda rc, o: o == "black-veil", required=False)
    res.check("installer is on the menu", "grep -m1 '^Name=' /usr/share/applications/liveinst.desktop",
              ok=lambda rc, o: "ENVY BLACK VEIL" in o)
    res.check("installer is on the live desktop", "ls ~/Desktop", ok=lambda rc, o: "liveinst.desktop" in o)
    res.check("installer doesn't look you up online (no geolocation)",
              "python3 -c 'from pyanaconda.core.configuration.anaconda import conf; conf.set_from_files(); "
              "print(repr(conf.timezone.geolocation_provider), conf.localization.use_geolocation)'",
              ok=lambda rc, o: o == "'' False")
    res.check("envy-tools works", "envy-tools list | head -6")
    res.check("ENVY app runtime (Python, PyQt6, cryptography)",
              "python3 -c 'import PyQt6.QtWidgets, cryptography; print(\"ok\")'", ok=lambda rc, o: o.endswith("ok"))
    res.check("base system", "head -3 /etc/os-release", required=False)
    res.check("kernel", "uname -r", required=False)


def install_to_disk(res: Results, args, out: Path) -> bool:
    print("== Installing BLACK VEIL onto the blank disk (unattended, LUKS2, UEFI)", flush=True)
    con = res.console
    con.run("cat > /tmp/envy-install.ks << 'EOF'\n" + install_ks(PLATFORM["tty"]) + "EOF\ntrue", 30)
    res.check("install: kickstart in place", "grep -c . /tmp/envy-install.ks")
    wrapper = base64.b64encode(AUTOMATED_ANACONDA.encode()).decode()
    con.run(f"echo {wrapper} | base64 -d > /tmp/envy-anaconda.py", 30)
    # Run the installer in the background (the serial shell stays responsive), then poll.
    # The same environment liveinst sets up (it's what the desktop icon runs, via pkexec):
    # the live user's session bus and PKEXEC_UID, which Anaconda uses to switch to the
    # user while it asks the desktop not to blank the screen, and the product name and
    # version from /etc/system-release. Like liveinst, SELinux is permissive while the
    # installer runs and restored afterwards (the installed system is enforcing).
    env = ("env PKEXEC_UID=$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus"
           " XDG_RUNTIME_DIR=/run/user/$(id -u)"
           " ANACONDA_PRODUCTNAME=\"$(sed -r -e 's/ *release.*//' /etc/system-release)\""
           " ANACONDA_PRODUCTVERSION=\"$(sed -r -e 's/^.* ([0-9.]+).*$/\\1/' /etc/system-release)\""
           " ANACONDA_ISFINAL=true")
    # In live mode Anaconda ignores --kickstart and parses its interactive defaults,
    # /usr/share/anaconda/interactive-defaults.ks, instead (BLACK VEIL's own defaults
    # are in there); in this throwaway live VM the test's kickstart is added to them,
    # and AUTOMATED_ANACONDA runs the result unattended.
    con.run("{ ( " + SUDO + " " + env + " sh -c 'cat /tmp/envy-install.ks >> /usr/share/anaconda/interactive-defaults.ks;"
            " setenforce 0; python3 /tmp/envy-anaconda.py --liveinst --cmdline"
            " > /tmp/envy-install.log 2>&1; echo $? > /tmp/envy-install.rc; setenforce 1' ) > /dev/null 2>&1 & }", 30)
    started, last, status = time.monotonic(), "", None
    while time.monotonic() - started < args.install_timeout:
        time.sleep(20)
        rc, out_rc = con.run("cat /tmp/envy-install.rc 2>/dev/null || echo running", 30)
        if out_rc.strip().isdigit():
            status = int(out_rc.strip())
            break
        rc, tail = con.run("tail -n 1 /tmp/envy-install.log 2>/dev/null", 30)
        if tail and tail != last:
            print(f"  installer: {tail[:160]}", flush=True)
            last = tail
    minutes = (time.monotonic() - started) / 60
    rc, log_tail = con.run("tail -n 25 /tmp/envy-install.log 2>/dev/null", 30)
    done = status is not None and (status == 0 or re.search(r"\binstallation complete\b", log_tail, re.I) is not None)
    res.record("install: the installer finished", done,
               f"exit {status} after {minutes:.1f} min · " + log_tail[-600:] if status is not None
               else f"still running after {minutes:.1f} min")
    logs = []
    for f in ("/tmp/envy-install.log", "/tmp/anaconda.log", "/tmp/storage.log", "/tmp/program.log", "/tmp/packaging.log"):
        rc, text = con.run(f"{SUDO} tail -n 120 {f} 2>/dev/null", 60)
        logs.append(f"===== {f}\n{text}\n")
    (out / "install-logs.txt").write_text("\n".join(logs))
    con.run(f"{SUDO} sync", 60)
    return done


def boot_live(args, out: Path, res: Results, disk: Path | None) -> bool:
    print("== Boot 2: the live system with a serial console, then checks from the inside", flush=True)
    kernel, initrd, volid = iso_paths(args.iso)
    print(f"  kernel {kernel}, initrd {initrd}, volume '{volid}'", flush=True)
    for src, dst in ((kernel, "vmlinuz"), (initrd, "initrd.img")):
        subprocess.run(["xorriso", "-osirrox", "on", "-indev", str(args.iso), "-extract", src, str(out / dst)],
                       check=True, capture_output=True)
    serial_path = SOCKETS / "serial2.sock"
    serial_path.unlink(missing_ok=True)
    cmdline = (f"root=live:CDLABEL={volid} rd.live.image quiet rhgb console=tty0 console={PLATFORM['tty']},115200n8 "
               "plymouth.ignore-serial-consoles systemd.journald.forward_to_console=0")
    extra = ovmf(out / "OVMF_VARS_boot2.fd") + [
        "-kernel", str(out / "vmlinuz"), "-initrd", str(out / "initrd.img"), "-append", cmdline,
        "-chardev", f"socket,id=ser2,path={serial_path},server=on,wait=off", "-serial", "chardev:ser2"]
    if disk:
        extra += ["-drive", f"file={disk},if=virtio,cache=writeback"]
    proc, qmp = start_qemu(args, out, "boot2", extra)
    res.console = Serial(serial_path, out / "serial-live.log")
    installed = False
    try:
        started = time.monotonic()
        ok = res.console.login("liveuser", "", first_timeout=600 * args.slow)
        res.record("boots to a login on the serial console", ok,
                   f"after {int(time.monotonic() - started)}s" if ok else "no login prompt / login failed")
        if not ok:
            return False
        live_checks(res, qmp, args, out)
        if disk:
            installed = install_to_disk(res, args, out)
    finally:
        stop_qemu(proc, qmp)
    return installed


# ----- boot 3: the installed system --------------------------------------------

def boot_installed(args, out: Path, res: Results, disk: Path, secure: bool = False) -> None:
    name, pre = ("boot4", "installed + Secure Boot: ") if secure else ("boot3", "installed: ")
    firmware = secure_boot_firmware(out / f"OVMF_VARS_{name}.fd") if secure else ovmf(out / f"OVMF_VARS_{name}.fd")
    if firmware is None:
        print("== Secure Boot (installed): skipped; no Secure Boot firmware with Microsoft's keys here", flush=True)
        return
    print("== Boot 4: the installed disk with Secure Boot on" if secure else
          "== Boot 3: the installed disk on fresh UEFI firmware (like moving the drive to another PC)", flush=True)
    serial_path = SOCKETS / f"serial-{name}.sock"
    serial_path.unlink(missing_ok=True)
    proc, qmp = start_qemu(args, out, name, firmware + [
        "-drive", f"file={disk},if=virtio,cache=writeback",
        "-chardev", f"socket,id=ser3,path={serial_path},server=on,wait=off", "-serial", "chardev:ser3"], cdrom=False,
        machine=SB_MACHINE if secure else None)
    con = Serial(serial_path, out / ("serial-installed-secureboot.log" if secure else "serial-installed.log"))
    res.console = con
    try:
        # Firmware, GRUB, then the initrd starts the ENVY splash, which asks for the disk
        # passphrase. Plymouth takes over the console once it starts, so the last thing the
        # serial console shows is the splash starting (systemd.show_status=1).
        start, next_shot, asked = time.monotonic(), 0.0, False
        while time.monotonic() - start < 420:
            con.pump(0.5)
            if re.search(r"Show Plymouth Boot Screen|Cryptography Setup|Please enter passphrase", con.buf):
                asked = True
                break
            t = time.monotonic() - start
            if t >= next_shot and next_shot < 120:
                qmp.screenshot(out / f"{name}-{int(t):03d}s.png")
                next_shot += 2.5 if not secure else 10
        if not secure:
            menus = [p for p in sorted(out.glob(f"{name}-*.png")) if grub_theme_visible(p)]
            res.record(f"{pre}the ENVY GRUB menu is on screen", bool(menus),
                       f"in {menus[0].name}" if menus else f"no themed menu in the {name}-*.png screenshots")
        res.record(f"{pre}boots to the ENVY splash, which asks for the disk passphrase", asked,
                   f"splash after {int(time.monotonic() - start)}s" if asked else "the boot splash never started (see the boot screenshots)")
        if not asked:
            return
        # Type the passphrase into the splash like a person would. Keys typed before the
        # prompt is up are ignored, so if the boot doesn't go on, try again.
        unlocked = False
        for attempt in range(3):
            time.sleep(15 if attempt == 0 else 5)
            if not secure:
                shot = out / ("installed-luks.png" if attempt == 0 else f"installed-luks-retry{attempt}.png")
                qmp.screenshot(shot)
                if attempt == 0:
                    res.record(f"{pre}the ENVY splash shows the passphrase box", passphrase_box_visible(shot),
                               "seen in installed-luks.png" if passphrase_box_visible(shot)
                               else "no passphrase box on screen (see installed-luks.png)")
            con.buf = ""                                 # only signs that come after typing count
            qmp.type_text(LUKS_PASSPHRASE)
            if wait_for(con, r"login:\s*$|Reached target.*(Initrd Root|Switch Root|Multi-User|Graphical)", 150):
                unlocked = True
                break
        res.record(f"{pre}unlocks with the passphrase typed into the ENVY splash", unlocked,
                   "unlocked" if unlocked else "no sign of the disk unlocking after 3 tries")
        if not unlocked:
            return
        logged_in = con.login(TEST_USER, TEST_PASSWORD, first_timeout=600)
        res.record(f"{pre}boots to a login", logged_in, "logged in over serial" if logged_in else "no login")
        if not logged_in:
            return
        if secure:
            secure_boot_checks(res, pre, TEST_SUDO)
            return
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            rc, o = con.run("systemctl is-active sddm", 20)
            if o == "active":
                break
            time.sleep(5)
        time.sleep(args.settle)
        qmp.screenshot(out / "installed-login.png")

        s = TEST_SUDO
        res.check("installed: booted with UEFI", "test -d /sys/firmware/efi && echo uefi", ok=lambda rc, o: o == "uefi")
        res.check("installed: it's the installed system, not the live image",
                  "test ! -e /run/initramfs/live && echo installed", ok=lambda rc, o: o == "installed")
        res.check("installed: system disk is LUKS2-encrypted",
                  f"{s} cryptsetup luksDump $(lsblk -rpno NAME,FSTYPE | awk '$2==\"crypto_LUKS\"{{print $1; exit}}') | grep -m1 '^Version'",
                  ok=lambda rc, o: o.split()[-1:] == ["2"])
        res.check("installed: disk layout", "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS", required=False)
        res.check("installed: graphical target", "systemctl is-active graphical.target", ok=lambda rc, o: o == "active")
        res.check("installed: SDDM login screen, no auto-login",
                  "systemctl is-active sddm; grep -rhs '^User=' /etc/sddm.conf /etc/sddm.conf.d/ || echo no-autologin",
                  ok=lambda rc, o: o.split() == ["active", "no-autologin"])
        res.check("installed: ENVY login theme selected", "grep -h '^Current=' /etc/sddm.conf.d/*.conf",
                  ok=lambda rc, o: "envy-black-veil" in o)
        res.check("installed: login screen log", f"{s} journalctl -b -u sddm --no-pager -o cat | tail -n 25", required=False)
        res.check("installed: ENVY boot splash is the default", "plymouth-set-default-theme",
                  ok=lambda rc, o: o == "envy-black-veil")
        res.check("installed: ENVY GRUB menu switched on",
                  f"{s} grep -E '^(terminal_output|set theme=).*' /boot/grub2/grub.cfg",
                  ok=lambda rc, o: "envy-black-veil/theme.txt" in o and "gfxterm" in o)
        res.check("installed: boot menu entries named ENVY BLACK VEIL",
                  f"{s} sh -c \"grep -h '^title' /boot/loader/entries/*.conf\"",
                  ok=lambda rc, o: bool(o) and all("ENVY BLACK VEIL" in line for line in o.splitlines()))
        for name, command, ok, required in no_network_listeners("installed: ", s) + no_phone_home("installed: ", s):
            res.check(name, command, ok=ok, required=required)
        res.check("installed: ENVY packages", "rpm -q envy-black-veil-theme envy-black-veil-release")
        res.check("installed: ENVY colours for the new user (skel)",
                  "grep -h '^ColorScheme=' ~/.config/kdeglobals 2>/dev/null", ok=lambda rc, o: "EnvyNeon" in o)
        res.check("installed: no live-installer icon for the new user",
                  "ls ~/Desktop 2>/dev/null | grep -c liveinst || true", ok=lambda rc, o: o.strip() in ("", "0"))
        res.check("installed: user is an administrator", "id -nG", ok=lambda rc, o: "wheel" in o.split())
        res.check("installed: hostname", "hostname", ok=lambda rc, o: o == "black-veil", required=False)
        res.check("installed: envy-tools works", "envy-tools list | head -4")
        res.check("installed: release", "cat /etc/envy-black-veil-release; head -2 /etc/os-release", required=False)

        # Sign in on the ENVY login screen like a person would, for a desktop screenshot.
        qmp.type_text(TEST_PASSWORD)
        deadline = time.monotonic() + 240
        signed_in = False
        while time.monotonic() < deadline:
            rc, _ = con.run(f"pgrep -u {TEST_USER} -x plasmashell >/dev/null", 20)
            if rc == 0:
                signed_in = True
                break
            time.sleep(5)
        res.record("installed: signs in on the ENVY login screen", signed_in,
                   "Plasma started for the new user" if signed_in else "no Plasma session after typing the password",
                   required=False)
        if signed_in:
            time.sleep(args.settle)
            qmp.screenshot(out / "installed-desktop.png")
    finally:
        stop_qemu(proc, qmp)


# ----- main --------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mem", type=int, default=6144)
    ap.add_argument("--cpus", type=int, default=4)
    ap.add_argument("--real-boot-seconds", type=int, default=300)
    ap.add_argument("--shot-every", type=int, default=6)
    ap.add_argument("--settle", type=int, default=25, help="seconds to let a desktop settle before its screenshot")
    ap.add_argument("--skip-real-boot", action="store_true")
    ap.add_argument("--install", action="store_true", help="also install to a blank disk and boot the installed system")
    ap.add_argument("--install-timeout", type=int, default=3600)
    ap.add_argument("--disk-size", default="30G")
    ap.add_argument("--keep-disk", action="store_true", help="keep the installed disk (installed-disk.qcow2) afterwards")
    ap.add_argument("--installed-disk", type=Path,
                    help="skip the live boots and the install; boot and check this already-installed disk")
    ap.add_argument("--arch", choices=sorted(PLATFORMS),
                    default=HOST_ARCH if HOST_ARCH in PLATFORMS else "x86_64")
    args = ap.parse_args()
    global PLATFORM, ACCEL, SLOW
    PLATFORM = PLATFORMS[args.arch]
    # Hardware virtualization runs only the computer's own architecture. Without it
    # the VM is emulated (several times slower): stretch the waits, and skip the
    # install, which would take hours.
    ACCEL = (hardware_accel() if args.arch == HOST_ARCH else None) or "tcg"
    args.slow = SLOW = 6 if ACCEL == "tcg" else 1
    print(f"{args.arch} VMs, " + {"kvm": "KVM", "hvf": "Hypervisor framework"}.get(
        ACCEL, f"emulated (no hardware virtualization for {args.arch} here)"), flush=True)
    if args.install and ACCEL == "tcg":
        print("  emulated: skipping the install test (it needs hardware virtualization to finish in time)")
        args.install = False
    args.iso = args.iso.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out.resolve()

    res = Results()
    if args.installed_disk:                             # iterate on the installed-system checks
        shots = []
        boot_installed(args, out, res, args.installed_disk.resolve())
        boot_installed(args, out, res, args.installed_disk.resolve(), secure=True)
    else:
        shots = [] if args.skip_real_boot else boot_real(args, out)
        if not args.skip_real_boot:
            boot_secure_live(args, out, res)
        disk = None
        if args.install:
            disk = out / "installed-disk.qcow2"
            disk.unlink(missing_ok=True)
            subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(disk), args.disk_size], check=True)
        installed = boot_live(args, out, res, disk)
        if args.install and installed:
            boot_installed(args, out, res, disk)
            boot_installed(args, out, res, disk, secure=True)
        if disk and disk.exists() and not args.keep_disk:
            disk.unlink()                               # 10+ GB; not worth keeping

    results = res.items
    failed = [r for r in results if r["required"] and not r["ok"]]
    (out / "results.json").write_text(json.dumps({"iso": args.iso.name, "checks": results,
                                                  "real_boot_screenshots": shots}, indent=2))
    lines = ["## ENVY BLACK VEIL boot test", "",
             f"ISO `{args.iso.name}`: **{'PASSED' if not failed and results else 'FAILED'}** "
             f"({sum(r['ok'] for r in results if r['required'])}/{sum(r['required'] for r in results)} required checks)", "",
             "| Check | Result | Detail |", "| --- | --- | --- |"]
    for r in results:
        mark = "✅" if r["ok"] else ("❌" if r["required"] else "ℹ️")
        detail = r["detail"].replace("\n", " · ").replace("|", "\\|")[:180]
        lines.append(f"| {r['check']} | {mark} | `{detail}` |")
    summary = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(summary)
    print(summary)
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
