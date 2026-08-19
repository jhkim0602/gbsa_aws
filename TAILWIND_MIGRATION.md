# Tailwind conversion contract

Goal: every remaining styled class moves onto the markup as Tailwind utilities, **with the
rendered UI unchanged**. Read this before converting anything.

Baseline commit: `ba64585` (`feat(ui): renew the interview room and adopt a shared design
system`). Built CSS at that commit: applicant 45.30 kB, company 186.95 kB.

## Setup already in place — do not change it

- `tailwindcss@4` + `@tailwindcss/vite@4`, wired in both `vite.config.ts`.
- Tokens live in `packages/design-system/theme.css` (`@iep/design-system`), declared with
  `@theme static`, so every token is reachable as a utility.
- Both entries are `@import "tailwindcss"` — **Preflight is ON**. The stylesheets were
  rewritten against it. Do not remove it, and do not reintroduce a per-app `base.css`.
- Every remaining app stylesheet is wrapped in `@layer components { ... }`. Utilities sit in
  a later layer, so **a utility on the markup always beats a leftover class rule**. That is
  what makes an incremental, file-by-file conversion safe.

## Hard rules

### 1. Font size — ALWAYS arbitrary, NEVER named

Named `text-*` utilities inject a paired `line-height`; arbitrary ones do not. The design
declares 480 `font-size`es against only 83 `line-height`s, so ~400 blocks intentionally
inherit their leading.

```
text-xs      → font-size:.75rem; line-height:calc(1/.75)   ← 1.333, WRONG
text-[12px]  → font-size:12px                              ← RIGHT
```

- `font-size: 12px` → `text-[12px]` ✅ (never `text-xs`)
- Add `leading-*` **only** when the source rule declares `line-height`.
- `line-height: 1.5` → `leading-[1.5]`. Verified: emits `line-height: 1.5`, nothing else.

Note: files already converted on the renewal branch (`InterviewRoom.tsx`, `submissions/`,
`tech-stack-combobox/`) use `text-sm`/`slate-*` deliberately — that was a redesign, not a
port. Do not "harmonise" them, and do not copy their approach into a fidelity conversion.

### 2. Preserve exact px values — use arbitrary values freely

The design uses 1/2/3/5/6/7/9/11/13px etc. The 4px spacing scale cannot express these.

- `padding: 0 18px` → `px-[18px]` (not `px-4`/`px-5`)
- When in doubt, use the arbitrary value. Correctness beats idiom.

Scale utilities are fine **only** where they resolve to the identical px. `--spacing` is
`0.25rem`, so `<n>` = `4n` px — verified against `tailwindcss@4.3.3`:

| px  | utility | px  | utility |
| --- | ------- | --- | ------- |
| 2   | `0.5`   | 20  | `5`     |
| 4   | `1`     | 24  | `6`     |
| 6   | `1.5`   | 28  | `7`     |
| 8   | `2`     | 32  | `8`     |
| 10  | `2.5`   | 40  | `10`    |
| 12  | `3`     | 48  | `12`    |
| 14  | `3.5`   |     |         |
| 16  | `4`     |     |         |

Anything not a multiple of 2 (1/3/5/7/9/11/13/18/22/26/30/34/38px…) **must** be arbitrary.

Radius — verified token values:

| CSS                    | utility                                   |
| ---------------------- | ----------------------------------------- |
| `border-radius: 3px`   | `rounded-[3px]`                           |
| `border-radius: 4px`   | `rounded-sm` (0.25rem)                    |
| `border-radius: 6px`   | `rounded-md` (0.375rem)                   |
| `border-radius: 8px`   | `rounded-lg` / `rounded-control` (0.5rem) |
| `border-radius: 10px`  | `rounded-panel` (0.625rem)                |
| `border-radius: 12px`  | `rounded-xl` (0.75rem)                    |
| `border-radius: 999px` | `rounded-full`                            |

Weight: `font-medium`=500, `font-semibold`=600, `font-bold`=700. The design also uses
550/650/680/750/800 — those need `font-[650]` (verified: emits `font-weight: 650`).

### 3. Colors come from the design-system tokens

These utilities exist (verified by compiling a probe against `theme.css`):

```
bg-/text-/border-  canvas surface surface-muted surface-strong border border-muted
                   border-strong ink ink-secondary muted subtle brand brand-strong
                   brand-soft success success-soft warning warning-soft danger danger-soft
shadow-soft  shadow-float   font-sans  font-mono
rounded-control  rounded-panel
```

`var(--color-text)` → `text-ink`, `var(--color-link)` → `brand`,
`var(--color-link-strong)` → `brand-strong`, `var(--color-purple-soft)` → `brand-soft`.

**These are NOT utilities**: `text-text`, `bg-link`, `bg-purple`, `bg-product-bar`. They are
`:root` aliases in `theme.css`, not `@theme` keys, so `bg-link` compiles to nothing. Confirmed
by probe. Always use the underlying token name.

Literal `#ffffff` stays literal → `text-white` / `bg-white`. Note `.icon-button` uses
`#ffffff` in components.css but `var(--color-surface)` in hiring.css — same color, and
hiring.css wins (see below).

Raw colors with no token go in as arbitrary values, in the form the bundle already uses:
`border-[#dc262640]`, `shadow-[0_0_0_3px_#5966ce1f]`,
`border-[color-mix(in_srgb,var(--color-danger)_35%,var(--color-border))]`.

### 3b. What Preflight already does — do not re-declare it

Verified against `node_modules/tailwindcss/preflight.css`:

| Preflight rule                                                                                          | So you do NOT need                                                                                                       |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `*,::before,::after { margin:0; padding:0; border:0 solid }`                                            | `m-0`, `p-0`, `border-0`                                                                                                 |
| `h1..h6 { font-size:inherit; font-weight:inherit }`                                                     | — but you **DO** need `font-bold` on a heading whose source rule declared `font-weight:700`, because the UA bold is gone |
| `ol,ul,menu { list-style:none }`                                                                        | `list-none`                                                                                                              |
| `img,svg,video,canvas { display:block; vertical-align:middle }`                                         | `block` on an icon                                                                                                       |
| `button,input,select,textarea { font:inherit; color:inherit; background:transparent; border-radius:0 }` | `font-inherit`, `bg-transparent` on a bare button                                                                        |
| `button { appearance:button }`                                                                          | —                                                                                                                        |

`theme.css` adds `button { cursor:pointer }` and `button:disabled { cursor:not-allowed }`, so
those are free too. It also sets `letter-spacing: 0` on form controls; a source rule declaring
`letter-spacing: 0` on a heading needs `tracking-normal`.

### 4. Selector translation

| CSS                         | Tailwind                                       |
| --------------------------- | ---------------------------------------------- |
| `:hover:not(:disabled)`     | `hover:not-disabled:`                          |
| `.x.is-active`              | conditional class in the template literal      |
| `.x:focus-visible`          | `focus-visible:`                               |
| `.x:disabled`               | `disabled:`                                    |
| `[data-state="current"] .y` | `data-[state=current]:` or lift to a prop      |
| `@media (max-width: 720px)` | `mw-720:` (**not** `max-[720px]:` — see below) |

Mobile-first inversion is NOT allowed — it changes which rule wins.

**Use `mw-N:`, never the built-in `max-[Npx]:`.** Verified against `tailwindcss@4.3.3`:
`max-[680px]:p-4` compiles to `@media (width < 680px)`, which **excludes** 680px, while the
source stylesheets declare `@media (max-width: 680px)`, which **includes** it. At a viewport
exactly equal to a breakpoint the two disagree — and 360/400/480/600/720 are real device
widths, so the off-by-one is visible.

`design-system/theme.css` declares an inclusive `@custom-variant` for every breakpoint the
design uses, so `mw-680:p-4` → `@media (max-width: 680px)`. All 24 exist:

```
mw-1180 mw-1080 mw-1050 mw-1040 mw-980 mw-960 mw-920 mw-900 mw-880 mw-860 mw-820 mw-780
mw-760 mw-720 mw-680 mw-640 mw-620 mw-600 mw-520 mw-480 mw-400 mw-360 mw-190 mw-108
```

They compose like any variant: `mw-620:[&>svg]:hidden`, `hover:mw-680:bg-brand`,
`mw-680:not-last:after:hidden`. The verifier fails the build on a bare `max-[Npx]:`.

**That widest-first order is load-bearing — leave it alone.** Tailwind sorts its own `max-*`
variants descending, but `@custom-variant` blocks emit in _declaration_ order, so for `mw-N:`
the declaration order **is** the cascade order. Two of these routinely match at once: at 600px
both `mw-780:` and `mw-620:` apply, and media queries do not raise specificity, so the one
emitted later wins. The stylesheets are desktop-first (`720` then `620` then …), where the
narrower query is the more specific intent, so the narrower variant must come last.

Practical consequence when converting: a property that the source overrides at two
breakpoints just works — write both, in any order in the attribute.

```
mw-780:grid-cols-3 mw-620:grid-cols-1     ← at 600px, grid-cols-1 wins. Correct.
```

The verifier fails the build if the declarations are ever reordered ascending.

### 5. What stays in CSS

Keep in the existing `@layer components` stylesheet, declarations verbatim, when a utility
genuinely cannot express it:

- `@media print` blocks (2 of them)
- `::before` / `::after` with generated `content` (22 rules)
- positional selectors over children the markup does not enumerate (72 rules):
  `:nth-child(2n)`, `:nth-last-child(2)`, `li + li`, `> span:not(.x)`
- `::-webkit-scrollbar` on specific elements

Prefer utilities. When you fall back, add a one-line comment saying why.

### 6. Class attribute style

- Static: plain string, ordered `layout → box → spacing → border → color → text → state`.
- Conditional: template literal, matching the existing code.
  ```tsx
  className={`... ${isActive ? "bg-surface-strong text-ink" : "text-muted"}`}
  ```
- A `cn()` helper exists in `hiring/tech-stack-combobox/utils.ts` (clsx + tailwind-merge) and
  a local one in `submissions/index.tsx`. Use `cn()` only in files that already import it;
  don't add new imports of it as part of a conversion.

### 7. Scope discipline

Convert styling only. Do **not** change markup structure, tag names, `aria-*`, `role`, `id`,
event handlers, prop shapes, or copy. Same DOM, same attributes — only `className` changes.

## Shared primitives — use these exact strings

Defined once and consumed from many files, so they must convert identically everywhere.
Winners below were read off the **built bundle** at `ba64585`, not the source order.

`components.css` is now imported **first** (index.css line 3), so where a feature stylesheet
redefines a primitive, **the feature file wins** — the reverse of what source order suggests.

> **These strings are company-console only.** The applicant app's `index.css` does not import
> `components.css`, so a class of the same name there is a _different_ rule. See
> "Applicant-app primitives" below before converting anything under `apps/applicant-interview`.

```
button-primary    inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg
                  border border-brand bg-brand px-[18px] text-[14px] font-semibold text-white
                  shadow-soft hover:not-disabled:bg-brand-strong

button-secondary  inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg
                  border border-border bg-white px-[18px] text-[14px] font-semibold text-ink
                  shadow-soft hover:not-disabled:bg-surface-muted
   is-danger   →  border-[color-mix(in_srgb,var(--color-danger)_35%,var(--color-border))]
                  text-danger                       (company.css; replaces border+text)

icon-button       inline-grid size-8 place-items-center rounded-md border border-border
                  bg-surface font-semibold text-muted
                  hover:bg-surface-muted hover:text-ink
                  disabled:cursor-not-allowed disabled:opacity-35
   ^ hiring.css version — THIS is what renders. The components.css version
     (inline-flex / rounded-lg / bg-white / hover:bg-surface-muted hover:text-ink) is
     fully overridden and dead. Its `:hover` still applies, so keep
     hover:bg-surface-muted hover:text-ink.

button-quiet      inline-flex min-h-7 rounded-[3px] border-0 bg-transparent px-2 text-[9px]
                  font-semibold text-brand hover:bg-brand-soft
                  mw-680:min-h-8 mw-680:border mw-680:border-border
                  mw-680:bg-surface mw-680:px-2.5

invitation-status inline-flex min-h-[26px] items-center rounded-md bg-surface-strong px-[9px]
                  text-[11px] font-semibold text-muted
   is-progress /  text-brand bg-brand-soft
   is-ready    →
   is-attention→  text-warning bg-warning-soft
   ^ hiring.css redefines the company.css version wholesale (min-height 22→26,
     radius 3→6, padding 7→9, adds font-size 11). These are the merged winners.

search-field      relative flex w-[min(280px,100%)] items-center mw-680:w-full
   > svg       →  absolute left-2.5 text-subtle

section-header    flex min-h-[57px] items-center justify-between gap-[14px] border-b
                  border-border px-[15px] py-[11px]
   > p         →  mt-0.5 text-[9px] text-muted

draft-validation  inline-flex items-center gap-1.5 text-[11px] leading-[1.35] text-muted
   is-invalid  →  text-danger
   is-empty    →  text-subtle

panel             rounded-xl border border-border bg-surface shadow-soft

status-badge      inline-flex min-h-5 items-center rounded-full bg-surface-strong px-2
                  font-mono text-[10px] font-medium whitespace-nowrap text-muted
   is-success  →  bg-success-soft text-success      (replaces the base bg/text)
   is-warning  →  bg-warning-soft text-warning
   is-danger   →  bg-danger-soft  text-danger

form-alert        mx-6 mt-[14px] rounded-md border border-[#dc262640] bg-danger-soft
                  px-[11px] py-[9px] text-[10px] text-danger
   is-success  →  border-[#1e9e6333] bg-success-soft text-success

page-header       flex min-h-[65px] items-center justify-between gap-5 px-8 pt-[30px]
                  pb-[14px] mw-680:items-start mw-680:p-4
   > h1        →  m-0 text-[28px] font-bold
   > p         →  mt-0.5 mb-0 text-[14px] leading-[1.5] text-muted

page-content      px-8 pt-5 pb-12 mw-680:p-4

async-state /     grid min-h-[260px] place-items-center p-[30px] text-center text-muted
empty-state       (their `p` children: m-0 text-[12px])
```

`button-danger` is defined in components.css but unreferenced — drop it.

### Applicant-app primitives — a separate, smaller set

`apps/applicant-interview/src/app/styles/index.css` imports only `tailwindcss`, `theme.css`,
`shell.css`, `access.css`, `interview.css`. **No `components.css`.** So in the applicant app:

- `.button-primary` / `.button-secondary` declare **color only** (interview.css 203–212). All
  their geometry comes from the _parent_ selector `.interview-actions button, .reconnect-banner
button`, which is where min-height/padding/radius/size/weight live. Converting a button inside
  those containers means emitting both halves onto the element:

  ```
  base (from the parent rule, applies to EVERY button in those containers):
      inline-flex min-h-11 items-center justify-center rounded-panel border border-border
      px-4 text-[13px] font-[650]
      disabled:opacity-45                    ← .interview-actions button:disabled only
  + button-primary  →  border-brand bg-brand text-white
  + button-secondary→  bg-surface text-ink
  ```

  `--applicant-control-height` is `44px` → `min-h-11`. `--applicant-radius` is `--radius-panel`
  → `rounded-panel`. `font: inherit` and `cursor: pointer` are Preflight/theme freebies.
  `border-color: ... !important` on `.button-primary` only exists to beat the parent's
  `border: 1px solid var(--applicant-border)`; as a utility, `border-brand` after
  `border-border` needs no `!`— emit only `border-brand`.

- There is **no** `min-h-10` / `px-[18px]` / `text-[14px]` / `shadow-soft` / hover state here,
  and no `.icon-button`, `.panel`, `.status-badge`, `.page-header`, `.page-content`,
  `.async-state`, `.empty-state`. Do not import the company strings.
- Applicant colors are `--applicant-*` aliases of the same tokens (`--applicant-blue` →
  `brand`, `--applicant-text` → `ink`, `--applicant-surface` → `surface`,
  `--applicant-border` → `border`, `--applicant-muted` → `muted`, `--applicant-subtle` →
  `subtle`, `--applicant-green` → `success`, `--applicant-orange` → `warning`,
  `--applicant-danger` → `danger`, `--applicant-blue-soft` → `brand-soft`,
  `--applicant-green-soft` → `success-soft`, `--applicant-bg` → `canvas`). Note
  `--applicant-green-strong` aliases `--color-brand`, **not** a green — use `brand`.

Before converting any other class that appears in the cross-file list below, check the bundle
for its real winner the same way (`grep` the built CSS, then check whether the later offset is
inside a `@media` block):

```
applicant-content  button-primary  button-quiet  button-secondary  empty-state  form-alert
icon-button  interview-room  invitation-status  invitation-table  is-active  is-danger
is-success  is-warning  page-header  panel  search-field  status-badge  workspace-form
```

## Dynamically constructed class names

A grep for a class name can come back empty while the class is live, because the name is
assembled at runtime:

```tsx
className={`assessment-badge assessment-badge--${state}`}   // review/ReportView.tsx
```

so `assessment-badge--confirmed|--partially_confirmed|--needs_follow_up|
--insufficient_evidence` are all reachable. Convert by mapping the state to a full utility
string:

```tsx
const badgeTone: Record<AssessmentState, string> = { confirmed: "...", ... }
```

Before treating any class as dead, grep for its distinctive _fragment_ (`assessment-badge`),
not the whole name. If it is genuinely unreferenced, leave it out and say so in your report —
do not silently drop styling something might reach.

## Working rules while converting in parallel

Several files are converted at once, so:

- **Do not edit, delete, or create any `.css` file.** The old stylesheets are the reference
  other converters are still reading, and `@layer components` already guarantees they lose to
  your utilities. They are pruned centrally at the end.
- **Do not remove `@import` lines** from `index.css`, for the same reason.
- **Do not run `npm run build` / `tsc -b`.** They race on `dist/` and `.tsbuildinfo`. The
  build is run centrally.
- Touch only the `.tsx` files assigned to you.
- Look up a class in whichever `.css` file defines it
  (`grep -rn '\.classname' apps/*/src --include='*.css'`), including `@media` blocks and
  `.is-*` modifiers further down the file.
- Report any structural CSS you need as text in your result; it is written centrally.

## Definition of done per file

1. Every class the file referenced is either expressed as utilities on the markup, or
   reported as needed structural CSS.
2. `className` no longer references a project class name — only Tailwind utilities.
3. Markup, attributes, handlers, and copy are untouched.

## Verify (run centrally)

```
python3 scripts/verify_tailwind_migration.py
npm run typecheck && npm run build && npm run lint && npm run format:check
```
