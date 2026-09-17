import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Clock, Mail, MapPin, MessageCircle, Phone } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { ServiceSelect } from "@/components/spectrum/service-select";
import { Highlight } from "@/components/spectrum/highlight";
import { hasApi } from "@/lib/api";
import { getContact, submitEnquiry, type Enquiry } from "@/lib/data/pages";
import { seoMeta } from "@/lib/data/site";

export const Route = createFileRoute("/contact")({
  loader: () => getContact(),
  staleTime: 60_000,
  head: ({ loaderData }) => ({ meta: seoMeta(loaderData?.seo) }),
  component: ContactPage,
});

const inputClass =
  "w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet";

const ICONS = { mail: Mail, phone: Phone, whatsapp: MessageCircle, map: MapPin, clock: Clock };

const EMPTY: Enquiry = {
  name: "",
  email: "",
  phone: "",
  institution: "",
  service: "",
  serviceOther: "",
  message: "",
};

function ContactPage() {
  const { copy, services, details } = Route.useLoaderData();
  const OTHER = copy.otherServiceOption;
  const serviceOptions = [...services, OTHER];
  const [form, setForm] = useState<Enquiry>(EMPTY);
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState("");
  const set = (key: keyof Enquiry) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (state === "sending") return;
    setError("");
    setState("sending");
    try {
      await submitEnquiry({
        ...form,
        service: form.service === OTHER ? "" : form.service,
        serviceOther: form.service === OTHER ? form.serviceOther : "",
      });
      setForm(EMPTY);
      setState("sent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setState("idle");
    }
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
        <p className="mt-4 max-w-2xl text-base font-medium text-muted-foreground">
          {copy.subtitle}
        </p>

        <div className="mt-14 grid gap-8 md:grid-cols-2">
          <motion.form
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            onSubmit={onSubmit}
            className="spectrum-border glass space-y-4 rounded-3xl bg-surface p-6 md:p-8"
          >
            <input
              required
              value={form.name}
              onChange={(e) => set("name")(e.target.value)}
              placeholder={copy.namePlaceholder}
              className={inputClass}
            />
            <input
              value={form.email}
              onChange={(e) => set("email")(e.target.value)}
              placeholder={copy.emailPlaceholder}
              type="email"
              className={inputClass}
            />
            <input
              value={form.phone}
              onChange={(e) => set("phone")(e.target.value)}
              placeholder={copy.phonePlaceholder}
              type="tel"
              className={inputClass}
            />
            <input
              value={form.institution}
              onChange={(e) => set("institution")(e.target.value)}
              placeholder={copy.institutionPlaceholder}
              className={inputClass}
            />
            <ServiceSelect
              name="service"
              options={serviceOptions}
              value={form.service}
              onChange={set("service")}
              placeholder={copy.servicePlaceholder}
            />
            <AnimatePresence initial={false}>
              {form.service === OTHER && (
                <motion.div
                  key="other"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.18 }}
                  className="overflow-hidden"
                >
                  <input
                    name="serviceOther"
                    value={form.serviceOther}
                    onChange={(e) => set("serviceOther")(e.target.value)}
                    placeholder={copy.otherServicePlaceholder}
                    className={inputClass}
                    autoFocus
                  />
                </motion.div>
              )}
            </AnimatePresence>
            <textarea
              value={form.message}
              onChange={(e) => set("message")(e.target.value)}
              placeholder={copy.messagePlaceholder}
              rows={5}
              className={`${inputClass} resize-none`}
            />
            <button
              type="submit"
              disabled={state === "sending"}
              className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold disabled:opacity-60"
            >
              {state === "sending" ? "Sending…" : copy.submitLabel}
            </button>
            {error && (
              <p role="alert" className="text-center text-xs font-medium text-[#ff9b6a]">
                {error}
              </p>
            )}
            {state === "sent" && (
              <p role="status" className="text-center text-xs font-medium text-teal">
                {copy.successMessage}
              </p>
            )}
            {!hasApi && state !== "sent" && (
              <p className="text-center text-xs text-muted-foreground">
                Demo form — messages are not sent.
              </p>
            )}
          </motion.form>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12 }}
            className="relative"
          >
            <Orb
              className="right-[-8%] top-8"
              colors={["#7C4DE0", "#2FBF8F"]}
              size={420}
              opacity={0.16}
            />
            <div className="spectrum-border glass relative rounded-3xl bg-surface p-6 md:p-8">
              <h2 className="font-display text-2xl font-semibold text-foreground">
                <Highlight text={copy.detailsHeading} />
              </h2>
              <ul className="mt-7 space-y-6">
                {details.map((d) => {
                  const Icon = ICONS[d.icon] ?? Mail;
                  return (
                    <li key={d.label} className="flex items-start gap-4">
                      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full border-2 border-violet/70">
                        <Icon className="h-5 w-5 text-foreground" />
                      </span>
                      <div>
                        <p className="font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
                          {d.label}
                        </p>
                        <p className="mt-1 text-sm font-medium text-foreground">{d.value}</p>
                      </div>
                    </li>
                  );
                })}
              </ul>
              <div className="spectrum-hairline my-7" />
              <p className="text-sm font-medium leading-relaxed text-muted-foreground">
                {copy.replyNote}
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
