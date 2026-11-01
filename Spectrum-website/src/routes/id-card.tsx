import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, BookOpen, Check } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { Highlight } from "@/components/spectrum/highlight";
import { ServiceSelect } from "@/components/spectrum/service-select";
import { GuidelinesModal } from "@/components/spectrum/guidelines-modal";
import { hasApi } from "@/lib/api";
import { getIdCardPage, payForDuplicateIdCard } from "@/lib/data/idcards";
import { newIdempotencyKey } from "@/lib/data/orders";
import { seoMeta } from "@/lib/data/site";
import { idCardGuidelines } from "@/lib/guidelines";
import { fill } from "@/lib/text";

export const Route = createFileRoute("/id-card")({
  loader: () => getIdCardPage(),
  staleTime: 60_000,
  head: ({ loaderData }) => ({ meta: seoMeta(loaderData?.seo) }),
  component: IdCardPage,
});

const inputClass =
  "w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet";

type Form = {
  studentName: string;
  className: string;
  admissionNo: string;
  cardType: string;
  lanyardColour: string;
  institution: string;
  email: string;
  phone: string;
};

const EMPTY: Form = {
  studentName: "",
  className: "",
  admissionNo: "",
  cardType: "",
  lanyardColour: "",
  institution: "",
  email: "",
  phone: "",
};

/**
 * Requesting a duplicate ID card: the student's details, the school (only
 * those that offer the service, each at its own price) and a Razorpay
 * payment. The guidelines greet every visit, and open again from the link
 * under the heading. Opened after mount, so the server render never paints
 * the modal.
 */
function IdCardPage() {
  const { copy, cardTypes, lanyardColours, institutions } = Route.useLoaderData();
  const [guidelines, setGuidelines] = useState(false);
  useEffect(() => setGuidelines(true), []);

  const [form, setForm] = useState<Form>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // One key per attempt; a fresh one after an error or a finished request.
  const [key, setKey] = useState(newIdempotencyKey);
  /** The paid request's number; null in demo mode. */
  const [done, setDone] = useState<{ number: string | null } | null>(null);
  const set = (field: keyof Form) => (value: string) => setForm((f) => ({ ...f, [field]: value }));

  const school = institutions.find((i) => i.name === form.institution);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError("");
    if (cardTypes.length && !form.cardType) return setError("Please choose the type of card.");
    if (lanyardColours.length && !form.lanyardColour)
      return setError("Please choose the color of the lanyard.");
    if (!school) return setError("Please choose your school.");
    if (form.phone.replace(/\D/g, "").length < 10)
      return setError("Please enter a valid phone number.");
    if (!hasApi) {
      setDone({ number: null });
      return;
    }
    setBusy(true);
    try {
      const paid = await payForDuplicateIdCard(
        {
          institutionId: school.id,
          studentName: form.studentName.trim(),
          className: form.className.trim(),
          admissionNo: form.admissionNo.trim(),
          cardType: form.cardType,
          lanyardColour: form.lanyardColour,
          email: form.email.trim(),
          phone: form.phone.trim(),
          idempotencyKey: key,
        },
        `${copy.priceLabel} · ${school.name}`,
      );
      if (paid) setDone({ number: paid.publicId });
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : copy.checkoutError);
      setKey(newIdempotencyKey());
    } finally {
      setBusy(false);
    }
  };

  const again = () => {
    setForm(EMPTY);
    setKey(newIdempotencyKey());
    setDone(null);
  };

  return (
    <div className="grain relative min-h-screen overflow-x-clip pb-24 pt-28">
      <Orb
        className="left-[-10%] top-24"
        colors={["#FF8A3D", "#D6339A"]}
        size={520}
        opacity={0.09}
      />

      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <Link
          to="/"
          className="-my-2 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> {copy.backLabel}
        </Link>

        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 font-display text-4xl font-semibold leading-tight text-foreground md:text-6xl"
        >
          <Highlight text={copy.title} />
        </motion.h1>
        <p className="mt-4 text-base font-medium text-muted-foreground">{copy.subtitle}</p>
        <button
          type="button"
          onClick={() => setGuidelines(true)}
          className="-my-2 mt-2 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-teal transition-colors hover:text-foreground"
        >
          <BookOpen className="h-4 w-4" /> {copy.guidelinesLink}
        </button>

        <AnimatePresence mode="wait" initial={false}>
          {done ? (
            <motion.div
              key="done"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              className="spectrum-border glass mt-9 rounded-3xl bg-surface px-6 py-12 text-center md:px-8 md:py-16"
            >
              <span className="spectrum-fill mx-auto grid h-14 w-14 place-items-center rounded-full">
                <Check className="h-6 w-6" />
              </span>
              <h2 className="mt-5 font-display text-3xl text-foreground">{copy.successTitle}</h2>
              <p className="mx-auto mt-3 max-w-md text-sm font-medium leading-relaxed text-muted-foreground">
                {done.number
                  ? fill(copy.successBody, { number: done.number })
                  : "Demo form — no request is sent and no payment is processed."}
              </p>
              <button
                type="button"
                onClick={again}
                className="spectrum-border mt-8 rounded-full px-6 py-2.5 text-sm font-semibold text-foreground"
              >
                {copy.successAgain}
              </button>
            </motion.div>
          ) : institutions.length === 0 ? (
            <motion.p
              key="unavailable"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="spectrum-border glass mt-9 rounded-3xl bg-surface p-8 text-center text-sm font-medium text-muted-foreground"
            >
              {copy.unavailableMessage}
            </motion.p>
          ) : (
            // Laid out like the Contact page: the details on the left, and on
            // the right the price and Pay button (below the details on a phone).
            <motion.form
              key="form"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ delay: 0.05 }}
              onSubmit={onSubmit}
              className="mt-9 grid gap-8 md:grid-cols-2"
            >
              <div className="spectrum-border glass space-y-4 rounded-3xl bg-surface p-6 md:p-8">
                <input
                  required
                  value={form.studentName}
                  onChange={(e) => set("studentName")(e.target.value)}
                  placeholder={copy.namePlaceholder}
                  className={inputClass}
                />
                {/* Pairs sit side by side while the panel can fit "Color of Lanyard"
                    in half its width, and stack when it can't (a phone, a tablet). */}
                <div className="@container">
                  <div className="grid gap-4 @sm:grid-cols-2">
                    <input
                      required
                      value={form.className}
                      onChange={(e) => set("className")(e.target.value)}
                      placeholder={copy.classPlaceholder}
                      className={inputClass}
                    />
                    <input
                      required
                      value={form.admissionNo}
                      onChange={(e) => set("admissionNo")(e.target.value)}
                      placeholder={copy.admissionNoPlaceholder}
                      className={inputClass}
                    />
                    {cardTypes.length > 0 && (
                      <ServiceSelect
                        name="cardType"
                        options={cardTypes}
                        value={form.cardType}
                        onChange={set("cardType")}
                        placeholder={copy.cardTypePlaceholder}
                      />
                    )}
                    {lanyardColours.length > 0 && (
                      <ServiceSelect
                        name="lanyardColour"
                        options={lanyardColours}
                        value={form.lanyardColour}
                        onChange={set("lanyardColour")}
                        placeholder={copy.lanyardPlaceholder}
                      />
                    )}
                  </div>
                </div>
                <ServiceSelect
                  name="institution"
                  options={institutions.map((i) => i.name)}
                  value={form.institution}
                  onChange={set("institution")}
                  placeholder={copy.institutionPlaceholder}
                />
                <input
                  required
                  value={form.email}
                  onChange={(e) => set("email")(e.target.value)}
                  placeholder={copy.emailPlaceholder}
                  type="email"
                  autoComplete="email"
                  className={inputClass}
                />
                <input
                  required
                  value={form.phone}
                  onChange={(e) => set("phone")(e.target.value)}
                  placeholder={copy.phonePlaceholder}
                  type="tel"
                  autoComplete="tel"
                  className={inputClass}
                />
              </div>

              <div className="relative">
                <Orb
                  className="right-[-8%] top-8"
                  colors={["#7C4DE0", "#2FBF8F"]}
                  size={420}
                  opacity={0.16}
                />
                <div className="spectrum-border glass relative rounded-3xl bg-surface p-6 md:p-8">
                  <h2 className="font-display text-2xl font-semibold text-foreground">
                    {copy.priceLabel}
                  </h2>
                  <p className="mt-2 text-sm font-medium text-muted-foreground">
                    {school ? school.name : copy.priceHint}
                  </p>
                  <AnimatePresence initial={false}>
                    {school && (
                      <motion.p
                        key="price"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.18 }}
                        className="spectrum-text overflow-hidden pt-5 font-display text-5xl font-semibold"
                      >
                        ₹{school.price}
                      </motion.p>
                    )}
                  </AnimatePresence>
                  <div className="spectrum-hairline my-7" />
                  <p className="text-sm font-medium leading-relaxed text-muted-foreground">
                    {copy.guidelinesOutro}
                  </p>
                  <button
                    type="submit"
                    disabled={busy}
                    className="spectrum-fill mt-7 w-full rounded-xl py-3.5 text-sm font-semibold disabled:cursor-wait disabled:opacity-70"
                  >
                    {busy
                      ? "Opening payment…"
                      : school
                        ? fill(copy.payButton, { price: school.price })
                        : copy.submitLabel}
                  </button>
                  {error && (
                    <p role="alert" className="mt-4 text-center text-xs font-medium text-[#ff9b6a]">
                      {error}
                    </p>
                  )}
                  {!hasApi && (
                    <p className="mt-4 text-center text-xs text-muted-foreground">
                      Demo form — no request is sent and no payment is processed.
                    </p>
                  )}
                </div>
              </div>
            </motion.form>
          )}
        </AnimatePresence>
      </div>

      <GuidelinesModal
        open={guidelines}
        onClose={() => setGuidelines(false)}
        content={idCardGuidelines(copy)}
      />
    </div>
  );
}
