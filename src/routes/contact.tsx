import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Mail, Phone, MapPin } from "lucide-react";
import { Orb } from "@/components/spectrum/orb";
import { ServiceSelect } from "@/components/spectrum/service-select";
import { services } from "@/lib/spectrum-data";

export const Route = createFileRoute("/contact")({
  head: () => ({
    meta: [
      { title: "Contact Spectrum — Book Event Photography" },
      {
        name: "description",
        content:
          "Talk to Spectrum about covering your school or college event. Email, WhatsApp or send us a message and we'll plan the shoot.",
      },
      { property: "og:title", content: "Contact Spectrum" },
      {
        property: "og:description",
        content: "Get in touch with Spectrum for school and college event photography in India.",
      },
    ],
  }),
  component: ContactPage,
});

const inputClass =
  "w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet";

const OTHER = "Other";
const serviceOptions = [...services, OTHER];

const details = [
  { icon: Mail, label: "Email", value: "support@spectrum.in" },
  { icon: Phone, label: "Phone / WhatsApp", value: "+91 98100 44120" },
  { icon: MapPin, label: "Studio", value: "2nd Floor, Hauz Khas Village, New Delhi 110016" },
];

function ContactPage() {
  const [service, setService] = useState("");

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
          className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Home
        </Link>

        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 font-display text-4xl font-semibold leading-tight text-foreground md:text-6xl"
        >
          Get In <span className="spectrum-text">Touch</span>
        </motion.h1>
        <p className="mt-4 max-w-2xl text-base font-medium text-muted-foreground">
          Planning an annual day, fest or graduation? Tell us the date and we'll take it from there.
        </p>

        <div className="mt-14 grid gap-8 md:grid-cols-2">
          <motion.form
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            onSubmit={(e) => e.preventDefault()}
            className="spectrum-border glass space-y-4 rounded-3xl bg-surface p-6 md:p-8"
          >
            <input placeholder="Your Name" className={inputClass} />
            <input placeholder="Email Address" type="email" className={inputClass} />
            <input placeholder="Phone Number" type="tel" className={inputClass} />
            <input placeholder="Institution" className={inputClass} />
            <ServiceSelect
              name="service"
              options={serviceOptions}
              value={service}
              onChange={setService}
              placeholder="Services"
            />
            <AnimatePresence initial={false}>
              {service === OTHER && (
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
                    placeholder="Tell us which service you need"
                    className={inputClass}
                    autoFocus
                  />
                </motion.div>
              )}
            </AnimatePresence>
            <textarea
              placeholder="Tell us about your event"
              rows={5}
              className={`${inputClass} resize-none`}
            />
            <button
              type="submit"
              className="spectrum-fill w-full rounded-xl py-3.5 text-sm font-semibold"
            >
              Send Message
            </button>
            <p className="text-center text-xs text-muted-foreground">
              Demo form — messages are not sent.
            </p>
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
                Reach us directly
              </h2>
              <ul className="mt-7 space-y-6">
                {details.map((d) => (
                  <li key={d.label} className="flex items-start gap-4">
                    <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full border-2 border-violet/70">
                      <d.icon className="h-5 w-5 text-foreground" />
                    </span>
                    <div>
                      <p className="font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
                        {d.label}
                      </p>
                      <p className="mt-1 text-sm font-medium text-foreground">{d.value}</p>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="spectrum-hairline my-7" />
              <p className="text-sm font-medium leading-relaxed text-muted-foreground">
                We reply to every enquiry within one working day. For an event happening this week,
                WhatsApp is fastest.
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
