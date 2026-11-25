#!/usr/bin/env bash
# build-in-vm.sh — build the ENVY BLACK VEIL ISO inside a throwaway AlmaLinux 10 VM.
#
# CI runs this on an Ubuntu machine with KVM (see .github/workflows/iso.yml). It
# boots AlmaLinux's official 10 cloud image (checksum-verified) with QEMU, logs in
# over SSH with a one-time key, copies this repository in, runs
# build/build-iso.sh there, and copies the ISO back out. Nothing touches the host
# beyond $VMDIR and $OUT.
#
# Needs: qemu-system-x86 qemu-utils cloud-image-utils openssh-client curl, and /dev/kvm.
# Env: VMDIR (VM files), OUT (results), VM_MEM (MiB), VM_CPUS, VM_DISK.
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
VMDIR="${VMDIR:-$HERE/.vm}"
OUT="${OUT:-$HERE/output}"
VM_MEM="${VM_MEM:-12288}"
VM_CPUS="${VM_CPUS:-$(nproc)}"
VM_DISK="${VM_DISK:-80G}"
IMAGES="https://repo.almalinux.org/almalinux/10/cloud/x86_64/images"
IMAGE="AlmaLinux-10-GenericCloud-latest.x86_64.qcow2"
PORT=2222

say() { printf "\033[38;5;51m==>\033[0m %s\n" "$*"; }
die() { printf "\033[38;5;205mbuild-in-vm:\033[0m %s\n" "$*" >&2; exit 1; }

[ -w /dev/kvm ] || die "/dev/kvm isn't usable; this needs hardware virtualization."
mkdir -p "$VMDIR" "$OUT"
cd "$VMDIR" || die "can't enter $VMDIR"

say "Downloading AlmaLinux's official 10 cloud image"
curl -fsSL --retry 3 -o "$IMAGE" "$IMAGES/$IMAGE" || die "download failed"
curl -fsSL --retry 3 -o CHECKSUM "$IMAGES/CHECKSUM" || die "checksum download failed"
grep -E "  ${IMAGE}\$" CHECKSUM | sha256sum -c - || die "the cloud image doesn't match AlmaLinux's published checksum"

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
cloud-localds seed.img user-data meta-data || die "cloud-localds failed"
rm -f disk.qcow2
qemu-img create -q -f qcow2 -F qcow2 -b "$IMAGE" disk.qcow2 "$VM_DISK" || die "qemu-img failed"

say "Booting the VM (${VM_CPUS} CPUs, ${VM_MEM} MiB)"
qemu-system-x86_64 -name envy-builder -enable-kvm -cpu host -machine q35 \
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
vm 'sudo cloud-init status --wait >/dev/null 2>&1; . /etc/os-release; echo "VM: $PRETTY_NAME, $(nproc) CPUs"; free -h | head -2; df -h /'

say "Copying the repository into the VM"
tar -C "$HERE" --exclude=./.git --exclude=./output --exclude=./.vm -czf - . \
    | vm 'rm -rf src && mkdir src && tar -xzf - -C src' || die "copying the repository failed"

say "Installing the build tools in the VM (lorax, anaconda, rpm-build, …)"
vm 'sudo dnf -y -q install epel-release && sudo dnf -y install lorax lorax-templates-almalinux anaconda rpm-build createrepo_c pykickstart librsvg2-tools grub2-tools-extra dejavu-sans-fonts libblockdev-nvme zstd' \
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
    ( cd "$OUT" && sha256sum -c envy-black-veil-*.iso.sha256 ) || die "the ISO changed on the way out"
    ls -la "$OUT"
else
    die "the ISO build failed (exit $status); see build.log and livemedia-logs.tar.gz"
fi
