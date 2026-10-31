import { Link } from "@tanstack/react-router";
import { Instagram, Youtube, Facebook, Mail, Phone } from "lucide-react";
import { useSite } from "@/lib/use-site";
import { fill } from "@/lib/text";

export function Footer() {
  // Everything here comes from Site settings › Footer; the quick links reuse
  // the navbar labels, so renaming a page in the admin renames it everywhere.
  const { copy, logoLight } = useSite();
  const socials = (
    [
      [Instagram, copy.footerInstagramUrl, "Instagram"],
      [Youtube, copy.footerYoutubeUrl, "YouTube"],
      [Facebook, copy.footerFacebookUrl, "Facebook"],
    ] as const
  ).filter(([, href]) => href);
  return (
    <footer className="relative bg-surface">
      <div className="spectrum-hairline w-full" />
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 md:gap-12 md:py-16 md:grid-cols-3">
        <div>
          <img src={logoLight} alt="Spectrum" className="h-9 w-auto" draggable={false} />
          {copy.footerTagline && (
            <p className="mt-4 font-display text-lg text-foreground">{copy.footerTagline}</p>
          )}
          {copy.footerDescription && (
            <p className="mt-2 max-w-xs text-sm text-muted-foreground">{copy.footerDescription}</p>
          )}
        </div>

        <div className="md:justify-self-center">
          <h3 className="font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
            {copy.footerLinksHeading}
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
                to="/institutions"
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
          </ul>
        </div>

        <div id="contact" className="md:justify-self-end">
          <h3 className="font-display text-xs uppercase tracking-[0.24em] text-muted-foreground">
            {copy.footerContactHeading}
          </h3>
          <ul className="mt-5 space-y-3 text-sm text-muted-foreground">
            {copy.footerEmail && (
              <li>
                <a
                  href={`mailto:${copy.footerEmail}`}
                  className="flex items-center gap-2 transition-colors hover:text-teal"
                >
                  <Mail className="h-4 w-4 text-teal" /> {copy.footerEmail}
                </a>
              </li>
            )}
            {copy.footerPhone && (
              <li>
                <a
                  href={`tel:${copy.footerPhone.replace(/[^\d+]/g, "")}`}
                  className="flex items-center gap-2 transition-colors hover:text-teal"
                >
                  <Phone className="h-4 w-4 text-teal" /> {copy.footerPhone}
                </a>
              </li>
            )}
          </ul>
          {socials.length > 0 && (
            <div className="mt-6 flex gap-3">
              {socials.map(([Icon, href, label]) => (
                <a
                  key={label}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={label}
                  className="group grid h-10 w-10 place-items-center rounded-full border border-violet/60 transition-all hover:border-transparent"
                >
                  <span className="absolute h-10 w-10 rounded-full opacity-0 transition-opacity group-hover:opacity-100 spectrum-fill" />
                  <Icon className="relative h-4 w-4 text-foreground" />
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
      <p className="pb-8 text-center text-xs text-muted-foreground">
        {fill(copy.footerCopyright, { year: new Date().getFullYear() })}
      </p>
    </footer>
  );
}
