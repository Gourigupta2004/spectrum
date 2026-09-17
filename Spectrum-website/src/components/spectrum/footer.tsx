import { Link } from "@tanstack/react-router";
import { Instagram, Youtube, Facebook, Mail, Phone } from "lucide-react";
import { useSite } from "@/lib/use-site";

export function Footer() {
  // Same labels as the navbar, so renaming a page in the admin renames it everywhere.
  const { copy } = useSite();
  return (
    <footer className="relative bg-surface">
      <div className="spectrum-hairline w-full" />
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 md:gap-12 md:py-16 md:grid-cols-3">
        <div>
          <img
            src="/spectrum-logo-light.png"
            alt="Spectrum"
            className="h-9 w-auto"
            draggable={false}
          />
          <p className="mt-4 font-display text-lg text-foreground">Imagination That Works</p>
          <p className="mt-2 max-w-xs text-sm text-muted-foreground">
            Premium photography and videography for institutions across India.
          </p>
        </div>

        <div className="md:justify-self-center">
          <h3 className="font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Quick Links
          </h3>
          <ul className="mt-4 space-y-1 text-sm">
            <li>
              <Link
                to="/"
                className="inline-block py-1.5 text-foreground transition-colors hover:text-teal"
              >
                {copy.navHome}
              </Link>
            </li>
            <li>
              <Link
                to="/events"
                className="inline-block py-1.5 text-foreground transition-colors hover:text-teal"
              >
                {copy.navEvents}
              </Link>
            </li>
            <li>
              <Link
                to="/about"
                className="inline-block py-1.5 text-foreground transition-colors hover:text-teal"
              >
                {copy.navAbout}
              </Link>
            </li>
            <li>
              <Link
                to="/contact"
                className="inline-block py-1.5 text-foreground transition-colors hover:text-teal"
              >
                {copy.navContact}
              </Link>
            </li>
            <li>
              <Link
                to="/portal"
                className="inline-block py-1.5 text-muted-foreground transition-colors hover:text-teal"
              >
                {copy.footerPortalLink}
              </Link>
            </li>
          </ul>
        </div>

        <div id="contact" className="md:justify-self-end">
          <h3 className="font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Contact
          </h3>
          <ul className="mt-5 space-y-3 text-sm text-muted-foreground">
            <li className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-teal" /> support@spectrum.in
            </li>
            <li className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-teal" /> +91 98100 44120
            </li>
          </ul>
          <div className="mt-6 flex gap-3">
            {[Instagram, Youtube, Facebook].map((Icon, i) => (
              <a
                key={i}
                href="#"
                aria-label="Social link"
                className="group grid h-10 w-10 place-items-center rounded-full border border-violet/60 transition-all hover:border-transparent"
              >
                <span className="absolute h-10 w-10 rounded-full opacity-0 transition-opacity group-hover:opacity-100 spectrum-fill" />
                <Icon className="relative h-4 w-4 text-foreground" />
              </a>
            ))}
          </div>
        </div>
      </div>
      <p className="pb-8 text-center text-xs text-muted-foreground">
        © 2025 Spectrum. All rights reserved.
      </p>
    </footer>
  );
}
