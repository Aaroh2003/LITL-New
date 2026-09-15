# LiTL — implementation contract

Source of truth: Figma file `xnzaow8rcNAjNAwoFkw5hd` — "LiTL — Lawyer in the Loop".
Screens come from page **01 · Desktop Flow**; tokens and components from **03 · Foundations & Components**.

## Stack

- Vite 8 + React 19 + TypeScript.
- Tailwind CSS v4 (`@tailwindcss/vite`, config-less — tokens live in `src/index.css` under `@theme`)
- react-router-dom 7
- `@/` is an alias for `src/`

## Rules for screen implementation

1. **Never hard-code hex values.** Use the Tailwind classes generated from the `@theme` tokens.
2. **Reuse the shared components** listed below rather than re-implementing nav/pills/cards.
3. Keep every screen a single default-exported component in `src/screens/`.
4. Screens render inside `<AppShell>` (top nav + boundary strip) unless the Figma frame has no nav.
5. Figma frames are 1440 wide. Build with flex/grid so the layout survives other widths —
   never absolute-position a whole screen.
6. Screen-specific copy and mock records live as `const` arrays at the top of the screen file.
7. Vector "assets" in this design are plain filled circles / typographic glyphs (↑ ◈ ◉ ⬒ ⟶),
   so they are reproduced with CSS and text rather than imported SVG files.

## Color tokens → Tailwind classes

| Token | Hex | Classes |
| --- | --- | --- |
| carbon-900 | `#0B0F1C` | `bg-carbon-900` `text-carbon-900` `border-carbon-900` |
| carbon-700 | `#1D2438` | `bg-carbon-700` `text-carbon-700` |
| yellow-500 | `#FFD60A` | `bg-yellow-500` `text-yellow-500` `border-yellow-500` |
| yellow-100 | `#FFF7C7` | `bg-yellow-100` |
| gold-ink | `#A88500` | `text-gold-ink` (overlines / accent text on light) |
| ochre | `#8B6914` | `bg-ochre` `text-ochre` (landing CTAs) |
| paper | `#FBFBF8` | `bg-paper` |
| cream | `#F9F8F3` | `bg-cream` (landing light surface) |
| ink | `#151A24` | `text-ink` |
| slate | `#59637A` | `text-slate` |
| slate-soft | `#8A94A8` | `text-slate-soft` |
| mist | `#E7E7DE` | `border-mist` `bg-mist` |
| cite-mark | `#FFF4A3` | `bg-cite-mark` (citation highlight) |
| passage-mark | `#E8EBFF` | `bg-passage-mark` (evidence passage) |
| green | `#0C8A5F` | `text-green` `bg-green` |
| amber | `#D97706` | `text-amber` `bg-amber` |
| red | `#E11D48` | `text-red` `bg-red` |
| blue | `#2563EB` | `text-blue` `bg-blue` |
| green-tint | `#DCF5EA` | `bg-green-tint` |
| amber-tint | `#FEF3E0` | `bg-amber-tint` |
| red-tint | `#FFE7ED` | `bg-red-tint` |
| blue-tint | `#E8EFFD` | `bg-blue-tint` |
| neutral-tint | `#EBEFF5` | `bg-neutral-tint` |

Radii: `rounded-card` (14px), `rounded-panel` (18px), `rounded-pill` (100px).
Elevation: `shadow-card`, `shadow-panel`.

## Type

| Role | Figma | Use |
| --- | --- | --- |
| Display | Space Grotesk Bold 40 | `.type-display` or `font-display text-[Npx] font-bold` |
| H2 | Space Grotesk Bold 28 | `.type-h2` |
| H3 | Inter SemiBold 20 | `.type-h3` |
| Body | Inter Regular 15 | default body |
| Small | Inter Regular 13 | `text-[13px] text-slate` |
| Overline | Inter SemiBold 11 tracked | `.type-overline text-gold-ink` |
| Serif | Source Serif 4 | `font-serif` (case citations on landing) |
| Mono | JetBrains Mono 13 | `.type-mono` / `font-mono` |

Fonts load from Google Fonts in `index.html`.

## Shared components

| Component | Path | Notes |
| --- | --- | --- |
| `AppShell` | `@/components/layout/AppShell` | nav + content + boundary strip; props `showNav`, `showBoundaryStrip`, `contentClassName` |
| `BoundaryStrip` | `@/components/layout/AppShell` | standalone footer statement |
| `AppTopNav` | `@/components/layout/AppTopNav` | Figma node 3:28 |
| `LogoLockup` | `@/components/layout/LogoLockup` | Figma node 3:24; props `size`, `tone` |
| `StatusPill` | `@/components/ui/StatusPill` | Figma node 3:23; `status` is one of the 7 `VerificationStatus` values |
| `Button` / `ButtonLink` | `@/components/ui/Button` | variants `primary \| secondary \| ghost \| danger`, sizes `sm \| md \| lg` |
| `Card` / `Overline` / `Divider` | `@/components/ui/Card` | `Card` tones: `card \| panel \| flat` |
| `cn` | `@/lib/cn` | class-name joiner |

## Flow

The table below preserves the original Figma prototype references, not live
application routes. `src/flow.ts` is legacy design metadata and is not used by
the application. Runtime routes are registered in `src/App.tsx`.

The implemented beta uses `/documents`, `/upload`, `/login`, `/help` and
document-specific `/documents/:documentId/{analysis,summary,review,reports}`
routes. Review accepts an optional finding ID; reports accept a snapshot ID.
All operational data comes from the `/v1` API. The landing reference card alone
is explicitly illustrative. The senior/team flow is deferred and the legacy
prototype routes below are not registered. The existing tokens, AppShell,
buttons/cards and slotted three-pane WorkspaceLayout remain in use.

| # | Screen | Route | Figma node |
| --- | --- | --- | --- |
| 01 | Landing | `/` | `4:2` |
| 02 | Upload | `/upload` | `12:10` |
| 03 | Analyzing | `/analyzing` | `14:23` |
| 04 | Detection Summary | `/summary` | `14:66` |
| 05 | Workspace — Evidence | `/workspace/evidence` | `17:43` |
| 06 | Workspace — Quote Mismatch | `/workspace/quote-mismatch` | `25:53` |
| 07 | Workspace — Could Not Be Verified | `/workspace/unverified` | `27:63` |
| 08 | Workspace — Review Complete | `/workspace/complete` | `29:73` |
| 09 | Verification Report | `/report` | `31:83` |
| 10 | Senior Review | `/senior-review` | `31:207` |
