# Study Guide Generator UI — Option A Visual Match

This is the **Option A** implementation: the generated mockup screens are used as high-fidelity visual assets, while the app shell, responsive layout, screen switching, and project structure are coded in **React + Tailwind**.

This gives the closest possible match to the mockup images.

## What is included

- Mobile welcome screen
- Mobile home dashboard
- Mobile Exam Cram page
- Mobile Claude-style Guides page
- Desktop dashboard mockup
- React screen switcher
- Tailwind dark theme setup
- Deep navy + bright orange design system
- Mockup assets in `public/mockups/`

## Install

```bash
npm install
```

## Run locally

```bash
npm run dev
```

Then open the local Vite URL shown in your terminal.

## Build

```bash
npm run build
```

## Important note

Because the original design was generated as flat PNG mockups, the closest way to match it exactly is to use those PNGs as visual assets. The current project is ideal for:

1. presenting the exact visual design,
2. using the screens as a frontend reference,
3. gradually replacing each image-backed screen with live React components.

If you need every text label, icon, card, and button to become fully editable/clickable, use these screens as the reference and rebuild one section at a time.
