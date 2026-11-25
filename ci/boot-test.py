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

Writes screenshots, serial logs, results.json and summary.md to --out and exits
non-zero if a required check fails. Needs qemu-system-x86_64, OVMF, qemu-img,
xorriso and /dev/kvm. Standard library only.
"""

from __future__ import annotations

import argparse
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
# (UTM, Parallels, VMware Fusion) and ARM PCs run natively.
PLATFORMS = {
    "x86_64": {
        "qemu": "qemu-system-x86_64",
        "machine": ["-machine", "q35"],
        "code": ["/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_CODE.fd"],
        "vars": ["/usr/share/OVMF/OVMF_VARS_4M.fd", "/usr/share/OVMF/OVMF_VARS.fd"],
        "display": ["-vga", "none", "-device", "virtio-vga,edid=on,xres=1600,yres=900"],
        "input": [],
        "tty": "ttyS0",
    },
    "aarch64": {
        "qemu": "qemu-system-aarch64",
        "machine": ["-machine", "virt,gic-version=max"],
        "code": ["/usr/share/AAVMF/AAVMF_CODE.fd"],
        "vars": ["/usr/share/AAVMF/AAVMF_VARS.fd"],
        "display": ["-device", "virtio-gpu-pci,edid=on,xres=1600,yres=900"],
        "input": ["-device", "qemu-xhci", "-device", "usb-kbd", "-device", "usb-tablet"],
        "tty": "ttyAMA0",
    },
}
PLATFORM = PLATFORMS["x86_64"]           # set from --arch in main()
KVM = os.access("/dev/kvm", os.R_OK | os.W_OK)

# The throwaway identity of the CI install (never used outside these VMs).
TEST_USER = "envytest"
TEST_PASSWORD = "envytest2026"
LUKS_PASSPHRASE = "envyblackveiltest"
TEST_SUDO = f"printf '{TEST_PASSWORD}\\n' | sudo -S -p ''"

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
ignoredisk --only-use=vda
zerombr
clearpart --all --initlabel --drives=vda
bootloader --boot-drive=vda --append="console=tty0 console={tty},115200n8 plymouth.ignore-serial-consoles systemd.show_status=1"
autopart --type=lvm --encrypted --passphrase={LUKS_PASSPHRASE} --luks-version=luks2
"""


def first_existing(paths):
    for p in paths:
        if Path(p).exists():
            return p
    raise SystemExit(f"none of these exist: {paths}")


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


KEY_NAMES = {" ": ["spc"], "-": ["minus"], ".": ["dot"], "/": ["slash"], "_": ["shift", "minus"]}


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


def start_qemu(args, out: Path, name: str, extra: list[str], cdrom=True) -> tuple[subprocess.Popen, QMP]:
    qmp_path = SOCKETS / f"{name}.qmp"
    qmp_path.unlink(missing_ok=True)
    accel = ["-enable-kvm", "-cpu", "host"] if KVM else ["-accel", "tcg,thread=multi", "-cpu", "max"]
    cmd = [PLATFORM["qemu"], "-name", f"envy-{name}"] + accel + PLATFORM["machine"] + [
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
        deadline = time.monotonic() + timeout
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
            if not self.expect(r"login:\s*$", first_timeout if attempt == 0 else 90):
                return False
            self.send(user + "\n")
            m = self.expect(r"(Password:\s*$|\$\s*$|Login incorrect)", 30)
            if m and m.group(1).startswith("Password"):
                self.send(password + "\n")
                m = self.expect(r"(\$\s*$|Login incorrect)", 30)
            if m and "$" in m.group(1):
                self.send("export PS1='$ ' TERM=dumb; stty -echo; unset PROMPT_COMMAND\n")
                self.expect(r"\$\s*$", 10)
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


# ----- boot 1: the real boot path ---------------------------------------------

def boot_real(args, out: Path) -> list[str]:
    print("== Boot 1: UEFI firmware -> the ISO's boot loader -> live desktop", flush=True)
    proc, qmp = start_qemu(args, out, "boot1", ovmf(out / "OVMF_VARS_boot1.fd"))
    shots, start = [], time.monotonic()
    try:
        while time.monotonic() - start < args.real_boot_seconds * args.slow:
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
    res.check("SDDM auto-login config", "grep -rh -A2 '^\\[Autologin\\]' /etc/sddm.conf /etc/sddm.conf.d/ 2>/dev/null",
              required=False)
    if rc != 0:                                          # explain a missing desktop in the same run
        res.check("diagnosis: SDDM log", f"{SUDO} journalctl -b -u sddm -o cat --no-pager | tail -n 40", required=False)
        res.check("diagnosis: live user's session log",
                  f"{SUDO} journalctl -b -o cat --no-pager _UID=$(id -u liveuser) | tail -n 60", required=False)
        res.check("diagnosis: errors this boot", f"{SUDO} journalctl -b -p err -o cat --no-pager | tail -n 40",
                  required=False)
    time.sleep(args.settle)
    if qmp.screenshot(out / "desktop.png"):
        print("  saved desktop.png", flush=True)

    res.check("system state", "systemctl is-system-running", ok=lambda rc, o: o in ("running", "degraded"), required=False)
    res.check("failed units", "systemctl --failed --no-legend --plain | head -20", required=False)
    res.check("graphical target reached", "systemctl is-active graphical.target", ok=lambda rc, o: o == "active")
    res.check("SDDM login manager active", "systemctl is-active sddm", ok=lambda rc, o: o == "active")
    res.check("booted with UEFI", "test -d /sys/firmware/efi && echo uefi", ok=lambda rc, o: o == "uefi")
    for name, command, ok, required in no_network_listeners("", SUDO):
        res.check(name, command, ok=ok, required=required)
    res.check("ENVY packages installed", "rpm -q envy-black-veil-theme envy-black-veil-release")
    res.check("ENVY release file", "cat /etc/envy-black-veil-release", ok=lambda rc, o: "ENVY BLACK VEIL" in o)
    res.check("ENVY boot splash is the default", "plymouth-set-default-theme", ok=lambda rc, o: o == "envy-black-veil")
    res.check("ENVY login theme selected", "grep -h '^Current=' /etc/sddm.conf.d/*.conf",
              ok=lambda rc, o: "envy-black-veil" in o)
    res.check("ENVY colour scheme for the user",
              "grep -h -E '^(ColorScheme|LookAndFeelPackage)=' ~/.config/kdeglobals /etc/xdg/kdeglobals 2>/dev/null",
              ok=lambda rc, o: "ColorScheme=EnvyNeon" in o)
    res.check("user's kdeglobals (head)", "ls -la ~/.config/kdeglobals /etc/skel/.config/kdeglobals; head -n 12 ~/.config/kdeglobals",
              required=False)
    res.check("ENVY wallpaper on the desktop",
              "grep -h -A3 'Wallpaper..org.kde.image..General' ~/.config/plasma-org.kde.plasma.desktop-appletsrc",
              ok=lambda rc, o: "EnvyBlackVeil" in o)
    res.check("hostname is black-veil", "hostname", ok=lambda rc, o: o == "black-veil", required=False)
    res.check("installer is on the menu", "grep -m1 '^Name=' /usr/share/applications/liveinst.desktop",
              ok=lambda rc, o: "ENVY BLACK VEIL" in o)
    res.check("installer is on the live desktop", "ls ~/Desktop", ok=lambda rc, o: "liveinst.desktop" in o)
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
    # Run the installer in the background (the serial shell stays responsive), then poll.
    # The same environment liveinst sets up (it's what the desktop icon runs): the live
    # user's session bus (Anaconda asks the desktop not to blank the screen through it)
    # and the product name and version from /etc/system-release.
    env = ("env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus XDG_RUNTIME_DIR=/run/user/$(id -u)"
           " ANACONDA_PRODUCTNAME=\"$(sed -r -e 's/ *release.*//' /etc/system-release)\""
           " ANACONDA_PRODUCTVERSION=\"$(sed -r -e 's/^.* ([0-9.]+).*$/\\1/' /etc/system-release)\""
           " ANACONDA_ISFINAL=true")
    con.run("{ ( " + SUDO + " " + env + " sh -c 'anaconda --liveinst --cmdline --kickstart=/tmp/envy-install.ks"
            " > /tmp/envy-install.log 2>&1; echo $? > /tmp/envy-install.rc' ) > /dev/null 2>&1 & }", 30)
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

def boot_installed(args, out: Path, res: Results, disk: Path) -> None:
    print("== Boot 3: the installed disk on fresh UEFI firmware (like moving the drive to another PC)", flush=True)
    serial_path = SOCKETS / "serial3.sock"
    serial_path.unlink(missing_ok=True)
    proc, qmp = start_qemu(args, out, "boot3", ovmf(out / "OVMF_VARS_boot3.fd") + [
        "-drive", f"file={disk},if=virtio,cache=writeback",
        "-chardev", f"socket,id=ser3,path={serial_path},server=on,wait=off", "-serial", "chardev:ser3"], cdrom=False)
    con = Serial(serial_path, out / "serial-installed.log")
    res.console = con
    try:
        start, next_shot, asked = time.monotonic(), 0.0, False
        while time.monotonic() - start < 420:            # GRUB, splash, then the passphrase prompt
            con.pump(0.5)
            if re.search(r"Cryptography Setup|systemd-cryptsetup@|Please enter passphrase", con.buf):
                asked = True
                break
            t = time.monotonic() - start
            if t >= next_shot and next_shot < 120:
                qmp.screenshot(out / f"boot3-{int(t):03d}s.png")
                next_shot += 2.5
        res.record("installed: boots and asks for the disk passphrase", asked,
                   f"after {int(time.monotonic() - start)}s" if asked else "no passphrase prompt seen on the serial console")
        if not asked:
            return
        unlocked = False
        for attempt in range(3):
            time.sleep(8)
            qmp.screenshot(out / ("installed-luks.png" if attempt == 0 else f"installed-luks-retry{attempt}.png"))
            con.buf = ""                                 # only signs that come after typing count
            qmp.type_text(LUKS_PASSPHRASE)
            if con.expect(r"Finished.*Cryptography Setup|Reached target.*Initrd Root|login:", 60):
                unlocked = True
                break
        res.record("installed: unlocks with the passphrase typed into the ENVY splash", unlocked,
                   "unlocked" if unlocked else "no sign of the disk unlocking after 3 tries")
        if not unlocked:
            return
        logged_in = con.login(TEST_USER, TEST_PASSWORD, first_timeout=600)
        res.record("installed: boots to a login", logged_in, "logged in over serial" if logged_in else "no login")
        if not logged_in:
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
                  "grep -E '^GRUB_(THEME|TERMINAL_OUTPUT)=' /etc/default/grub; " + s + " grep -c 'envy-black-veil' /boot/grub2/grub.cfg",
                  ok=lambda rc, o: "envy-black-veil/theme.txt" in o and "gfxterm" in o)
        for name, command, ok, required in no_network_listeners("installed: ", s):
            res.check(name, command, ok=ok, required=required)
        res.check("installed: ENVY packages", "rpm -q envy-black-veil-theme envy-black-veil-release")
        res.check("installed: ENVY colours for the new user",
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
    ap.add_argument("--arch", choices=sorted(PLATFORMS), default=os.uname().machine
                    if os.uname().machine in PLATFORMS else "x86_64")
    args = ap.parse_args()
    global PLATFORM
    PLATFORM = PLATFORMS[args.arch]
    # Without KVM the VM is emulated (several times slower): stretch the waits, and
    # skip the install, which would take hours.
    args.slow = 1 if KVM else 6
    print(f"{args.arch} VMs, {'KVM' if KVM else 'emulated (no /dev/kvm)'}", flush=True)
    if args.install and not KVM:
        print("  no KVM: skipping the install test (it needs hardware virtualization to finish in time)")
        args.install = False
    args.iso = args.iso.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out.resolve()

    shots = [] if args.skip_real_boot else boot_real(args, out)
    res = Results()
    disk = None
    if args.install:
        disk = out / "installed-disk.qcow2"
        disk.unlink(missing_ok=True)
        subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(disk), args.disk_size], check=True)
    installed = boot_live(args, out, res, disk)
    if args.install and installed:
        boot_installed(args, out, res, disk)
    if disk and disk.exists():
        disk.unlink()                                   # 10+ GB; not worth keeping

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
