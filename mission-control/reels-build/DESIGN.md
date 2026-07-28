# DESIGN.md

> This file is the single source of truth for visual/UX decisions in this repo.
> Claude Code (or any coding agent) should read this file before writing or
> editing any UI code, and follow it instead of guessing. If a request
> conflicts with this file, flag the conflict instead of silently picking one.

## 1. Voice & Feel
<!-- One or two sentences describing the vibe you're going for. Be concrete —
     "clean SaaS dashboard" is more useful than "modern and sleek". -->
- Feel: {{FEEL}}
- Reference products / sites we're inspired by: {{REFERENCES}}
- Things to explicitly avoid: {{ANTI_PATTERNS}}

## 2. Color Palette
<!-- Keep this to a short, named list. Every color used in the UI should map
     to one of these tokens — no ad-hoc hex codes in components. -->

| Token | Hex | Usage |
|---|---|---|
| `color-bg` | {{BG}} | page background |
| `color-surface` | {{SURFACE}} | cards, panels, modals |
| `color-border` | {{BORDER}} | dividers, outlines |
| `color-text-primary` | {{TEXT_PRIMARY}} | headings, body text |
| `color-text-secondary` | {{TEXT_SECONDARY}} | captions, muted text |
| `color-accent` | {{ACCENT}} | primary actions, links, focus rings |
| `color-accent-hover` | {{ACCENT_HOVER}} | hover/active state of accent |
| `color-success` | {{SUCCESS}} | success states |
| `color-warning` | {{WARNING}} | warning states |
| `color-danger` | {{DANGER}} | destructive actions, errors |

Dark mode: {{DARK_MODE_RULE}}
<!-- e.g. "Every token above has a dark-mode pair defined in tailwind.config
     under `dark:`. Never hardcode a light-only color." -->

## 3. Spacing & Layout
<!-- One scale, used everywhere. If you use Tailwind, this is just naming your
     subset of the default scale so the agent doesn't invent random values. -->
- Base unit: {{BASE_UNIT}} (e.g. 4px)
- Allowed spacing steps: {{SPACING_SCALE}} (e.g. 4, 8, 12, 16, 24, 32, 48, 64)
- Max content width: {{MAX_WIDTH}}
- Grid: {{GRID_RULE}} (e.g. 12-col, 24px gutter, breakpoints at 640/1024/1280)
- Never use arbitrary spacing values (e.g. `mt-[13px]`) outside this scale.

## 4. Typography
| Role | Font | Size | Weight | Line-height |
|---|---|---|---|---|
| Display | {{FONT_DISPLAY}} | {{SIZE_DISPLAY}} | {{WEIGHT_DISPLAY}} | {{LH_DISPLAY}} |
| Heading | {{FONT_HEADING}} | {{SIZE_HEADING}} | {{WEIGHT_HEADING}} | {{LH_HEADING}} |
| Body | {{FONT_BODY}} | {{SIZE_BODY}} | {{WEIGHT_BODY}} | {{LH_BODY}} |
| Caption | {{FONT_CAPTION}} | {{SIZE_CAPTION}} | {{WEIGHT_CAPTION}} | {{LH_CAPTION}} |

- Max heading levels per page: {{HEADING_RULE}}
- Never introduce a new font family without updating this table first.

## 5. Components
<!-- List the components that already exist so the agent reuses them instead
     of re-inventing a button/card/modal every time. -->

### Buttons
- Variants: {{BUTTON_VARIANTS}} (e.g. primary, secondary, ghost, destructive)
- Default corner radius: {{RADIUS_BUTTON}}
- States that must be styled: default, hover, active, focus-visible, disabled, loading

### Cards / Panels
- Corner radius: {{RADIUS_CARD}}
- Shadow: {{SHADOW_CARD}}
- Padding: {{PADDING_CARD}}

### Forms & Inputs
- Corner radius: {{RADIUS_INPUT}}
- Error state rule: {{ERROR_STATE_RULE}}
- Label placement: {{LABEL_PLACEMENT}}

### Other reusable components
{{OTHER_COMPONENTS}}
<!-- e.g. "Badge, Tooltip, Toast, EmptyState, Skeleton loader — see /src/ui/" -->

## 6. Motion
- Default transition duration: {{TRANSITION_DURATION}}
- Easing: {{EASING}}
- What gets animated: {{MOTION_RULES}} (e.g. "hover/focus only, no page-load animations")

## 7. Iconography & Imagery
- Icon set: {{ICON_SET}} (e.g. Lucide, Heroicons — pick one, don't mix)
- Icon size default: {{ICON_SIZE}}
- Image treatment: {{IMAGE_RULE}} (rounded corners? aspect ratio? placeholders?)

## 8. Accessibility Baseline
- Minimum contrast ratio: {{CONTRAST_RATIO}} (e.g. WCAG AA, 4.5:1 for body text)
- All interactive elements must have a visible focus state.
- All images/icons-as-buttons need an accessible label.

## 9. Rules for the Agent
<!-- The part that actually changes agent behavior. Keep it short and
     imperative — this is what gets re-read on every UI task. -->
1. Before building or editing any page/component, re-read this file.
2. Only use tokens/values defined above. If something isn't covered here,
   stop and ask, don't invent a one-off value.
3. Reuse an existing component from Section 5 before creating a new one.
4. If a user request conflicts with this file (e.g. "make the button pink"
   when pink isn't a token), point out the conflict and ask whether to
   update DESIGN.md or make a one-off exception.
5. When you do introduce something new that should become a standard
   (a new component, a new color), propose an addition to this file in the
   same turn — don't let drift accumulate silently.
