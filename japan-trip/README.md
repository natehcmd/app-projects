# japan-trip

Interactive Japan trip planner built for a father-son trip — Nate & Dad's Japan 2026.

**Live site:** https://natehcmd.github.io/japan-trip/

## Pages

- **[index.html](https://natehcmd.github.io/japan-trip/)** — the day planner. Browse 50+ activities across Tokyo, Kyoto and Osaka, filter by city or type, assign them to any of 10 days, and watch the budget and a live Leaflet route map update. Plans persist in `localStorage`. Includes a small offline chatbot that answers common trip questions.
- **[overview.html](https://natehcmd.github.io/japan-trip/overview.html)** — the trip overview. Month-by-month "when to go" guide, the three-city route with a day-split calculator, a full map of every activity, and the pre-flight checklist (JR Pass, IDP, sell-out bookings).

## Run locally

No build step — it's plain HTML/CSS/JS:

```sh
python3 -m http.server 8000
# then open http://localhost:8000/
```

Or just open `index.html` directly in a browser. (Maps and fonts load from CDNs, so you need to be online.)

## Stack

- Pure HTML/CSS/JS — no build step, no dependencies to install
- [Leaflet 1.9.4](https://leafletjs.com/) (unpkg CDN) + OpenStreetMap tiles for maps
- Google Fonts: Shippori Mincho + Zen Kaku Gothic New
- Washi-paper aesthetic with automatic dark mode (`prefers-color-scheme`), reduced-motion support, and visible focus styles

## Deployment

Pushes to `main` deploy automatically to GitHub Pages via `.github/workflows/pages.yml`.

## Why I built it

Wanted a single shareable page we could both pull up on our phones during the trip — no app installs, no logins.
