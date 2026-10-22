import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { ContentProvider } from "@/content";
import { useLenis } from "@/hooks/useLenis";
import Logo from "@/components/Logo";
import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Marquee from "@/components/Marquee";
import About from "@/components/About";
import Projects from "@/components/Projects";
import TechStack from "@/components/TechStack";
import AiWorkflows from "@/components/AiWorkflows";
import Services from "@/components/Services";
import Testimonials from "@/components/Testimonials";
import Contact from "@/components/Contact";
import Footer from "@/components/Footer";
import Admin from "@/pages/Admin";

function Intro() {
  return (
    <motion.div
      className="fixed inset-0 z-[100] grid place-items-center bg-night"
      initial={{ y: 0 }}
      animate={{ y: "-100%" }}
      transition={{ duration: 0.8, ease: [0.76, 0, 0.24, 1], delay: 1.1 }}
      aria-hidden="true"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.75 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <Logo size={80} withWordmark={false} />
      </motion.div>
    </motion.div>
  );
}

function Portfolio() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");
  useLenis();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <div className="relative min-h-screen bg-night font-body text-slate-300">
      <Intro />
      <div className="grain pointer-events-none fixed inset-0 z-[90] opacity-[0.04]" aria-hidden="true" />
      <Navbar dark={dark} onToggleTheme={() => setDark((d) => !d)} />
      <main>
        <Hero />
        <Marquee />
        <About />
        <Projects />
        <TechStack />
        <AiWorkflows />
        <Services />
        <Testimonials />
        <Contact />
      </main>
      <Footer />
    </div>
  );
}

export default function App() {
  return (
    <ContentProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Portfolio />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" richColors />
    </ContentProvider>
  );
}
