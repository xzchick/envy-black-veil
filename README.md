<p align="center">
  <img src="https://raw.githubusercontent.com/xzchick/xzchick/main/envy-banner-animated.svg" width="100%" alt="ENVY neon galaxy banner" />
</p>

# ENVY BLACK VEIL

**A Linux world of my own.** Custom desktop tools, privacy workflows, recovery maps, and a neon soul.

Created by [Envy (@xzchick)](https://github.com/xzchick).

> **IN DEVELOPMENT · Public project preview**
>
> This repository introduces the project and shows development screenshots. Source code and installation downloads are not published here yet. It is not a stable release.

## What is BLACK VEIL?

BLACK VEIL is my custom **AlmaLinux + KDE Plasma** environment and Python/Qt application suite. It brings system inspection, encrypted backups, local planning, privacy utilities, and disk-image recovery into a shared dark interface with pink and cyan accents.

The development source reviewed for this overview is **1.5.0 dev9**, targeting **AlmaLinux 10.2 x86_64 and KDE Plasma 6**. Desktop, installer, and end-to-end workflow acceptance are ongoing.

## See the builds

### RECLAIM · Recovery, one block at a time

![Reclaim development screenshot](https://raw.githubusercontent.com/xzchick/xzchick/main/reclaim-development.png)

A **1,024-block map** follows GNU ddrescue map updates: pink for fully read ranges, red for errors or retries, and black for untried ranges. The development workflow uses read-only disk-image files and a new output on a separate filesystem. PhotoRec carving is a separate workflow.

*Screenshot: synthetic display test with fabricated error ranges. Map colors describe byte reads, not verified recovered files. This is not a real disk recovery result.*

### COMMAND CENTER · Find the next tool

![Command Center development screenshot](https://raw.githubusercontent.com/xzchick/xzchick/main/command-center-development.png)

A searchable launch point for suite applications, system overviews, explicit actions, and command output.

*Screenshot: development interface in its idle state.*

### OPS DESK · Keep the plan together

![Ops Desk development screenshot](https://raw.githubusercontent.com/xzchick/xzchick/main/ops-desk-development.png)

Encrypted local plans with role aliases, assignments, progress, scheduled check-ins, and authenticated handoff files. Each edit saves a new encrypted revision. Check-ins are local; the application does not send messages or run background monitoring.

*Screenshot: sample task and synthetic test data.*

## Inside the suite

| Tool | Purpose |
| :--- | :--- |
| **Guardian** | Inspect SELinux, firewall state, failed services, listening sockets, and storage encryption visibility. Unavailable observations remain unknown. |
| **Restore** | Restic encrypted backups, snapshot browsing, repository checks, and recovery to a new destination. |
| **Vault** | Passphrase-protected file encryption and decryption to separate destinations. |
| **Veil** | Encrypted file/folder packages in supported image, audio, and video carriers. |
| **Network Lab** | Local interfaces, routes, listeners, VPN observations, and access to KDE's connection editor. |
| **Forge** | Rootless Podman image/container management and restricted experimental workspaces. |
| **Oracle** | Ollama-powered local model prompts, explicit model downloads, and optional encrypted-history setup. |
| **Evidence Vault** | Case manifests, copied-file intake, and integrity verification. |
| **Device Center** | Hardware inventory and available thermal/GPU observations. |
| **Package Center** | Package inventories, RPM searches, and interactive installation from configured repositories. |
| **Orbit** | Orbital-element downloads on request and offline satellite predictions using Skyfield. |
| **Purge** | Preview eligible old cache files and move a reviewed item to Trash. |

## Availability & requirements

There is **no public installer or source checkout in this repository yet**. Screenshots show development interfaces, not a finished downloadable operating system.

The development environment uses Python 3.12+, Qt bindings, and a Linux desktop. Individual workflows require their own dependencies, including GNU ddrescue/PhotoRec, Restic, Podman, Ollama, or Skyfield. Applications run as the desktop user; privileged operations use separate authorization flows.

For context, these are commands used with the existing development source; they are **not installation commands for this preview repository**:

```sh
python3 -m envy.cli --help
python3 -m envy.cli gui reclaim
python3 -m unittest discover -s tests -v
```

Exact setup steps and supported downloads will accompany a reviewed source or release publication.

## Roadmap

- [ ] Complete installed-system and KDE Plasma acceptance in a disposable Linux VM.
- [ ] Verify the dev9 package lifecycle and prepare matching installation media; earlier dev8 media does not include the dev9 Reclaim GUI.
- [ ] Validate backup, recovery, snapshot, reboot, and rescue workflows end to end.
- [ ] Test display behavior and supported hardware on explicitly selected test targets.
- [ ] Review source files for private data and resolve redistribution/licensing questions before publication.
- [ ] Establish production signing, release/update hosting, and independent security review.
- [ ] Publish versioned setup instructions, known limitations, and verified release artifacts.

There is no release date promised yet. Current limitations include no automatic interrupted-job resume in Reclaim and no physical failing-drive acquisition through its image-recovery interface. Full installed-system acceptance remains unfinished.

## Follow the project

Follow [@xzchick](https://github.com/xzchick) for updates. Suggestions and questions about the preview are welcome in this repository's Issues.

<p align="center"><code>printf '%s\n' 'curiosity → experiments → useful tools'</code></p>
