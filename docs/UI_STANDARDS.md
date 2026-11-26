# UI standards (web)

Every screen uses the same font, type scale, colours and shapes. These are defined once, as tokens in
`apps/web/src/app/globals.css` (`@theme`). Shared building blocks live in `apps/web/src/components/ui`.
CI runs `python scripts/ui_codemod.py --check src` from `apps/web` and fails when a page is off the standard.

## Font

- Latin text uses Inter. Tamil uses Noto Sans Tamil. Both are self-hosted with `next/font` in `app/layout.tsx`.
- The browser picks the Tamil font for Tamil characters on its own, so no class is needed.
- `html[lang=ta]` gets a little more line height. `LanguageContext` keeps `lang` in step with the language toggle.
- Numbers in tables and KPIs use tabular figures (`table` or `.tabular`), so columns line up.

## Type scale (nothing below 12px)

| Class | Size | Use |
|---|---|---|
| `text-title` | 24px | Page title. AppShell renders it as the page's only `h1`. |
| `text-kpi` | 30px | Big numbers in `StatTile` |
| `text-heading` | 16px | Card titles (`CardHeader`) |
| `text-body` | 14px | Body text, table cells, navigation, inputs |
| `text-label` | 13px | Field and KPI labels, subtitles |
| `text-caption` | 12px | Table heads, hints, badges |

Tailwind's `text-xs` (12px) and `text-sm` (14px) are still allowed. Arbitrary sizes such as `text-[10px]` are not.

Use only three weights:

- `font-normal` for text
- `font-medium` for labels and links
- `font-semibold` for titles and values

`font-bold`, `font-extrabold` and `font-black` are not used. Labels are written in sentence case, never with `uppercase`.

## Colour tokens

Use these instead of hex values. They work with every utility (`text-`, `bg-`, `border-`, `ring-`, `from-` and the rest), and opacity works too (`bg-brand/10`).

| Group | Tokens |
|---|---|
| Text | `ink` (headings, values), `ink-soft` (body), `muted` (labels), `subtle` (placeholders, ids) |
| Surfaces | `canvas` (page), `surface` (cards), `surface-2` (table head, tiles, hover) |
| Lines | `line` (borders), `line-soft` (dividers, bar tracks), `line-strong` (inputs, dashed) |
| Brand | `navy`, `navy-2` (dark panels), `brand` (also the app sidebar), `brand-hover`, `brand-soft`, `brand-line`, `teal`, `teal-hover` |
| Status | `success`, `warning`, `danger`, each with `-fill`, `-soft`, `-faint` and `-line`, plus `info`/`info-soft` and `violet`/`violet-soft` |

Rules:

- Green, amber and red mean status only.
- Fills are for bars and charts. Soft and faint backgrounds are for badges and notices.
- Charts (recharts) need literal colour values. Copy them from the `@theme` block and name the constant, as `BAND_HEX` does in `app/college/page.tsx`.
- Only the dark code-editor and lab surfaces keep literal hex classes. They are listed in `DARK_OK` in the script.
- To add a colour, add a token to `@theme` and to `HEX` in `scripts/ui_codemod.py`.

## Shape and spacing

- Cards, panels and dialogs: `rounded-card` (12px), `border border-line`, `shadow-card`. Popovers and toasts use `shadow-pop`.
- Tiles inside cards, inputs and buttons: `rounded-tile` (8px). Badges and progress bars: `rounded-full`.
- Page sections are 24px apart (`space-y-6`, or `gap-6` for grids). Cards use 20px padding (`p-5`).
- Tables run edge to edge inside a card with `padded={false}`. Rows are 44–48px tall.

## Page skeleton

```tsx
<AppShell pageTitle={t("x.title")} pageSubtitle={t("x.help")} pageActions={<Button>…</Button>}>
  <div className="space-y-6 max-w-6xl">
    <section className="grid gap-4 sm:grid-cols-3">
      <StatTile label={…} value={…} hint={…} tone={deltaTone(change)} />
    </section>
    <Card padded={false}>
      <CardHeader className="px-5 pt-5" title={…} actions={<Select …/>} />
      <Table><THead><tr><Th>…</Th><Th align="right">…</Th></tr></THead>
        <tbody><Tr><Td>…</Td><Td align="right">…</Td></Tr></tbody></Table>
    </Card>
  </div>
</AppShell>
```

- **Reference screens:** `app/college/readiness/page.tsx` (screen 39) and `app/college/page.tsx` (screen 19).
- **Page title:** the title stays inside the shell, because tests find each screen by its `h1`. Pass `header={false}` only when a page draws its own `h1`.
- **Building blocks:**
  - `Card`, `CardHeader`
  - `StatTile`, `MetricBar`, `ProgressBar`, `DistributionBar`, `deltaTone`
  - `Badge` (tones: neutral, brand, info, success, warning, danger, violet)
  - `Button` and `buttonClass` (primary, secondary, ghost, danger; sizes sm, md)
  - `Input`, `Select`, `Field`, `Tabs`, `EmptyState`
  - `Table`, `THead`, `Th`, `Tr`, `Td`
- **Merging classes:** use `cn()` from `lib/cn.ts`. It knows the custom size and colour tokens, so `text-caption` and `text-muted` don't cancel each other out.

## Checking and fixing

```bash
cd apps/web
python scripts/ui_codemod.py --check src     # what CI runs
python scripts/ui_codemod.py src/app/trainer # rewrites class names in place (no logic changes)
```

Check every new screen in Tamil and at phone width. Tamil words are longer: let labels wrap (`line-clamp-2`, `break-words`) rather than cutting them off.
