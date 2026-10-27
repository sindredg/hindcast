# Case charts

Cloudflare Radar images shown next to a case's evidence. Unlike the status pages and postmortems, these are committed: Radar's downloadable graphs and images are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Each image is unchanged from the download. Its source page, retrieval time, and SHA-256 are in [`data/cases.yaml`](../cases.yaml) (kind `chart`).

| Image | Source | Licence | Attribution |
|---|---|---|---|
| [`cloudflare-2025-11-18/radar-http-traffic.png`](cloudflare-2025-11-18/radar-http-traffic.png) | [Radar traffic, worldwide, 2025-11-18](https://radar.cloudflare.com/traffic?dateStart=2025-11-18&dateEnd=2025-11-18) | CC BY 4.0 | Cloudflare Radar, "HTTP traffic worldwide" |
| [`cloudflare-2026-02-20/radar-announced-ipv4.png`](cloudflare-2026-02-20/radar-announced-ipv4.png) | [Radar routing, AS13335, 2026-02-20](https://radar.cloudflare.com/routing/as13335?dateStart=2026-02-20&dateEnd=2026-02-20) | CC BY 4.0 | Cloudflare Radar, "Announced IP address space from AS13335", IPv4 /24s |
| [`cloudflare-2026-02-20/radar-bgp-announcements.png`](cloudflare-2026-02-20/radar-bgp-announcements.png) | [Radar routing, AS13335, 2026-02-20](https://radar.cloudflare.com/routing/as13335?dateStart=2026-02-20&dateEnd=2026-02-20) | CC BY 4.0 | Cloudflare Radar, "BGP announcements from AS13335" |

Radar offers whole UTC days only, even when the page address asks for times. A view is used only if it carries no annotation that names a cause. The development case's views end before its resolved update. The 2025-11-18 view runs about four hours past the resolved update; those hours show traffic back near the week before. Its shaded band is Radar's own marking of the event, without text.
