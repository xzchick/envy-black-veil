#!/usr/bin/env python3
"""Boot the ENVY BLACK VEIL ISO in a VM and check it, the way a person would.

Boot 1, the real path: UEFI firmware -> the ISO's own boot loader -> the live
desktop. Screenshots every few seconds record the boot menu, the splash and the
desktop.

Boot 2, the same kernel and initrd with a serial console added, so this script
can log in as the live user and check the system from the inside: the desktop is
running, SELinux and the firewall are on, nothing listens on the network, and the
ENVY identity (splash, login theme, colours, wallpaper, installer, envy-tools) is
in place.

Writes screenshots, the serial log, results.json and a Markdown summary to --out.
Exits non-zero if any required check fails. Needs qemu-system-x86_64, OVMF,
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

OVMF_CODE = ["/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_CODE.fd"]
OVMF_VARS = ["/usr/share/OVMF/OVMF_VARS_4M.fd", "/usr/share/OVMF/OVMF_VARS.fd"]


def first_existing(paths):
    for p in paths:
        if Path(p).exists():
            return p
    raise SystemExit(f"none of these exist: {paths}")


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
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(str(path))
            return s
        except OSError:
            s.close()
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


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
        except RuntimeError:
            ppm = png.with_suffix(".ppm")
            try:
                self.cmd("screendump", filename=str(ppm))
                ppm_to_png(ppm, png)
                ppm.unlink()
                return True
            except Exception as exc:                     # noqa: BLE001
                print(f"  screenshot failed: {exc}")
                return False

    def quit(self):
        try:
            self.cmd("quit")
        except Exception:                                # noqa: BLE001
            pass


def start_qemu(args, run_dir: Path, name: str, extra: list[str]) -> tuple[subprocess.Popen, QMP]:
    qmp_path = SOCKETS / f"{name}.qmp"
    qmp_path.unlink(missing_ok=True)
    cmd = ["qemu-system-x86_64", "-name", f"envy-{name}", "-enable-kvm", "-cpu", "host", "-machine", "q35",
           "-m", str(args.mem), "-smp", str(args.cpus),
           "-vga", "none", "-device", "virtio-vga,edid=on,xres=1600,yres=900",
           "-display", "none", "-nic", "user,model=virtio-net-pci",
           "-drive", f"file={args.iso},media=cdrom,readonly=on",
           "-qmp", f"unix:{qmp_path},server=on,wait=off"] + extra
    log = open(run_dir / f"{name}-qemu.log", "w")
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    return proc, QMP(qmp_path)


# ----- boot 1: the real boot path ---------------------------------------------

def boot_real(args, out: Path) -> list[str]:
    print("== Boot 1: UEFI firmware -> the ISO's boot loader -> live desktop")
    vars_copy = out / "OVMF_VARS.fd"
    shutil.copy(first_existing(OVMF_VARS), vars_copy)
    proc, qmp = start_qemu(args, out, "boot1", [
        "-drive", f"if=pflash,format=raw,readonly=on,file={first_existing(OVMF_CODE)}",
        "-drive", f"if=pflash,format=raw,file={vars_copy}"])
    shots, start = [], time.monotonic()
    try:
        while time.monotonic() - start < args.real_boot_seconds:
            t = int(time.monotonic() - start)
            png = out / f"boot1-{t:03d}s.png"
            if qmp.screenshot(png):
                shots.append(png.name)
            if proc.poll() is not None:
                print("  QEMU exited early")
                break
            time.sleep(args.shot_every)
    finally:
        qmp.quit()
        proc.wait(timeout=30)
    print(f"  {len(shots)} screenshots")
    return shots


# ----- boot 2: serial console checks ---------------------------------------------

class Serial:
    def __init__(self, path: Path, log: Path):
        self.sock = connect_unix(path)
        self.sock.setblocking(False)
        self.buf = ""
        self.count = 0
        self.log = open(log, "a", encoding="utf-8", errors="replace")

    def _pump(self, wait: float) -> None:
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
            self._pump(0.5)
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
            self._pump(0.5)
        return None, self.buf.strip()


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


def boot_checks(args, out: Path) -> list[dict]:
    print("== Boot 2: the same kernel with a serial console, then checks from the inside")
    kernel, initrd, volid = iso_paths(args.iso)
    print(f"  kernel {kernel}, initrd {initrd}, volume '{volid}'")
    for src, dst in ((kernel, "vmlinuz"), (initrd, "initrd.img")):
        subprocess.run(["xorriso", "-osirrox", "on", "-indev", str(args.iso), "-extract", src, str(out / dst)],
                       check=True, capture_output=True)
    serial_path = SOCKETS / "serial.sock"
    serial_path.unlink(missing_ok=True)
    cmdline = (f"root=live:CDLABEL={volid} rd.live.image quiet rhgb console=tty0 console=ttyS0,115200n8 "
               "plymouth.ignore-serial-consoles systemd.journald.forward_to_console=0")
    proc, qmp = start_qemu(args, out, "boot2", [
        "-kernel", str(out / "vmlinuz"), "-initrd", str(out / "initrd.img"), "-append", cmdline,
        "-chardev", f"socket,id=ser0,path={serial_path},server=on,wait=off", "-serial", "chardev:ser0"])
    console = Serial(serial_path, out / "serial.log")
    results: list[dict] = []

    def record(name, ok, detail, required=True):
        results.append({"check": name, "ok": bool(ok), "required": required, "detail": detail.strip()[:2000]})
        print(f"  {'PASS' if ok else ('FAIL' if required else 'INFO')}  {name}: {detail.strip()[:160]}")

    try:
        started = time.monotonic()
        logged_in = False
        for attempt in range(12):
            if not console.expect(r"login:\s*$", 600 if attempt == 0 else 60):
                break
            console.send("liveuser\n")
            m = console.expect(r"(Password:\s*$|\$\s*$|Login incorrect)", 30)
            if m and m.group(1).startswith("Password"):
                console.send("\n")
                m = console.expect(r"(\$\s*$|Login incorrect)", 30)
            if m and "$" in m.group(1):
                logged_in = True
                break
            time.sleep(5)                                # livesys may still be creating liveuser
        record("boots to a login on the serial console", logged_in,
               f"after {int(time.monotonic() - started)}s" if logged_in else "no login prompt / login failed")
        if not logged_in:
            return results
        console.send("export PS1='$ ' TERM=dumb; stty -echo; unset PROMPT_COMMAND\n")
        console.expect(r"\$\s*$", 10)

        def check(name, command, ok=lambda rc, o: rc == 0, required=True, timeout=60):
            rc, output = console.run(command, timeout)
            record(name, rc is not None and ok(rc, output), output if output else f"exit {rc}", required)
            return rc, output

        # Wait for the live desktop: SDDM logs liveuser into Plasma.
        deadline = time.monotonic() + 420
        while time.monotonic() < deadline:
            rc, _ = console.run("pgrep -u liveuser -x plasmashell >/dev/null", 20)
            if rc == 0:
                break
            time.sleep(5)
        check("Plasma desktop is running for the live user", "pgrep -u liveuser -a plasmashell")
        time.sleep(args.settle)
        if qmp.screenshot(out / "desktop.png"):
            print("  saved desktop.png")

        check("system state", "systemctl is-system-running",
              ok=lambda rc, o: o.strip() in ("running", "degraded"), required=False)
        check("failed units", "systemctl --failed --no-legend --plain | head -20", required=False)
        check("graphical target reached", "systemctl is-active graphical.target", ok=lambda rc, o: o == "active")
        check("SDDM login manager active", "systemctl is-active sddm", ok=lambda rc, o: o == "active")
        check("desktop session type", "loginctl show-session $(loginctl list-sessions --no-legend | awk '$3==\"liveuser\" && $0 !~ /ttyS0/ {print $1; exit}') -p Type -p Desktop",
              required=False)
        check("SELinux is enforcing", "getenforce", ok=lambda rc, o: o == "Enforcing")
        check("firewall is running", "firewall-cmd --state 2>/dev/null || sudo -n firewall-cmd --state",
              ok=lambda rc, o: o.endswith("running"))
        check("firewall opens no services or ports",
              "sudo -n firewall-cmd --list-services; sudo -n firewall-cmd --list-ports",
              ok=lambda rc, o: rc == 0 and set(o.split()) <= {"dhcpv6-client"})
        check("SSH server is off", "systemctl is-enabled sshd 2>&1; systemctl is-active sshd 2>&1",
              ok=lambda rc, o: "enabled" not in o.split() and "active" not in o.split())
        check("nothing listens on the network (TCP)",
              "ss -H -tln | awk '{print $4}' | grep -v -E '^(127\\.|\\[::1\\]|::1)' || true",
              ok=lambda rc, o: o.strip() == "")
        check("UDP sockets bound beyond loopback (DHCP client etc.)",
              "ss -H -uln | awk '{print $4}' | grep -v -E '^(127\\.|\\[::1\\]|::1)' || true", required=False)
        check("ENVY packages installed", "rpm -q envy-black-veil-theme envy-black-veil-release")
        check("ENVY release file", "cat /etc/envy-black-veil-release", ok=lambda rc, o: "ENVY BLACK VEIL" in o)
        check("ENVY boot splash is the default", "plymouth-set-default-theme", ok=lambda rc, o: o == "envy-black-veil")
        check("ENVY login theme selected", "grep -h '^Current=' /etc/sddm.conf.d/*.conf",
              ok=lambda rc, o: "envy-black-veil" in o)
        check("ENVY colour scheme for the user", "kreadconfig6 --file kdeglobals --group General --key ColorScheme",
              ok=lambda rc, o: o == "EnvyNeon")
        check("ENVY wallpaper on the desktop",
              "grep -h -A3 'Wallpaper..org.kde.image..General' ~/.config/plasma-org.kde.plasma.desktop-appletsrc",
              ok=lambda rc, o: "EnvyBlackVeil" in o)
        check("hostname", "hostname", required=False)
        check("installer is on the menu", "test -x /usr/bin/liveinst && grep -m1 '^Name=' /usr/share/applications/liveinst.desktop",
              ok=lambda rc, o: rc == 0 and "ENVY BLACK VEIL" in o)
        check("installer is on the live desktop", "ls ~/Desktop", ok=lambda rc, o: "liveinst.desktop" in o)
        check("envy-tools works", "envy-tools list | head -6")
        check("ENVY app runtime (Python, PyQt6, cryptography)",
              "python3 -c 'import PyQt6.QtWidgets, cryptography; print(\"ok\")'", ok=lambda rc, o: o.endswith("ok"))
        check("base system", "head -3 /etc/os-release", required=False)
        check("kernel", "uname -r", required=False)
    finally:
        qmp.quit()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mem", type=int, default=4096)
    ap.add_argument("--cpus", type=int, default=2)
    ap.add_argument("--real-boot-seconds", type=int, default=300)
    ap.add_argument("--shot-every", type=int, default=6)
    ap.add_argument("--settle", type=int, default=25, help="seconds to let the desktop settle before its screenshot")
    ap.add_argument("--skip-real-boot", action="store_true")
    args = ap.parse_args()
    args.iso = args.iso.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out.resolve()

    shots = [] if args.skip_real_boot else boot_real(args, out)
    results = boot_checks(args, out)
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
