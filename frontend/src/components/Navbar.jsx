import { useState } from "react";
import { AnimatePresence, motion, useScroll, useSpring } from "framer-motion";
import { Menu, X } from "lucide-react";
import Logo from "./Logo";

const links = [
  ["Projects", "#projects", "nav-projects-link"],
  ["Stack", "#stack", "nav-stack-link"],
  ["AI Workflows", "#ai", "nav-ai-link"],
  ["Services", "#services", "nav-services-link"],
  ["Contact", "#contact", "nav-contact-link"],
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 24 });

  return (
    <header className="fixed inset-x-0 top-0 z-40 border-b border-white/5 bg-black/60 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        <a href="#top" data-testid="nav-logo" aria-label="rpsahnni.dev home" onClick={() => setOpen(false)}>
          <Logo size={34} />
        </a>
        <nav className="hidden items-center gap-7 text-sm font-medium text-slate-400 md:flex">
          {links.map(([label, href, tid]) => (
            <a key={href} href={href} data-testid={tid} className="transition-colors duration-200 hover:text-emerald-400">
              {label}
            </a>
          ))}
          <a
            href="#contact"
            data-testid="nav-cta-button"
            className="rounded-full bg-emerald-500 px-5 py-2 font-semibold text-night transition-transform duration-200 hover:-translate-y-0.5 hover:bg-emerald-400"
          >
            Hire me
          </a>
        </nav>
        <button
          className="text-slate-200 md:hidden"
          aria-label="Toggle menu"
          data-testid="nav-menu-toggle"
          onClick={() => setOpen(!open)}
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.nav
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden border-t border-white/5 bg-night/95 md:hidden"
          >
            <div className="flex flex-col gap-4 px-5 py-5 text-sm font-medium text-slate-300">
              {links.map(([label, href, tid]) => (
                <a key={href} href={href} data-testid={`${tid}-mobile`} onClick={() => setOpen(false)}>
                  {label}
                </a>
              ))}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
      <motion.div className="absolute bottom-0 left-0 h-px w-full origin-left bg-emerald-400/70" style={{ scaleX }} />
    </header>
  );
}
