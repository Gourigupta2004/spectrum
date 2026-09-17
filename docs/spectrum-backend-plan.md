# Spectrum — Django backend + admin + frontend wiring

## Context

The repo is a hardcoded TanStack Start frontend (Lovable template, SSR on Cloudflare Workers). Every image is an Unsplash URL or an SVG data-URI, every text is an inline constant, and the portal keeps state in three in-memory stores that reset on refresh. The client demo works, but nothing is editable and nothing persists.

Goal: a Django backend where **every piece of content except the footer is editable from admin**, **every image is an uploaded file on S3** (local disk in dev), **every batch of photos is bulk-uploaded by drag-drop / multi-select / clipboard paste**, and the admin has the fewest possible steps. Then wire the existing frontend to it **without losing the demo data**: all current fixtures are seeded into the DB (images downloaded into storage), and the frontend keeps its TS fixtures as a fallback when `VITE_API_URL` is unset.

Decisions already made by the user:
- Monorepo: frontend moves to `Spectrum-website/`, backend lives in `Spectrum-backend/`.
- Checkout is real: Razorpay payment, delivery by Twilio WhatsApp and email, full-res downloads.
- Event gallery photos and Caption Workspace items are **independent** photo sets (two models, two bulk uploaders).
- Frontend wiring is in scope; hardcoded data is migrated, not deleted.

Routine calls made in this plan (change if you disagree): Django 5.2 + DRF, PostgreSQL, **django-q2** for image processing (ORM broker + sync mode in dev, Redis in prod; no Celery), **presigned direct-to-S3** uploads with automatic multipart fallback on local storage, **JWT in localStorage** for the portal (portal routes client-only), `djangorestframework-camel-case` so JSON field names match the existing TS types verbatim.

---

## 0. Repo restructure

```
Spectrum/
  README.md                      # new: how to run both halves
  docker-compose.yml             # new: postgres + redis for dev (optional; psql 18 is installed locally)
  Spectrum-website/              # git mv of everything frontend: src/ public/ package.json bun.lock vite.config.ts tsconfig.json eslint.config.js components.json bunfig.toml .prettierrc .prettierignore .lovable/ AGENTS.md README.md
  Spectrum-backend/              # new Django project
```
- `git mv` (not copy) so history follows. Delete untracked build dirs (`.output`, `.tanstack`, `.wrangler`, `node_modules`) and rebuild inside `Spectrum-website/`.
- Root `.gitignore`: keep the existing entries prefixed for both dirs, add `Spectrum-backend/.env`, `Spectrum-backend/media/`, `Spectrum-backend/seed/cache/`, `.venv/`.
- **Risk to flag:** Lovable sync expects the project at repo root (`.lovable/project.json`, the `@lovable.dev/vite-tanstack-config` plugin). After the move, Lovable edits may stop syncing. User accepted the layout; note it in the root README.

---

## 1. Backend scaffold — `Spectrum-backend/`

```
manage.py  pyproject.toml  .env.example  README.md
spectrum/settings/{base,dev,prod}.py   spectrum/urls.py   spectrum/storages.py   spectrum/admin_site.py
apps/content/   # site-wide + page singletons and their ordered children, enquiries
apps/catalog/   # Institution, Event, EventPhoto
apps/portal/    # Member, CaptionItem, SchoolClass, Student, JWT auth
apps/orders/    # Order, OrderItem, Payment, WebhookEvent, DownloadToken, Delivery
apps/uploads/   # ProcessedImage mixin, UploadBatch, admin upload endpoints, JS uploader, processing tasks, seed command
seed/fixtures.json   seed/cache/ (gitignored)
deploy/{gunicorn.service,qcluster.service,nginx.conf}
```

Packages (`pyproject.toml`, use `python3 -m venv .venv && .venv/bin/python -m ensurepip && pip install -e .` or Poetry which is installed): `Django~=5.2`, `djangorestframework~=3.16`, `djangorestframework-camel-case`, `djangorestframework-simplejwt`, `django-cors-headers`, `django-solo`, `django-storages[s3]`, `boto3`, `Pillow`, `pillow-heif`, `django-q2`, `django-redis`, `razorpay`, `twilio`, `natsort`, `psycopg[binary]`, `gunicorn`, `requests`, `python-dotenv`.

Settings essentials:
- `STORAGES`: `default` = `PublicMediaStorage` (S3, public-read, long `CacheControl`, optional `custom_domain` for CloudFront), `private` = `PrivateMediaStorage` (S3, private, presigned GET 1 h). Dev: both are `FileSystemStorage` under `media/public` and `media/private`, served by Django in DEBUG.
- `Q_CLUSTER`: dev `{"orm": "default", "sync": True}` (tasks run inline, no Redis); prod `{"redis": ..., "workers": 2, "timeout": 120, "retry": 180, "max_attempts": 3}`.
- `CACHES`: dev LocMem; prod django-redis (shared across gunicorn + qcluster so invalidation works).
- DRF: `CamelCaseJSONRenderer/Parser`, `AllowAny` default, JWT auth class, `ConditionalGetMiddleware` for ETags.
- CORS: `CORS_ALLOWED_ORIGINS=[site origin]`, no credentials, `authorization` header allowed.
- Admin: `spectrum/admin_site.py` custom `AdminSite` with title "Spectrum", grouped index (see §7), Groups/Q tables/token-blacklist unregistered.

---

## 2. Image pipeline — `apps/uploads/`

**Mixin** (`apps/uploads/models.py`), inherited by every image-bearing model:
```
ProcessedImage (abstract): original (private storage, upload_to=uuid key), thumb (400px WebP), web (1600px WebP, EXIF stripped),
  width, height, original_name, original_size, status pending|processing|ready|failed, error, processed_at, sort_order
WatermarkedImage(ProcessedImage): + preview (1200px WebP with tiled diagonal "Spectrum · Preview Only" text)  # EventPhoto only
```
Public serializers always expose `web` (or `preview` for gallery photos), never `original`.

**Processing task** `apps/uploads/tasks.py::process_image(model_label, pk)`: claim row (`status in pending/failed` → `processing`), open original via storage, `pillow_heif` opener, `Image.draft` for JPEG, `ImageOps.exif_transpose`, produce variants, save with `update_fields`. Failure → `failed` + error text; admin action "Reprocess". Single-image models (Institution image, Event cover, story images, SiteSettings logos) enqueue the same task from `post_save` when `original` changed.

**Bulk upload endpoints** (`apps/uploads/views.py`, mounted at `/admin/uploads/`, `@staff_member_required`, CSRF via `X-CSRFToken`, per-target `add_*` permission):

| Method | URL | Purpose |
|---|---|---|
| POST | `/admin/uploads/batches/` | body `{target, parentId?, files:[{clientId,name,size,type}]}` → `{batchId, mode:"s3"\|"direct", files:[{clientId,key,uploadUrl?}]}`; rejects >40 MB / bad type; `mode` chosen by whether private storage is S3 |
| PUT | `uploadUrl` | browser → S3 presigned PUT (s3 mode) |
| POST | `/admin/uploads/batches/{id}/files/{clientId}/` | multipart fallback (direct mode) |
| POST | `/admin/uploads/batches/{id}/commit/` | `{files:[{clientId,index,key,name,size}]}` → creates rows, idempotent per (batch, clientId) |
| GET | `/admin/uploads/batches/{id}/` | `{total,pending,processing,ready,failed}` for the progress poll |
| POST | `/admin/uploads/batches/{id}/retry-failed/` | re-enqueue |

`UploadBatch(id uuid, target, parent_id, created_by, base_sort_order)`; `sort_order = base + index` where index is the client's natural-sorted position, so ordering never depends on upload completion order. Default name = humanized filename stem (strip ext, `_`/`-` → space; leave camera names like `DSC01234` alone).

**Target registry** (`apps/uploads/registry.py`): `catalog.eventphoto` (parent event, name→title), `portal.captionitem` (parent event, name→moment_title, defaults status/requested = needs-caption), `portal.student` (parent school_class, name stays blank), `content.heroslide` (name→caption), `content.tieup` (name→name).

**Admin mixin** `BulkUploadAdminMixin(bulk_upload_targets=[...])`: overrides `change_form_template` to render one drop zone per target under the fieldsets, only on the change page (Add page defaults to "Save and continue" so the user lands on the uploader immediately). Below the drop zone: a read-only thumbnail grid (`only("id","thumb","title","status")`, 200 per page) with a link to the child changelist for `list_editable` titles/order. **No TabularInline of hundreds of rows.**

**JS uploader** `apps/uploads/static/uploads/bulk-uploader.js` (vanilla, no build): drop zone (folders via `webkitGetAsEntry`), `<input type=file multiple accept="image/*,.heic,.heif">`, `document` `paste` handler reading `clipboardData.files` (multi-file paste is Chromium-only; label the hint accordingly), natural sort, prepare in chunks of 200, 4 concurrent XHRs with progress, retry 3× with backoff (403 on presign → re-prepare), commit every 25 files, `beforeunload` guard, then polls processing counts until done and refreshes the grid.

S3 bucket CORS: allow `PUT` from the Django admin origin, `Content-Type` header, expose `ETag`.

---

## 3. Content models — `apps/content/` (everything except the footer)

Singletons via `django-solo` (one click from the admin index straight to the form). Text fields that need the gradient word use a `[word]` markup convention rendered by a `<Highlight>` component in the frontend (e.g. `Every Moment, [Yours] Forever`).

| Model | Fields (all editable) | Children (ordered inlines / bulk) |
|---|---|---|
| `SiteSettings` | logo_light, logo_mark, favicon (ProcessedImage-style single images); intro_video_webm, intro_video_mp4 (FileField), intro_tagline_line1 `[Five Decades]`, intro_tagline_line2, skip_label; nav labels (events/about/contact); default SEO title/description/og; not-found + error copy | — |
| `HomePage` | seo (title, description, og_title, og_description); hero_title `Every Moment, [Yours] Forever`, hero_subtitle; search_placeholder; institutions_heading; services_heading, services_subtitle; featured_heading, featured_cta_label | `HeroSlide(ProcessedImage: caption)` **bulk**; `Stat(value, suffix, label)`; `Service(label)` (also feeds contact dropdown) |
| `AboutPage` | seo; back_label; lead_line `Established in 1980 — Nearly [Five Decades] of …`; pull_quote; tieups_heading, tieups_subtitle, tieups_caption_template `Tied up for {years} years`; faqs_heading | `Capability(label)`; `StoryBlock(ProcessedImage: title, body, alt)`; `TieUp(ProcessedImage: name, years)` **bulk**; `Faq(question, answer)` |
| `ContactPage` | seo; title `Get In [Touch]`, subtitle; placeholders (name, email, phone, institution, service, service_other, message); submit_label; reply_note; details_heading | `ContactDetail(icon key: mail\|phone\|map, label, value)` |
| `EventsPageCopy` | seo; title, back_label; filter labels; empty_state | — |
| `GalleryCopy` | seo template `{event} Gallery — {institution}`; back_label; watermark_text; select_label, selected_label; sticky bar templates; bundle_label template; pay_cta; checkout (summary heading, placeholders, delivery toggle label, pay button template `Pay ₹{total} with Razorpay →`); success (headline, body, note, back_label) | — |
| `PortalCopy` | login labels/placeholders; workspace headings; branch card titles/copy; caption workspace labels/empty states; students labels; PDF footer line | — |
| `Enquiry` | name, email, phone, institution, service (FK Service nullable), service_other, message, created_at, handled | — |

All ordered children: `sort_order` + `SortableInline` (drag handle via `django-admin-sortable2` or plain `list_editable`; pick admin-sortable2 for one-step reordering).

Cache: every content model's `post_save/post_delete` deletes `pages:*` keys.

---

## 4. Catalog — `apps/catalog/`

```
Institution: slug (=TS id, e.g. "dps"), name, short, city, type school|college, image (ProcessedImage single), sort_order, published
Event: slug, name, institution FK, date (DateField) + date_label (display, auto-filled "March 15, 2025" if blank), price_per_photo (int ₹), bundle_price (int ₹, default 299), cover (ProcessedImage single), is_recent, is_popular, published, sort_order
EventPhoto(WatermarkedImage): event FK, title
```
- `photos` count = annotation `Count("photos", filter=Q(status="ready"))`.
- `tags` computed from the two booleans (`["recent","popular"]`).
- `bundleSavings` computed server-side and returned; frontend stops importing the constant.
- `EventAdmin`: fieldsets (basics, pricing, cover) + **two drop zones** (Gallery photos → `catalog.eventphoto`; Caption items → `portal.captionitem`). `EventPhotoAdmin` changelist: thumb, title, status, sort_order (`list_editable`), filter by event.

---

## 5. Portal — `apps/portal/`

```
Member: user OneToOne(auth.User), institution FK (null for Spectrum staff), role institution|spectrum, display_name
CaptionItem(ProcessedImage): event FK, institution FK (denormalised), moment_title, caption, correction, requested (3 needs-* choices),
  status (5 choices), action_by, updated_at, seed_key
SchoolClass: institution FK, name ("6C"), group Primary|Middle|Senior, sort_order
Student(ProcessedImage): school_class FK, name (blank until named), roll_no (=sort_order+1), seed_key
```
- Login uses **Institution ID + password** as today: username = institution login id (e.g. `dps-newdelhi`). JWT (simplejwt): access 30 min, refresh 14 d, rotation + blacklist.
- Resolve is validated server-side: `approved` is terminal; `needs-caption` → caption text → `corrected`; `needs-approval` → `approved`; `needs-correction/corrected` → correction note → `corrected` (mirrors `submit()` in `portal.workspace.events.tsx:440-446`). `action_by` comes from the request body (free-text "by" field is kept in the UI) and `updated_at` is set server-side.
- `SchoolClassAdmin` gets the bulk uploader (`portal.student`); class size = number of students. `StudentAdmin` changelist: thumb, class, name (`list_editable`).
- Every portal queryset is scoped by `request.member.institution_id`; Spectrum-role members can pass `?institution=`.

---

## 6. Orders, payment, delivery — `apps/orders/`

```
Order: id uuid, public_id (10-char), event FK, kind photos|bundle, name, email, phone (E.164), deliver_whatsapp, deliver_email,
  amount_paise, currency, status created|paid|failed|delivered|refunded, razorpay_order_id, idempotency_key, zip_file (private), paid_at, delivered_at
OrderItem: order FK, photo FK(PROTECT), unit_price_paise, unique(order, photo)
Payment: order FK, razorpay_payment_id unique, signature, method, amount_paise, status, verified_via client|webhook, raw JSON
WebhookEvent: provider, event_id unique, type, payload, processed_at
DownloadToken: order OneToOne, token, downloads, disabled
Delivery: order FK, channel email|whatsapp, status pending|sent|delivered|failed, attempts, last_error, provider_message_id, sent_at
```
Flow: `POST /api/orders/` recomputes price from DB, creates Razorpay order, returns `keyId + razorpayOrderId`; client opens Razorpay Checkout; `POST /api/orders/{id}/verify/` verifies signature; webhook `POST /api/webhooks/razorpay/` verifies with the webhook secret and dedupes via `WebhookEvent`. Both paths converge in `services.mark_paid()` (`select_for_update`, idempotent) → `on_commit` enqueue `fulfil_order` → materialise bundle items, build zip on disk to private storage, create `DownloadToken`, create `Delivery` rows, enqueue `send_delivery` per channel. Email via Django SMTP backend (console in dev); WhatsApp via Twilio Content Template (pre-approved) with `status_callback` → `POST /api/webhooks/twilio/status/`. Retries with backoff up to 3, then `failed`.

`GET /api/downloads/{token}/` mints fresh 1-hour presigned GETs each call, so the link in the message never expires. Frontend gets a `/downloads/$token` route.

Admin: `OrderAdmin` with read-only Payment/Delivery inlines, status badge, search by public id/email/phone/payment id, actions **Resend email / Resend WhatsApp / Re-run fulfilment**, copyable download link. `DeliveryAdmin` filtered to failed = support queue.

---

## 7. Admin index layout (minimum steps)

```
SITE CONTENT   Site settings · Home page · About page · Contact page · Events page · Gallery & checkout copy · Portal copy
CATALOG        Institutions · Events (upload gallery + caption items here) · Event photos (titles/order)
PORTAL         Classes (upload student photos here) · Students (names) · Caption items · Members
INBOX          Enquiries · Orders · Deliveries
```
Hidden: Groups, django-q tables (except Failed tasks), token blacklist. Each singleton is one click; each batch is "open parent → drop files → done" with no Save button needed.

---

## 8. Public + portal API (camelCase, IDs as strings, shapes = existing TS types)

| Method | URL | Returns |
|---|---|---|
| GET | `/api/site/` | SiteSettings payload (logos, intro video, taglines, nav labels, default SEO, 404/error copy) |
| GET | `/api/pages/home/` | `{copy, seo, heroSlides:[{id,src,caption}], stats:[{to,suffix,label}], services:string[], institutions:Institution[], events:SpectrumEvent[]}` |
| GET | `/api/pages/about/` | `{copy, seo, capabilities, story:[{title,body,image,alt}], tieUps:[{name,years,image}], faqs:[{q,a}]}` |
| GET | `/api/pages/contact/` | `{copy, seo, services, details:[{icon,label,value}]}` |
| GET | `/api/pages/events/`, `/api/pages/gallery/`, `/api/pages/portal/` | copy singletons |
| GET | `/api/institutions/` | `Institution[]` |
| GET | `/api/events/?institution=&type=&tag=` | `SpectrumEvent[]` (`slug,name,institutionId,institution,date,photos,pricePerPhoto,image,tags`) |
| GET | `/api/events/{slug}/` | `SpectrumEvent & {gallery:[{id,title,image}], bundlePrice, bundleSavings}` (ready photos, preview URLs) |
| POST | `/api/contact/` | creates Enquiry → 201 |
| POST | `/api/portal/auth/token/` `/refresh/` `/logout/` | simplejwt |
| GET | `/api/portal/me/` | `{id, displayName, role, institution:{id,name,city}, events:[{slug,name}]}` |
| GET | `/api/portal/caption-items/?event=` | `CaptionItem[]` (exact TS shape) |
| POST | `/api/portal/caption-items/{id}/resolve/` | `{status, caption?, correction?, actionBy}` → item |
| POST | `/api/portal/caption-items/` (multipart) and `/{id}/image/` | spectrum role: add / replace image |
| GET | `/api/portal/classes/` | `SchoolClass[] & {size, namedCount}`; plus `totals:{students, named}` for the branch badge |
| GET | `/api/portal/classes/{id}/` | `{...cls, students:[{id,photo,name}]}` |
| PUT | `/api/portal/classes/{id}/names/` | `{names:{[studentId]:name}}` → bulk_update |
| POST/GET | `/api/orders/`, `/api/orders/{id}/verify/`, `/api/orders/{id}/` | see §6 |
| GET | `/api/downloads/{token}/` | purchased items with fresh signed URLs |

Efficiency: page payloads built with ≤5 queries and stored in cache with no TTL (explicit invalidation on save); `select_related("institution")` + `only()` on photo lists; public views `@cache_control(public, max_age=60, s_maxage=300)` + ETag 304s; public image URLs are plain (no signing per URL). Portal endpoints uncached, ETag only.

---

## 9. Seed: migrate the hardcoded data

1. `Spectrum-website/scripts/export-fixtures.ts` (run with `bun`): imports `spectrum-data.ts`, `caption-data.ts`, `student-data.ts` and the new `src/lib/page-fixtures.ts` (the inline consts moved out of `about.tsx:29-115`, `contact.tsx:34-38`, `index.tsx:151-155`, `brand-intro.tsx` taglines, plus all `head()` meta and page copy strings) → writes `Spectrum-backend/seed/fixtures.json` (committed).
2. `manage.py seed_fixtures [--sync] [--skip-images]`: upserts by natural key (institution slug, event slug, class id, student id `6c-1`, caption `c-1`, hero slide index, tie-up name), downloads each Unsplash URL once into `seed/cache/` with a thread pool, saves as `original`, enqueues/ runs processing. Student SVG avatars are rendered to PNG with Pillow (same hue formula as `avatar()` in `student-data.ts:51`). Copies `public/spectrum-logo-light.png`, `spectrum-mark.png`, `favicon.png`, `spr-intro.*` into SiteSettings. Creates the demo member `dps-newdelhi` / `demo` (institution role) and a `spectrum` staff member. Idempotent.

---

## 10. Frontend wiring — `Spectrum-website/`

- `src/lib/api.ts`: `API_URL = import.meta.env.VITE_API_URL`, `hasApi`, `apiFetch<T>()` with JSON/Bearer handling and one 401→refresh retry.
- `src/lib/page-fixtures.ts`: exported copies of the inline consts (routes import from here in fallback mode).
- `src/lib/data/{site,pages,events,portal,orders}.ts`: one `getX()` per resource; the **only** `hasApi` branch in the app; return the existing TS types (`SpectrumEvent`, `Photo`, `CaptionItem`, `SchoolClass`, `Student`) so components don't change shape. Fallback builds objects from the fixtures. In prod (`hasApi`) a failed fetch throws (no silent fallback that masks outages).
- Public routes: add `loader` + `Route.useLoaderData()` (`index.tsx`, `about.tsx`, `contact.tsx`, `events/index.tsx`, `events/$slug.tsx`); `head: ({loaderData})` for dynamic titles; `staleTime: 60_000`. `$slug` finally reads its param. `__root.tsx` loads `/api/site/` for logos/nav/SEO/404 copy. `Highlight` component renders `[word]` markup.
- Contact form: controlled inputs → `POST /api/contact/`, success/error state; remove "Demo form" note when `hasApi`.
- Portal: `ssr: false` on `/portal`; `src/lib/auth.ts` (tokens in `localStorage["spectrum.portal"]`); `sessionStore` → `useAuth()`; `portalRole/portalInstitution` → `useMe()`. `captionStore` → `useQuery(["portal","captions"])` + `useMutation` with the same optimistic patch `resolve()` applies today. `namesStore` → class query + `useNameFlush()` that batches name commits into one `PUT …/names/` 600 ms after the last Enter/blur (and on `pagehide` with `keepalive`), keeping Enter-to-next untouched. `exportRosterPdf` takes server-named students (drop the names map). Add Image / Replace photo → multipart mutations.
- Checkout: `checkout-modal.tsx` becomes controlled; on Pay → `createOrder` → load Razorpay checkout.js → `verify` → `onPaid`; success overlay polls `/api/orders/{id}/` and shows the download link. Demo mode keeps today's fake flow. New route `routes/downloads/$token.tsx`.
- `wrangler`/build: set `VITE_API_URL` at build time (inlined; same value on Worker and browser). API must be HTTPS:443 for Workers. Loaders never touch `localStorage`.
- Keep `spectrum-data.ts`, `caption-data.ts`, `student-data.ts` in place as the fallback source; `roster-pdf.ts` stays client-side.

---

## 11. Implementation order

1. Repo move (§0) → confirm `bun dev` still runs from `Spectrum-website/`.
2. Backend scaffold + settings + storages + admin site (§1).
3. `apps/uploads` mixin, task, registry, endpoints, JS uploader, admin mixin (§2) — build once, reuse everywhere.
4. `apps/content` models + solo admin + page endpoints + cache signals (§3, §8).
5. `apps/catalog` + EventAdmin with both uploaders + public events API (§4).
6. `apps/portal` models, JWT, scoped endpoints, class/student admin (§5).
7. `apps/orders` + Razorpay + fulfilment + Twilio/email + downloads + support admin (§6).
8. Export script + `seed_fixtures` (§9); run it; eyeball admin.
9. Frontend wiring (§10) route by route; portal last; checkout with Razorpay test keys.
10. Deploy files (`deploy/`), `.env.example`, root README.

---

## 12. Verification

- **Backend unit/API**: `manage.py test` covering: upload prepare/commit idempotency and sort_order; process_image on a JPEG with EXIF rotation and on a HEIC; caption resolve state machine; portal scoping (institution A can't read B); order price recomputation, signature verification (client + webhook), webhook dedupe; page payload query counts with `assertNumQueries`.
- **Seed**: fresh DB → `migrate` → `seed_fixtures --sync` → `/api/pages/home/` returns 8 slides, 3 stats, 9 services, 5 institutions, 6 events; `/api/events/annual-day-2025-dps/` returns 18 ready gallery photos with preview URLs; `/api/portal/classes/` returns 30 classes, 5 named students.
- **Admin manual pass**: log in → Events → Annual Day → drop 30 files → progress bar → thumbnails appear → titles editable on the changelist. Repeat with clipboard paste in Chrome. Classes → 6C → drop headshots → students appear unnamed. Home page → hero slides drop zone. Every string on every public page is found in exactly one admin form.
- **Frontend**: `bun dev` with `VITE_API_URL` unset renders identically to today (fixtures). With `VITE_API_URL=http://localhost:8000` all pages render from the API; `/events/<other-slug>` shows that event, not DPS; contact form creates an Enquiry; portal login `dps-newdelhi/demo` → approve a caption → refresh → still approved; name three students → refresh → persisted; PDF export uses server names.
- **Checkout**: Razorpay test keys → pay with test card → order `paid` → email in console backend contains the download link → `/downloads/<token>` lists files with working signed URLs → WhatsApp delivery via Twilio sandbox to an opted-in number → Twilio status callback flips Delivery to `delivered` → admin "Resend" works.
- **Prod smoke**: S3 bucket CORS PUT from admin origin; `qcluster` processing a 200-file batch under 2 workers without OOM; Cloudflare Worker SSR fetching the HTTPS API.
