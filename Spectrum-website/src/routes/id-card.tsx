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
  institution: string;
  email: string;
  phone: string;
};

const EMPTY: Form = {
  studentName: "",
  className: "",
  admissionNo: "",
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
  const { copy, institutions } = Route.useLoaderData();
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
        className="right-[-10%] top-24"
        colors={["#7C4DE0", "#2FBF8F"]}
        size={520}
        opacity={0.09}
      />

      <div className="relative z-10 mx-auto max-w-2xl px-6">
        <Link
          to="/"
          className="-my-2 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> {copy.backLabel}
        </Link>

        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 font-display text-4xl font-semibold leading-tight text-foreground md:text-5xl"
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
              className="spectrum-border glass mt-10 rounded-3xl bg-surface p-8 text-center md:p-10"
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
              className="spectrum-border glass mt-10 rounded-3xl bg-surface p-8 text-center text-sm font-medium text-muted-foreground"
            >
              {copy.unavailableMessage}
            </motion.p>
          ) : (
            <motion.form
              key="form"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ delay: 0.05 }}
              onSubmit={onSubmit}
              className="spectrum-border glass mt-10 grid gap-4 rounded-3xl bg-surface p-6 sm:grid-cols-2 md:p-8"
            >
              <input
                required
                value={form.studentName}
                onChange={(e) => set("studentName")(e.target.value)}
                placeholder={copy.namePlaceholder}
                className={`${inputClass} sm:col-span-2`}
              />
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
              <ServiceSelect
                name="institution"
                options={institutions.map((i) => i.name)}
                value={form.institution}
                onChange={set("institution")}
                placeholder={copy.institutionPlaceholder}
                className="sm:col-span-2"
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

              <div className="sm:col-span-2">
                <div className="spectrum-hairline mb-4 mt-2" />
                {school ? (
                  <div className="flex items-center justify-between gap-4 font-display text-foreground">
                    <span className="min-w-0 text-sm">
                      {copy.priceLabel}
                      <span className="block truncate text-xs text-muted-foreground">
                        {school.name}
                      </span>
                    </span>
                    <span className="spectrum-text shrink-0 text-2xl">₹{school.price}</span>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">{copy.priceHint}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={busy}
                className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold disabled:cursor-wait disabled:opacity-70 sm:col-span-2"
              >
                {busy
                  ? "Opening payment…"
                  : school
                    ? fill(copy.payButton, { price: school.price })
                    : copy.submitLabel}
              </button>
              {error && (
                <p
                  role="alert"
                  className="text-center text-xs font-medium text-[#ff9b6a] sm:col-span-2"
                >
                  {error}
                </p>
              )}
              {!hasApi && (
                <p className="text-center text-xs text-muted-foreground sm:col-span-2">
                  Demo form — no request is sent and no payment is processed.
                </p>
              )}
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
