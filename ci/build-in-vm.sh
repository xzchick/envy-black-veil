#!/usr/bin/env bash
# build-in-vm.sh — build the ENVY BLACK VEIL ISO inside a throwaway AlmaLinux 10 VM.
#
# Works on Linux (KVM) and macOS (Apple's Hypervisor framework) and builds for the
# computer's own architecture: the x86_64 ISO on Intel/AMD machines, the aarch64
# ISO on ARM ones such as Apple Silicon Macs. (On Windows, run it in WSL2, which
# offers KVM on Windows 11.) CI runs it on Ubuntu with KVM (.github/workflows/iso.yml).
#
# It boots AlmaLinux's official 10 cloud image (checksum-verified) with QEMU, logs
# in over SSH with a one-time key, copies this repository in, runs
# build/build-iso.sh there, and copies the ISO back out. Nothing touches the host
# beyond $VMDIR and $OUT.
#
# Needs: QEMU and qemu-img (with UEFI firmware for aarch64), curl, ssh, and one of
# cloud-localds, hdiutil (macOS), xorriso, genisoimage or mkisofs for the
# cloud-init seed.   macOS: brew install qemu
#                     Debian/Ubuntu: sudo apt install qemu-system qemu-utils cloud-image-utils
# Env: VMDIR (VM files), OUT (results), VM_MEM (MiB), VM_CPUS, VM_DISK, VM_SSH_PORT.
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
VMDIR="${VMDIR:-$HERE/.vm}"
OUT="${OUT:-$HERE/output}"
VM_MEM="${VM_MEM:-12288}"
VM_CPUS="${VM_CPUS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
VM_DISK="${VM_DISK:-80G}"
PORT="${VM_SSH_PORT:-2222}"

say() { printf "\033[38;5;51m==>\033[0m %s\n" "$*"; }
die() { printf "\033[38;5;205mbuild-in-vm:\033[0m %s\n" "$*" >&2; exit 1; }
sha256check() { if command -v sha256sum >/dev/null 2>&1; then sha256sum -c "$@"; else shasum -a 256 -c "$@"; fi; }

case "$(uname -m)" in
    x86_64 | amd64)  ARCH=x86_64 ;;
    aarch64 | arm64) ARCH=aarch64 ;;
    *) die "unsupported machine $(uname -m): build on an x86_64 or aarch64 computer" ;;
esac
IMAGES="https://repo.almalinux.org/almalinux/10/cloud/$ARCH/images"
IMAGE="AlmaLinux-10-GenericCloud-latest.$ARCH.qcow2"

# Hardware virtualization: KVM on Linux, the Hypervisor framework on macOS.
case "$(uname -s)" in
    Linux)
        [ -w /dev/kvm ] || die "/dev/kvm isn't usable; this needs hardware virtualization (are you in the kvm group?)."
        accel=(-accel kvm -cpu host) ;;
    Darwin)
        [ "$(sysctl -n kern.hv_support 2>/dev/null)" = 1 ] || die "this Mac doesn't offer hardware virtualization."
        accel=(-accel hvf -cpu host) ;;
    *) die "build on Linux or macOS (on Windows, in WSL2)" ;;
esac

mkdir -p "$VMDIR" "$OUT"
cd "$VMDIR" || die "can't enter $VMDIR"

if [ "$ARCH" = x86_64 ]; then
    qemu="qemu-system-x86_64"
    machine=(-machine q35)
    firmware=()                                    # the cloud image boots with QEMU's default BIOS
else
    qemu="qemu-system-aarch64"
    machine=(-machine virt)
    share="$(dirname "$(command -v "$qemu" || echo /usr/bin/"$qemu")")/../share/qemu"
    code=""
    for f in "$share/edk2-aarch64-code.fd" /usr/share/AAVMF/AAVMF_CODE.fd \
             /usr/share/edk2/aarch64/QEMU_EFI-pflash.raw /usr/share/qemu/edk2-aarch64-code.fd; do
        [ -f "$f" ] && { code="$f"; break; }
    done
    [ -n "$code" ] || die "no aarch64 UEFI firmware found (macOS: brew install qemu · Debian/Ubuntu: qemu-efi-aarch64 · Fedora: edk2-aarch64)"
    # A blank NVRAM the size of the firmware image; the firmware formats it on first boot.
    rm -f efivars.fd
    qemu-img create -q -f raw efivars.fd "$(wc -c < "$code" | tr -d ' ')" || die "qemu-img failed"
    firmware=(-drive "if=pflash,format=raw,readonly=on,file=$code" -drive "if=pflash,format=raw,file=$VMDIR/efivars.fd")
fi
command -v "$qemu" >/dev/null || die "$qemu isn't installed (macOS: brew install qemu · Debian/Ubuntu: sudo apt install qemu-system)"

say "Getting AlmaLinux's official 10 cloud image ($ARCH)"
curl -fsSL --retry 3 -o CHECKSUM "$IMAGES/CHECKSUM" || die "checksum download failed"
# A copy from an earlier run is reused only while it still matches the published checksum.
grep -E "  ${IMAGE}\$" CHECKSUM | sha256check - >/dev/null 2>&1 \
    || curl -fsSL --retry 3 -o "$IMAGE" "$IMAGES/$IMAGE" || die "download failed"
grep -E "  ${IMAGE}\$" CHECKSUM | sha256check - || die "the cloud image doesn't match AlmaLinux's published checksum"

say "Preparing the build VM (one-time SSH key, cloud-init seed, ${VM_DISK} disk)"
rm -f key key.pub
ssh-keygen -q -t ed25519 -N '' -f key
cat > user-data <<EOF
#cloud-config
users:
  - name: builder
    groups: wheel
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    shell: /bin/bash
    ssh_authorized_keys:
      - $(cat key.pub)
growpart:
  mode: auto
  devices: ["/"]
EOF
printf 'instance-id: envy-builder\nlocal-hostname: envy-builder\n' > meta-data
rm -rf seed.img seed
if command -v cloud-localds >/dev/null 2>&1; then
    cloud-localds seed.img user-data meta-data
elif command -v hdiutil >/dev/null 2>&1; then          # macOS
    mkdir seed && cp user-data meta-data seed/ \
        && hdiutil makehybrid -quiet -iso -joliet -default-volume-name cidata -o seed.iso seed \
        && mv seed.iso seed.img
else
    mkiso="$(command -v xorriso || command -v genisoimage || command -v mkisofs)" \
        || die "no tool to make the cloud-init seed (cloud-localds, hdiutil, xorriso, genisoimage or mkisofs)"
    case "$mkiso" in *xorriso) mkiso="$mkiso -as mkisofs" ;; esac
    $mkiso -quiet -V cidata -J -r -o seed.img user-data meta-data
fi
[ -s seed.img ] || die "making the cloud-init seed failed"
rm -f disk.qcow2
qemu-img create -q -f qcow2 -F qcow2 -b "$IMAGE" disk.qcow2 "$VM_DISK" || die "qemu-img failed"

say "Booting the VM ($ARCH, ${accel[1]}, ${VM_CPUS} CPUs, ${VM_MEM} MiB)"
rm -f vm.pid
"$qemu" -name envy-builder "${accel[@]}" "${machine[@]}" ${firmware[@]+"${firmware[@]}"} \
    -smp "$VM_CPUS" -m "$VM_MEM" \
    -drive if=virtio,file=disk.qcow2,cache=unsafe,discard=unmap \
    -drive if=virtio,format=raw,file=seed.img \
    -nic "user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:${PORT}-:22" \
    -display none -serial "file:$VMDIR/console.log" \
    -daemonize -pidfile "$VMDIR/vm.pid" || die "QEMU failed to start"

ssh_opts=(-i "$VMDIR/key" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
          -o LogLevel=ERROR -o ConnectTimeout=5 -o ServerAliveInterval=30 -o ServerAliveCountMax=20)
vm() { ssh "${ssh_opts[@]}" -p "$PORT" builder@127.0.0.1 "$@"; }
stop_vm() {
    vm 'sudo systemctl poweroff' >/dev/null 2>&1
    sleep 5
    [ -f "$VMDIR/vm.pid" ] && kill "$(cat "$VMDIR/vm.pid")" 2>/dev/null
}
trap stop_vm EXIT

for _ in $(seq 1 120); do vm true 2>/dev/null && break; sleep 5; done
vm true || { tail -n 60 "$VMDIR/console.log"; die "the VM never answered on SSH"; }
# Commands in single quotes run inside the VM, so they expand there, on purpose.
# shellcheck disable=SC2016
vm 'sudo cloud-init status --wait >/dev/null 2>&1; . /etc/os-release; echo "VM: $PRETTY_NAME ($(uname -m)), $(nproc) CPUs"; free -h | head -2; df -h /'

say "Copying the repository into the VM"
# COPYFILE_DISABLE and --no-xattrs keep macOS's resource forks and file tags out.
COPYFILE_DISABLE=1 tar -C "$HERE" --no-xattrs --exclude=./.git --exclude=./output --exclude=./.vm \
    --exclude=.DS_Store --exclude=__pycache__ -czf - . \
    | vm 'rm -rf src && mkdir src && tar -xzf - -C src' || die "copying the repository failed"

say "Installing the build tools in the VM (lorax, anaconda, rpm-build, …)"
vm 'sudo dnf -y -q install epel-release && sudo dnf -y install lorax lorax-templates-almalinux anaconda rpm-build createrepo_c pykickstart librsvg2-tools grub2-tools-extra dejavu-sans-fonts dejavu-sans-mono-fonts libblockdev-nvme zstd' \
    > "$OUT/vm-setup.log" 2>&1 || { tail -n 40 "$OUT/vm-setup.log"; die "installing the build tools failed"; }

say "Building the ISO in the VM (this is the long part)"
vm 'cd src && sudo ./build/build-iso.sh' 2>&1 | tee "$OUT/build.log"
status=${PIPESTATUS[0]}

say "Collecting the build logs"
vm 'sudo tar -C src/output -czf - logs 2>/dev/null' > "$OUT/livemedia-logs.tar.gz" || true

if [ "$status" -eq 0 ]; then
    say "Copying the ISO out of the VM"
    scp "${ssh_opts[@]}" -P "$PORT" "builder@127.0.0.1:src/output/envy-black-veil-*" "$OUT/" \
        || die "copying the ISO out failed"
    ( cd "$OUT" && sha256check envy-black-veil-*-"$ARCH".iso.sha256 ) || die "the ISO changed on the way out"
    ls -la "$OUT"
else
    die "the ISO build failed (exit $status); see build.log and livemedia-logs.tar.gz"
fi
