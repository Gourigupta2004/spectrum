import { Link } from "@tanstack/react-router";
import { Instagram, Youtube, Facebook, Mail, Phone } from "lucide-react";

export function Footer() {
  return (
    <footer className="relative bg-surface">
      <div className="spectrum-hairline w-full" />
      <div className="mx-auto grid max-w-6xl gap-12 px-6 py-16 md:grid-cols-3">
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
          <ul className="mt-5 space-y-3 text-sm">
            <li>
              <Link to="/" className="text-foreground transition-colors hover:text-teal">
                Home
              </Link>
            </li>
            <li>
              <Link to="/events" className="text-foreground transition-colors hover:text-teal">
                Events
              </Link>
            </li>
            <li>
              <Link to="/about" className="text-foreground transition-colors hover:text-teal">
                About Us
              </Link>
            </li>
            <li>
              <Link to="/contact" className="text-foreground transition-colors hover:text-teal">
                Contact
              </Link>
            </li>
            <li>
              <Link
                to="/portal"
                className="text-muted-foreground transition-colors hover:text-teal"
              >
                Institution Login
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
