# Spectrum Showcase

Here's the rewritten prompt — pure frontend, hardcoded, client-ready showcase:

---

Spectrum — Frontend UI Showcase (Hardcoded / No Backend)

Build a stunning, fully hardcoded frontend-only website for Spectrum, a premium photography and videography company that captures school and college events. This is a client presentation build — no backend, no APIs, no database. Everything is hardcoded with dummy data. The goal is one thing: make it look absolutely incredible.

---

Visual Design & UI Direction

Overall Theme — "Spectrum in the Dark" (Logo-Driven Color System):

The brand logo is a multi-color ribbon "S" — a gradient sweep from golden yellow → orange → coral red at the top, through emerald green → teal, into violet → magenta at the base — paired with a bold charcoal-black wordmark on a clean white field. Use the provided Spectrum logo file as-is wherever the logo appears — do not redraw or approximate it. Audit every gradient stop and accent color in this spec against the actual colors sampled from that logo file and adjust the hex values below if they drift from the real asset, so the site's palette is a true match to the logo, not a stylized guess.

- **Theme direction — consistently, moderately dark (not near-black):** the entire site, hero included, runs on one unified dark base rather than swinging between a light hero and dark sections. This should read as "a little dark" — a soft, muted charcoal-plum, not the deep near-black of a cinema theme. The same base tone carries from the top of the hero all the way to the footer, so the site never feels like it's stitched together from a light section and a dark section — it's one continuous, cohesive dark surface.
- Base canvas (every section, hero included — single consistent tone): `#221F29`. No light-to-dark fades between sections; footer and modals may dip a touch deeper to `#1C1A22` purely for subtle layering, but the difference should be barely perceptible, not a visible shift.
- Text — tuned for high visibility against this dark base:
  - Headings: warm-white `#F6F4F1`
  - Secondary/body copy: light muted gray `#C3BEC9`
  - Never use dark charcoal-ink text anywhere on the site now that the whole canvas is dark — every text color must pass clear contrast against `#221F29`.
- Signature Spectrum Gradient (the site's single most important visual signature — used for logo mark, primary CTA buttons, hero headline accent word, active states, glowing borders, selection checkmarks, price badges, section-divider hairlines, loading shimmer): a warm-to-cool sweep pulled straight from the ribbon —
  `#FFC93C → #FF8A3D → #E8503A → #2FBF8F → #7C4DE0 → #D6339A`
  (Confirm these six stops against the actual logo file colors during implementation and nudge any that don't match.)
  Used as an accent — thin lines, glows, gradient text, gradient-filled buttons/icons, badges — never as a full-bleed background wash, so the dark canvas stays the dominant surface and the gradient reads as a deliberate highlight rather than noise.
  **Animated by default:** wherever the Spectrum Gradient appears — text-fills, button fills, borders, badges, hairlines, icons, the logo mark itself — it runs a slow, continuous hue-cycle/position animation as its resting idle state, sweeping warm (yellow/orange/red) into cool (teal/violet/magenta) and looping back, like light through a prism. Interaction states (hover, active, selection) speed up or intensify this existing animation rather than switching on a new one.
- **More color, without clutter:** to make the site feel richer and more colorful (not just accent lines), add a small number of large, heavily-blurred "ambient glow" orbs in the Spectrum Gradient hues, positioned low-opacity (8–12%) behind key sections — hero, stats band, featured events — so color washes softly through the dark canvas like light bleeding through fabric. Keep these orbs few, large, and soft — 1–2 per section max — so the effect adds warmth and richness without ever competing with text or turning busy/messy. Every other use of color stays exactly as scoped elsewhere in this doc (gradient accents, teal, violet) — this ambient-glow layer is the only addition, purely atmospheric.
- Secondary solid accent — Spectrum Teal `#2FBF8F`: for links, secondary badges, success ticks, hover underlines — a calmer single-color pull from the mid-ribbon for places a full gradient would be too busy.
- Tertiary solid accent — Spectrum Violet `#8B5CF6`: for focus rings, toggle switches, filter-chip active states — the cool end of the ribbon, used to balance the warm oranges elsewhere so the palette never tips too hot.
- Subtle film grain texture overlay across the site for a photographic, tactile feel.
- Typography: Playfair Display or Cormorant Garamond (serif) for headlines and display text, set in warm-white `#F6F4F1`, with the Spectrum Gradient applied as an animated text-fill on one key hero word for a signature moment. Inter or DM Sans for body copy, prices, labels, and UI elements.
- Contrast rule of thumb: every gradient or accent color sits on the consistent dark `#221F29` canvas — never on a muddy mid-tone — so the spectrum colors stay vivid, jewel-like, and unmistakably premium, and every line of text stays clearly legible against that same dark base.

---

Site Navigation — A Floating, Self-Effacing Nav (No Traditional Navbar)

Every page needs a way back to every other page, but a fixed, full-width, boxed navbar would fight the cinematic, editorial feel of the rest of the site. Instead, navigation is one small floating element that stays quiet until it's needed:

- The pill: a small, pill-shaped nav bar, centered at the top of the viewport, floating over the content. It uses the actual Spectrum logo file (ribbon mark; wordmark alongside it if legible at this size against the dark background — use a light/white-knockout version of the "spectrum" wordmark here rather than its original charcoal-black, since charcoal-black text would disappear against the dark canvas) plus three understated serif-caps text links (Events / How It Works / Contact) in warm-white. On load it sits transparent, no background, no border, directly over the dark hero. Once the user scrolls, it condenses into a small frosted-glass pill (a slightly lighter/lifted glass tone over the dark base) with a hairline animated Spectrum Gradient border — the same frosted-glass language already used in the Checkout Modal, so it feels native rather than bolted on.
- Scroll behavior: on scroll-down the pill fades to ~60% opacity and shrinks slightly so it never competes with the photography; on scroll-up it springs back to full opacity — the familiar "disappearing dock" pattern, so it's always reachable but never in the way.
- Active state: the current section gets a thin animated Spectrum Gradient underline beneath its link — no filled colored button, keeps the pill visually light.
- Gallery-only selection badge: on the Gallery page, a small circular counter badge (e.g. "3") appears at the right end of the pill once photos are selected, mirroring the sticky bottom bar's count. Tapping it smooth-scrolls to the sticky bar / opens the checkout modal — a quiet shortcut, not a second competing CTA.
- Mobile: the pill condenses to just the logomark and a single minimal icon — three small dots, not a hamburger, to keep the premium/editorial tone — which opens a full-screen frosted overlay menu (same dark base, slightly lifted) with the same three links in large serif type, warm-white (thin animated Spectrum Gradient underline on tap), and a close (×) in the same style as the Checkout Modal's close button.
- Secondary wayfinding (no breadcrumbs needed): the Events Listing and Gallery pages each get one small, quiet "← All Events" text link at the top-left of the page content itself (separate from the floating pill), in muted light gray, brightening to Spectrum Teal on hover — enough to always answer "how do I get back" without adding a breadcrumb trail or a second nav bar.
- Footer as the full site map: the Footer's Quick Links section (already specified) lists Home / Events / How It Works / Contact — the same destinations as the floating pill, so anyone who scrolls all the way down gets the complete map, while the pill up top stays deliberately minimal.

---

Page 1 — Homepage

Hero Section:
- **Full-width, edge-to-edge** — no side margins or max-width container; the hero bleeds the entire viewport width.
- **Fits entirely within the first viewport (above the fold):** the headline, subheadline, and the coverflow carousel must all be visible together on load, with zero scrolling required to see through the end of the carousel. Everything after the carousel — the search bar and the "Browse by Institution" row — lives just below this first viewport; reaching them is meant to take a small, deliberate scroll rather than being crammed into the initial view.
- Background: the same consistent dark base `#221F29` as the rest of the site (no separate light hero zone), with one soft ambient gradient glow orb behind the headline (per the "more color, without clutter" rule above).
- Centered large serif headline: "Every Moment, Yours Forever" in warm-white `#F6F4F1`, with the word "Yours" rendered in the animated Spectrum Gradient text-fill as the hero's signature brand moment.
- Subheadline below in muted light gray: "Spectrum captures school and college events. Browse, choose, and own your memories."
- Below the text: a 3D coverflow carousel of 6–8 event photography placeholder images — graduations, sports days, cultural performances, college fests, classroom candids. The active center image is full-scale and sharp; flanking images recede in perspective with slight scale-down, blur, and opacity fade. Carousel auto-rotates slowly and supports drag/swipe on mobile.
- Images in the carousel have a soft dark drop shadow with a faint animated spectrum-gradient glow at the edge to lift them off the dark background.
- Below the fold — first scroll reveal:
  - A clean pill-shaped search bar — "Find your school, college, or event…" with a search icon button filled in the animated Spectrum Gradient. Non-functional, styled only.
  - "Browse by Institution" row: a horizontal row of 5 circular institution icons (one per hardcoded institution), each a circular photo (school/college building or crest placeholder) with a thin animated Spectrum Gradient ring border, and the institution name in small serif caps, warm-white, centered directly underneath the circle. On hover, the ring border speeds up its gradient animation and the circle lifts 4px with a soft glow. Row scrolls horizontally on mobile (snap-scroll, no visible scrollbar).
  - Click/redirect logic:
    - If the clicked institution has more than one hardcoded event, route to `/events` with that institution pre-applied as the active filter chip. Ryan International School is the institution used to demonstrate this — it has two hardcoded events (Sports Meet 2025 and Republic Day Celebration 2025), so clicking its icon opens the Events Listing page already filtered to just those two.
    - If the clicked institution has only one hardcoded event, skip the listing page entirely and route straight to that event's Gallery page (`/events/[slug]`). Delhi Public School demonstrates this — one hardcoded event (Annual Day 2025), so its icon routes straight to the gallery.
    - St. Xavier's, Amity, and The Doon School also have exactly one event each, so their icons follow the same single-event, straight-to-gallery pattern as DPS.
    - Since only the Annual Day / DPS gallery is fully built out, every event slug (including Ryan International's two, once reached via the filtered listing) redirects to that same hardcoded gallery page for the presentation, per the routing rule in the Pages/Routes section below.

Stats Band:
- Same consistent dark `#221F29` base, with one soft ambient gradient glow orb behind it (per the "more color, without clutter" rule above).
- Three stat callouts centered, each number rendered in the animated Spectrum Gradient text-fill: "12,000+ Events Captured" / "48 Schools & Colleges" / "2.4 Lakh Photos Delivered"
- Entrance animation: numbers count up when scrolled into view.

How It Works Section:
- Same consistent dark `#221F29` base.
- Three steps in a horizontal row, each with a circular icon badge outlined in the animated Spectrum Gradient, bold number, serif heading in warm-white, and body copy in muted light gray:
  - 01 — We Shoot → Spectrum covers your school or college event professionally.
  - 02 — You Browse → Parents and students browse protected photo galleries online.
  - 03 — You Own It → Pay and receive full-res photos on WhatsApp or email instantly.
- Subtle scroll-triggered fade-in for each step.

Featured Events Section:
- Same consistent dark `#221F29` base, with one soft ambient gradient glow orb behind the section heading.
- Section heading in serif, warm-white: "Recently Captured"
- 3-column grid of hardcoded event cards (see Event Card spec below) — Annual Day, Sports Meet, Graduation Ceremony, Cultural Fest, etc.
- "View All Events" button filled with the animated Spectrum Gradient below the grid.

Footer:
- Same consistent dark base, `#1C1A22` (the barely-deeper footer tone).
- The actual Spectrum logo file (full-color ribbon mark, with a light/white-knockout wordmark for legibility on dark) + tagline "Imagination That Works" in warm-white on the left.
- Quick links in center, in warm-white — Home / Events / How It Works / Contact, same destinations as the floating nav pill — hover underline in Spectrum Teal.
- Contact info in muted light gray + social icons on right, icons outlined in Spectrum Violet with animated gradient fill on hover.
- Thin animated Spectrum Gradient hairline border across the top of the footer.

---

Page 2 — Events Listing Page

- Same consistent dark `#221F29` background as the rest of the site.
- Small "← Home" text link top-left of the page content, muted light gray brightening to Spectrum Teal on hover (per the Site Navigation section above).
- Page heading in large serif, warm-white: "All Events"
- Filter chips row: All / Schools / Colleges / Recent / Popular — pill style, warm-white text on default state, Spectrum Violet fill with warm-white text on active state, thin animated gradient outline on hover. When arriving from a hero institution icon, an additional chip for that institution's name appears pre-selected/active (e.g. "Delhi Public School"), showing only that institution's events; clicking "All" clears it.
- Masonry or uniform grid of Event Cards:
  - Tall portrait-ratio card.
  - Full-bleed event thumbnail as background (use placeholder gradient images or Unsplash school/event images).
  - Bottom gradient scrim (dark base to transparent) overlaid with:
    - Institution name (small caps in Spectrum Teal)
    - Event name (warm-white serif)
    - Date + photo count (small muted light gray)
    - Price badge: "From ₹29" — pill with a thin animated Spectrum Gradient border, text in warm-white
  - Hover: card lifts 6px, thumbnail zooms 5%, glowing border animates through the Spectrum Gradient (speeds up on hover, keeps cycling at rest).
- Hardcode the 6 events listed in the Dummy Data section below, spread across the 5 institutions (Ryan International has two, demonstrating an institution with multiple events).

---

Page 3 — Event Gallery Page

- Same consistent dark `#221F29` background — photos are the primary focal point on the page, gradient accents used sparingly so they read as premium punctuation, not clutter.
- Small "← All Events" text link top-left of the page content, muted light gray brightening to Spectrum Teal on hover (per the Site Navigation section above).
- Top: event name in large serif, warm-white; institution name in Spectrum Teal caps; date and photo count in muted light gray text.
- Important — each thumbnail represents a "moment," not a single photo: a school/college event has many components — speeches, performances, award ceremony, group photos, and more. Each image in the grid is a single representative glimpse of one such moment, standing in for every photo Spectrum captured during that moment. Selecting a thumbnail means the user is requesting the entire photo set from that specific moment, not just the one preview image shown.
- 3-column photo grid (2 on mobile) of hardcoded placeholder images, each representing one moment of the event — all appear as if watermarked:
  - Moment title bar on every thumbnail: a bottom gradient scrim (dark base to transparent) with the moment name in warm-white serif (e.g. "Award Distribution", "Solo Dance Performance"), and directly beneath it in small muted Spectrum Teal caps, the photo count for that moment (e.g. "24 photos in this moment").
  - Each image also has a diagonal semi-transparent text overlay: "Spectrum — Preview Only"
  - Lock icon badge in top-right corner of each photo, filled with the animated Spectrum Gradient.
  - Right-click disabled via JavaScript.
  - Drag blocked via CSS.
  - On hover: cinematic shimmer sweep left-to-right across the image (shimmer tinted with a faint spectrum hue-shift), a centered "Select This Moment" pill appears.
  - On click/select: glowing border cycling through the Spectrum Gradient + a checkmark badge in Spectrum Teal appears on the thumbnail, with the moment title bar staying visible so the selection is easy to identify. Click again to deselect.
- Hardcoded moments for the Annual Day 2025 (DPS) gallery — 18 thumbnails, each with a title and a photo count that sums to the event's 182 photos, e.g.: Welcome & Opening Address (8), Lighting the Lamp (6), Chief Guest Speech (10), Solo Dance Performance (14), Group Dance Performance (12), Musical Segment (12), Drama / Skit (16), Fashion Show Walk (10), Award Distribution (16), Prize Distribution (14), Backstage Candids (12), Audience & Crowd Shots (8), Group Photo — Faculty (6), Group Photo — Students (10), Vote of Thanks (5), Closing Ceremony (9), Finale & Confetti (7), Campus & Decor Shots (7).
- Sticky bottom bar (always visible while scrolling):
  - Same dark base with an animated Spectrum Gradient glow strip along the top edge; all bar text in warm-white for readability against the dark background.
  - Left: "3 moments selected · 42 photos · ₹87" (updates live as the user clicks — use JS to sum the photo counts of selected moments and multiply by the per-moment price).
  - Center: "Full Album Bundle — Save 43% · ₹299 for all 182 photos across every moment" (18 moments × ₹29/moment = ₹522 individually, so ₹299 is an accurate ~43% saving — keep this math in sync if the per-moment price changes)
  - Right: "Pay & Get Photos →" button filled with the animated Spectrum Gradient, warm-white text — opens checkout modal on click.

---

Component — Checkout Modal

- Triggered by clicking the pay CTA.
- Same dark base (`#1C1A22`) modal centered on a blurred dark overlay; all modal text (labels, inputs, summary) in warm-white for readability.
- Frosted glass border with a subtle animated Spectrum Gradient inner edge glow.
- Left panel: Order summary — selected moment thumbnails (small), each with its title and photo count, per-moment price, total. If bundle selected, shows bundle price instead.
- Right panel:
  - Input: "Your Name"
  - Input: "WhatsApp Number" (with WhatsApp icon)
  - Input: "Email Address" (with mail icon)
  - Toggle: "Deliver via WhatsApp / Email" — Spectrum Violet toggle switch.
  - Large button filled with the animated Spectrum Gradient, warm-white text: "Pay ₹87 with Razorpay →" — non-functional, styled only, total dynamically reflects whatever the sticky bar showed (matches the "3 moments selected" example above).
- Close button (×) top-right, in warm-white.
- On clicking the pay button → close modal → show Payment Success Screen.

---

Component — Payment Success Screen

- Full-screen overlay in the same consistent dark base.
- Slow radial light burst animation radiating from center, cycling through the Spectrum Gradient hues (CSS keyframes).
- Large animated checkmark icon filled with the animated Spectrum Gradient.
- Serif headline, in warm-white: "Your Memories Are On Their Way."
- Body, in warm-white: "We're sending your full-resolution photos to your WhatsApp right now. Check your messages in a while."
- Small muted light gray text: "Didn't receive? Contact us at support@spectrum.in"
- "Back to Events" warm-white text link below, underline in Spectrum Teal on hover.

---

Micro-interactions & Animations (All CSS/JS — No Libraries Needed Except Framer Motion)

- Scroll-triggered fade-ins on every section, all against the same consistent dark base — no background color change on scroll, only content fading in.
- Hero carousel: smooth 3D coverflow auto-rotation, drag support, touch/swipe on mobile.
- Stat counter: numbers animate up when scrolled into view, digits in animated Spectrum Gradient text-fill.
- Event card hover: lift + zoom + Spectrum Gradient glow border (gradient continuously animates at rest, speeds up on hover).
- Gallery image hover: shimmer sweep (spectrum-tinted) + Select pill.
- Photo selection: Spectrum Gradient border flash + Spectrum Teal checkmark badge, sticky bar counter updates live.
- Button hover: Spectrum Gradient glow pulse (gradient continuously animates at rest, pulses faster on hover).
- Modal open/close: smooth scale + fade transition.
- Payment success: gradient light burst + checkmark draw animation.
- Loading skeleton: dark shimmer sweep on page load, faint spectrum hue running through it.
- Ambient background glow orbs (hero, stats band, featured events) drift very slowly — a slow, almost imperceptible float — so they read as atmosphere, not motion graphics.
- All scroll animations use `IntersectionObserver` or Framer Motion's `whileInView`.
- **Universal gradient rule:** every single instance of the Spectrum Gradient across the site — logo, buttons, borders, badges, hairlines, text-fills, icons — runs a continuous, slow hue-cycle/position animation (roughly 6–10s loop, `linear`, `infinite`) as its default idle state, sweeping from warm (yellow/orange/red) into cool (teal/violet/magenta) and back. Interaction states (hover, active, selection) simply speed up or intensify this existing animation rather than turning on an animation that wasn't there before.

---

Hardcoded Dummy Data to Include

Institutions:
- Delhi Public School, New Delhi
- St. Xavier's College, Mumbai
- Ryan International School, Bengaluru
- Amity University, Noida
- The Doon School, Dehradun

Events (hardcode across institutions):
- Annual Day 2025 — DPS New Delhi — March 15 — 182 photos — ₹29/moment
- Graduation Ceremony 2025 — St. Xavier's — April 3 — 94 photos — ₹49/moment
- Sports Meet 2025 — Ryan International — Feb 20 — 210 photos — ₹29/moment
- Republic Day Celebration 2025 — Ryan International — Jan 26 — 76 photos — ₹29/moment (second event — Ryan International is the institution used to demonstrate the multi-event routing branch)
- Cultural Fest "Rang" 2025 — Amity — Jan 18 — 340 photos — ₹29/moment
- Founder's Day 2025 — The Doon School — Dec 10 — 128 photos — ₹49/moment

For gallery page: Use the 18 hardcoded moments listed in the Gallery Page spec above (Unsplash school/event photography URLs or CSS gradient placeholders if Unsplash not available), each tagged with its moment title and photo count.

---

Tech Stack — Frontend Only

- Next.js 14 (App Router) — page routing between Homepage, Events, Gallery
- Tailwind CSS — all styling
- Framer Motion — carousel, scroll animations, modal transitions, page transitions
- Vanilla JS — photo selection logic, sticky bar counter, right-click disable, modal open/close
- No backend. No API calls. No database. Everything hardcoded.

---

Pages / Routes

- `/` — Homepage (hero + stats + how it works + featured events + footer)
- `/events` — All Events listing page
- `/events/[slug]` — Gallery page (use one hardcoded slug like `annual-day-2025-dps`)
- All other event slugs can redirect to the same hardcoded gallery page

---

Build Order

Global styles and theme tokens (including the animated Spectrum Gradient, the consistent moderately-dark base, warm-white text, and ambient glow orbs) → Homepage hero with carousel (full-width, above-the-fold through the carousel) → Search bar + institution row (below the fold) → Stats band + How It Works → Featured events section → Events listing page → Gallery page with selection logic → Checkout modal → Payment success screen → Micro-interactions and scroll animations → Final polish pass.

---

The goal of this build is a client presentation showpiece. Every scroll should feel intentional. Every interaction should feel premium. The whole site should read as one consistent, moderately dark experience — never pitch-black, never a jarring mix of light and dark sections — with the Spectrum Gradient and soft ambient color glows keeping it rich and colorful without ever tipping into visual clutter, and every piece of text clearly legible against the dark base throughout. When the client opens this on their phone or laptop, they should feel immediately confident that Spectrum is a world-class platform. Make it look crazy good.

logo is attached for your reference.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/037350cc-bc61-4cec-90bc-278dbde24d8d).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
