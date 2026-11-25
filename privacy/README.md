# Privacy defaults

Installed by the `envy-black-veil-release` package, so the live system and every
installed system get them. The kickstart also turns off two timers and DNF's
weekly count (see `kickstart/envy-black-veil.ks`), and CI checks all of it.

| File | Installed as | What it does |
| --- | --- | --- |
| `90-envy-privacy.conf` | `/etc/NetworkManager/conf.d/90-envy-privacy.conf` | No connectivity check: NetworkManager stops fetching a vendor's test page every few minutes. |
| `firefox-policies.json` | `/etc/firefox/policies/policies.json` | Firefox: no telemetry, studies, Pocket, sponsored tiles or suggestions, and no recommendations. Settings you can change stay changeable; see `about:policies`. |
| `anaconda-90-envy-privacy.conf` | `/etc/anaconda/conf.d/90-envy-privacy.conf` | The installer doesn't send your IP address to a geolocation service to guess your language and time zone. |

What stays on: security and time. `dnf` still checks AlmaLinux's and EPEL's
mirrors for updates, chrony keeps the clock right, and Firefox keeps Safe
Browsing. Turn the rest back on with the comments in each file.
