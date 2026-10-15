# drogue brand assets

All artwork below was split out of the master brand board.
White artwork is transparent-background; `-on-dark` files keep the
board's dark (`#0B0F14`) background baked in.

## Logo

| File | Use it when… |
|------|--------------|
| `logo-lockup-white.png` / `logo-lockup-white.svg` | Full lockup (mark + `drogue` + `CONTROL • DEFEND • OPTIMIZE`) on **dark** surfaces - README hero (dark mode), docs hero, social cards |
| `logo-lockup-black.png` | Full lockup on **light** surfaces - README hero (light mode), PyPI page, slides |
| `logo-lockup-on-dark.png` | Same lockup with the `#0B0F14` background baked in, for places that can't do transparency |
| `logo-mark-white.png` / `logo-mark-white.svg` | Standalone `D` mark on **dark** surfaces - avatars, badges, section headers |
| `logo-mark-black.png` | Standalone mark on **light** surfaces |
| `logo-mark-on-dark.png` | Mark with dark background baked in |
| `social-preview.png` | 1200×630 social / OpenGraph card (`#0B0F14` + blue glow + lockup) |

SVG files are raster-embedded traces of the board artwork, not
hand-drawn vectors - prefer the PNGs for print.

## Favicons / app icons (`../favicons/`)

| File | Use |
|------|-----|
| `favicon.svg` | Docs site favicon + modern browsers (dark rounded tile + white mark) |
| `favicon.ico` | Multi-size fallback (16/32/48) for legacy browsers |
| `favicon-16x16.png`, `favicon-32x32.png`, `favicon-48x48.png` | Standard `<link rel="icon">` sizes |
| `apple-touch-icon.png` | iOS home-screen icon (180×180) |
| `android-chrome-192x192.png`, `android-chrome-512x512.png` | PWA / Android (`site.webmanifest`) |
| `logo-mark-{32,180,192,512}.png` | Plain transparent mark (no tile) for embeds |

## Colors

| Token | Hex | Usage |
|-------|-----|-------|
| Background | `#0B0F14` | App-icon tile, social card, dark surfaces |
| Foreground | `#FFFFFF` | Mark, wordmark, tagline |
| Accent | `#3B82F6` | Tagline dots, glow, links |

## Rules

- Keep clearspace around the lockup ≥ the height of the `d` in `drogue`.
- Never recolor the mark; use the white file on dark, black file on light.
- Minimum sizes: lockup ≥ 120 px wide, mark ≥ 16 px.
