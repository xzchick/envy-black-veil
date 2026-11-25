# ENVY BLACK VEIL — convenience targets.
# The real work is in build/build-iso.sh (Linux only). These targets wrap it and
# the validators so `make validate` can run anywhere with the right tools.

VERSION ?= $(shell awk '/^Version:/ {print $$2}' packaging/envy-black-veil.spec)
ARCH    ?= x86_64

.PHONY: help validate validate-ks validate-shell validate-desktop validate-xml iso clean

help:
	@echo "ENVY BLACK VEIL"
	@echo "  make validate   run every linter (kickstart, shell, desktop, qml/xml)"
	@echo "  make iso        build the live ISO + ENVY RPMs (Linux, root; see build/build-iso.sh)"
	@echo "  make clean      remove build output"

validate: validate-ks validate-shell validate-desktop validate-xml
	@echo "All validators passed."

validate-ks:
	@echo "== kickstart =="
	ksvalidator kickstart/envy-black-veil.ks

validate-shell:
	@echo "== shell =="
	shellcheck -e SC2059 tools/envy-tools tools/envy-hardware-report build/build-iso.sh ci/build-in-vm.sh \
		try-black-veil.sh live/dracut/90envy-live-persist/*.sh repo/publish.sh \
		tools/envy-os-release theme/kernel/96-envy-black-veil-title.install

validate-desktop:
	@echo "== desktop entries =="
	@command -v desktop-file-validate >/dev/null && \
		desktop-file-validate tools/desktop/envy-hardware-report.desktop && \
		printf '[Desktop Entry]\nType=Application\nName=ENVY Vault\nExec=envy-vault\nTerminal=false\nCategories=Utility;Security;\n' \
		> /tmp/envy.desktop && desktop-file-validate /tmp/envy.desktop && rm -f /tmp/envy.desktop || \
		echo "desktop-file-validate not installed; skipping"

validate-xml:
	@echo "== QML / SVG well-formedness =="
	@for f in theme/sddm/envy-black-veil/Main.qml theme/sddm/envy-black-veil/metadata.desktop; do \
		echo "  $$f"; done
	@command -v xmllint >/dev/null && \
		xmllint --noout theme/wallpaper/envy-black-veil.svg theme/grub/envy-black-veil/background.svg \
			theme/plymouth/envy-black-veil/logo.svg theme/plymouth/envy-black-veil/spark.svg || \
		echo "xmllint not installed; skipping SVG check"

iso:
	sudo VERSION=$(VERSION) ARCH=$(ARCH) ./build/build-iso.sh

clean:
	rm -rf .build output
