# Branding

Logo exploration archive from the July 2026 rebrand (replacing the original
"HS" text mark).

- [`logo-explorations-2026-07.png`](logo-explorations-2026-07.png) is a contact
  sheet of the candidate directions in the "premium dark" treatment (glyph
  carries the gradient on a near-black tile). The early-bird and career-steps
  tiles show their final refined forms.
- [`logo-early-bird-refinement-2026-07.png`](logo-early-bird-refinement-2026-07.png)
  is the refinement round of the early-bird direction, the runner-up candidate:
  sun object removed, bird enlarged and centered, eye added, dawn rendered as an
  atmospheric glow.
- [`explorations/`](explorations/) holds the source SVG for each candidate as
  labeled on the sheet, plus `early-bird-final.svg` and
  `career-steps-final.svg` (the two refined finalists).

## Final mark

**Career steps**: an emerald→lime gradient staircase that launches into a
45° arrow with a glow at the peak, on a deep teal-black sky. It reads as
climbing the career ladder and taking off. The production SVG lives at
`frontend/public/icon.svg` and is the single source of truth for the
favicon/PWA PNGs and the in-app `Brand` component.

The SVG carries an internal `prefers-color-scheme` media query: in light mode
the tile flips to a mint surface with deeper emerald→lime steps, so the
in-app mark (and the README logo on GitHub) adapts with the OS theme.
Rasterized PNG icons keep the dark default, which reads on any surface.

## Palette

The app accent follows the mark while surfaces stay neutral (see
`frontend/src/index.css` tokens): emerald brand/primary on zinc backgrounds,
with **light and dark modes** driven by `color-scheme: light dark` and CSS
`light-dark()`. Dark uses `#34d399` accents on `#09090b` surfaces, light uses
`#047857` on `#fafafa`. Semantic status colors (success green, danger red) are
independent tokens and keep their meaning regardless of the brand accent.
