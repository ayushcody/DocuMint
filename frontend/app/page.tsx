import {
  ArrowRight,
  BadgeCheck,
  Boxes,
  Braces,
  Database,
  FileSearch,
  FileText,
  GitBranch,
  Layers3,
  LockKeyhole,
  MessageSquareQuote,
  Network,
  ScanSearch,
  Search,
  ShieldCheck,
  SplitSquareHorizontal,
  Workflow,
} from "lucide-react";

import { ParseDebugger } from "@/components/ParseDebugger";

type Feature = {
  title: string;
  description: string;
  icon: JSX.Element;
  accent: string;
};

type Agent = {
  label: string;
  title: string;
  description: string;
};

const productFeatures: Feature[] = [
  {
    title: "Parse",
    description: "Turn PDFs, scans, and images into clean LLM-ready text with page bboxes.",
    icon: <ScanSearch aria-hidden size={20} />,
    accent: "text-teal bg-[#e8faf7]",
  },
  {
    title: "Extract",
    description: "Pull structured JSON from documents and attach citations to every field.",
    icon: <Braces aria-hidden size={20} />,
    accent: "text-sky bg-[#edf5ff]",
  },
  {
    title: "Classify",
    description: "Route documents into natural-language categories using semantic similarity.",
    icon: <GitBranch aria-hidden size={20} />,
    accent: "text-[#9d5b03] bg-[#fff7e8]",
  },
  {
    title: "Split",
    description: "Separate concatenated packets into logical documents and sections.",
    icon: <SplitSquareHorizontal aria-hidden size={20} />,
    accent: "text-coral bg-[#fff1f1]",
  },
  {
    title: "Index",
    description: "Build ColQwen2-powered visual RAG search over rendered document pages.",
    icon: <Search aria-hidden size={20} />,
    accent: "text-[#5f4bb6] bg-[#f0edff]",
  },
];

const howItWorks: Feature[] = [
  {
    title: "Upload once",
    description: "Originals are stored permanently in MinIO with workspace-scoped paths.",
    icon: <FileText aria-hidden size={20} />,
    accent: "text-teal bg-[#e8faf7]",
  },
  {
    title: "Run the agents",
    description: "Intake, layout, OCR, assembly, and verifier work as a Celery pipeline.",
    icon: <Workflow aria-hidden size={20} />,
    accent: "text-sky bg-[#edf5ff]",
  },
  {
    title: "Inspect visually",
    description: "PDF.js canvas overlays show each block, confidence score, and citation.",
    icon: <FileSearch aria-hidden size={20} />,
    accent: "text-[#9d5b03] bg-[#fff7e8]",
  },
  {
    title: "Use the output",
    description: "Send clean text, JSON, page citations, and RAG hits to your product.",
    icon: <Database aria-hidden size={20} />,
    accent: "text-coral bg-[#fff1f1]",
  },
];

const agents: Agent[] = [
  {
    label: "Agent 1",
    title: "Intake & Anchoring",
    description: "Rasterizes pages at 300 DPI and preserves native PDF text coordinates.",
  },
  {
    label: "Agent 2",
    title: "Layout Detection",
    description: "Finds text, tables, figures, formulas, headers, and footers for routing.",
  },
  {
    label: "Agent 3",
    title: "Specialist Parsers",
    description: "Routes simple regions, tables, scans, and handwriting to the right parser.",
  },
  {
    label: "Agent 4",
    title: "Assembly",
    description: "Orders blocks, stitches tables, and builds the final document AST.",
  },
  {
    label: "Agent 5",
    title: "Verifier",
    description: "Renders predicted output and compares it with crops using visual checks.",
  },
  {
    label: "Agent 6",
    title: "Schema Extraction",
    description: "Produces structured fields with calibrated confidence and bbox citations.",
  },
  {
    label: "Agent 7",
    title: "Visual RAG",
    description: "Indexes page renders with ColQwen2 multi-vectors and Qdrant MaxSim search.",
  },
];

export default function Page() {
  return (
    <main className="min-h-screen bg-paper text-ink">
      <SiteNav />
      <HeroSection />
      <AccessStrip />
      <SectionShell
        eyebrow="Capabilities"
        id="operations"
        title="One document pipeline for five product operations"
      >
        <div className="grid gap-3 md:grid-cols-5">
          {productFeatures.map((feature) => (
            <FeatureCard key={feature.title} feature={feature} />
          ))}
        </div>
      </SectionShell>
      <SectionShell eyebrow="How it works" id="how-it-works" title="From upload to verified output">
        <div className="grid gap-4 md:grid-cols-4">
          {howItWorks.map((step, index) => (
            <div
              className="rounded-lg border border-line bg-white p-4 shadow-sm"
              key={step.title}
            >
              <div className={`mb-4 inline-grid h-10 w-10 place-items-center rounded-md ${step.accent}`}>
                {step.icon}
              </div>
              <p className="text-xs font-black uppercase tracking-wide text-muted">
                Step {index + 1}
              </p>
              <h3 className="mt-1 text-base font-black">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">{step.description}</p>
            </div>
          ))}
        </div>
      </SectionShell>
      <SectionShell eyebrow="Architecture" id="architecture" title="Seven agents, one auditable path">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-7">
          {agents.map((agent) => (
            <article className="rounded-lg border border-line bg-white p-4 shadow-sm" key={agent.label}>
              <p className="text-xs font-black uppercase tracking-wide text-sky">{agent.label}</p>
              <h3 className="mt-2 text-base font-black">{agent.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">{agent.description}</p>
            </article>
          ))}
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <ProofPoint icon={<LockKeyhole aria-hidden size={18} />} title="Workspace isolation" />
          <ProofPoint icon={<BadgeCheck aria-hidden size={18} />} title="Calibrated confidence" />
          <ProofPoint icon={<MessageSquareQuote aria-hidden size={18} />} title="Citations everywhere" />
        </div>
      </SectionShell>
      <SectionShell eyebrow="About" id="about" title="Built for teams that need document AI they can verify">
        <div className="grid gap-6 lg:grid-cols-[1fr_0.8fr]">
          <div className="rounded-lg border border-line bg-white p-5 shadow-sm">
            <p className="text-base leading-7 text-muted">
              DocuMind AI is designed for document-heavy teams that need more than raw OCR.
              Every parse block is traceable to a page region, every extracted value carries a
              citation, and every confidence score exposes calibrated and raw values. The product
              is self-hostable, workspace-scoped, and built for debugging failures instead of
              hiding them.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <Tag label="FastAPI" />
              <Tag label="PostgreSQL RLS" />
              <Tag label="MinIO" />
              <Tag label="Celery" />
              <Tag label="Qdrant" />
              <Tag label="PDF.js Canvas" />
            </div>
          </div>
          <div className="rounded-lg border border-line bg-[#172026] p-5 text-white shadow-dock">
            <ShieldCheck aria-hidden className="text-[#7de2d1]" size={28} />
            <h3 className="mt-4 text-xl font-black">Core promise</h3>
            <p className="mt-3 text-sm leading-6 text-white/75">
              Do not trust black-box document output. Inspect the crop, verify the rendered
              result, calibrate the score, and keep the correction loop attached to the source.
            </p>
          </div>
        </div>
      </SectionShell>
      <section className="border-t border-line bg-[#edf5ff] px-3 py-4" id="studio">
        <div className="mx-auto mb-4 flex max-w-7xl flex-wrap items-end justify-between gap-3 px-1">
          <div>
            <p className="text-xs font-black uppercase tracking-wide text-sky">Live studio</p>
            <h2 className="display-font mt-1 text-2xl font-black md:text-4xl">
              Parse and inspect a document
            </h2>
          </div>
          <a
            className="inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-black text-white shadow-sm transition hover:-translate-y-0.5"
            href="#top"
          >
            Back to overview
          </a>
        </div>
        <div className="mx-auto max-w-[1600px] overflow-hidden rounded-lg border border-line bg-white shadow-dock">
          <ParseDebugger />
        </div>
      </section>
    </main>
  );
}

function SiteNav() {
  return (
    <header
      className="sticky top-0 z-30 border-b border-line bg-white/90 px-3 py-3 backdrop-blur"
      id="top"
    >
      <nav className="mx-auto flex max-w-7xl items-center justify-between gap-3">
        <a className="flex items-center gap-3" href="#top">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-ink text-white">
            <Layers3 aria-hidden size={18} />
          </span>
          <span className="display-font text-lg font-black">DocuMind AI</span>
        </a>
        <div className="hidden items-center gap-5 text-sm font-bold text-muted md:flex">
          <a className="hover:text-ink" href="#operations">
            Operations
          </a>
          <a className="hover:text-ink" href="#how-it-works">
            How it works
          </a>
          <a className="hover:text-ink" href="#architecture">
            Architecture
          </a>
          <a className="hover:text-ink" href="#about">
            About
          </a>
        </div>
        <a
          className="inline-flex h-9 items-center gap-2 rounded-md bg-sky px-3 text-sm font-black text-white shadow-sm transition hover:-translate-y-0.5"
          href="#studio"
        >
          Open Studio <ArrowRight aria-hidden size={15} />
        </a>
      </nav>
    </header>
  );
}

function HeroSection() {
  return (
    <section className="mx-auto grid max-w-7xl gap-6 px-4 py-9 md:gap-8 md:py-14 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
      <div>
        <p className="inline-flex rounded-md border border-line bg-white px-3 py-1 text-xs font-black uppercase tracking-wide text-teal shadow-sm">
          Verifiable Document AI
        </p>
        <h1 className="display-font mt-4 text-5xl font-black leading-[1.02] md:mt-5 md:text-7xl">
          DocuMind AI
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted md:mt-5 md:text-lg md:leading-8">
          Parse, extract, classify, split, and index documents with visual citations,
          calibrated confidence, and a debugger that shows exactly where each result came from.
        </p>
        <div className="mt-6 flex flex-wrap gap-3 md:mt-7">
          <a
            className="inline-flex h-11 items-center gap-2 rounded-md bg-ink px-5 text-sm font-black text-white shadow-dock transition hover:-translate-y-0.5"
            href="#studio"
          >
            Try Parse Studio <ArrowRight aria-hidden size={16} />
          </a>
          <a
            className="inline-flex h-11 items-center gap-2 rounded-md border border-line bg-white px-5 text-sm font-black text-ink shadow-sm transition hover:-translate-y-0.5"
            href="#architecture"
          >
            View Architecture
          </a>
        </div>
      </div>
      <ProductPreview />
    </section>
  );
}

function ProductPreview() {
  const rows = ["Invoice No: INV-912371", "Vendor: Acme Corp", "Total: $4,250.00"];

  return (
    <div className="rounded-lg border border-line bg-white p-3 shadow-dock">
      <div className="grid gap-3 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-md border border-line bg-[#f8fafc] p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-black uppercase tracking-wide text-muted">PDF page</span>
            <span className="rounded-md bg-[#e8faf7] px-2 py-1 text-xs font-black text-teal">
              canvas overlays
            </span>
          </div>
          <div className="relative aspect-[16/9] rounded-md border border-line bg-white p-4 md:aspect-[3/4] md:p-5">
            <div className="h-5 w-28 rounded bg-[#d8e3e8]" />
            <div className="mt-5 space-y-2 md:mt-7 md:space-y-3">
              <div className="h-3 w-full rounded bg-[#e3ebef]" />
              <div className="h-3 w-10/12 rounded bg-[#e3ebef]" />
              <div className="h-3 w-11/12 rounded bg-[#e3ebef]" />
            </div>
            <div className="absolute left-[14%] top-[26%] h-[10%] w-[60%] rounded border-2 border-teal bg-[#7de2d1]/15" />
            <div className="absolute left-[18%] top-[62%] h-[12%] w-[68%] rounded border-2 border-coral bg-[#ff7a7a]/10" />
            <div className="absolute bottom-[10%] left-[14%] h-[11%] w-[72%] rounded border-2 border-sky bg-[#2f80ed]/10" />
          </div>
        </div>
        <div className="hidden rounded-md border border-line bg-ink p-4 text-white md:block">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-wide text-white/60">
            <Network aria-hidden size={15} /> Verified JSON
          </div>
          <div className="mt-5 space-y-3">
            {rows.map((row, index) => (
              <div className="rounded-md bg-white/8 p-3" key={row}>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-black">{row}</span>
                  <span className="rounded bg-[#7de2d1] px-2 py-1 text-xs font-black text-ink">
                    {(0.91 - index * 0.03).toFixed(2)}
                  </span>
                </div>
                <div className="text-xs text-white/60">citation: page 1, bbox attached</div>
              </div>
            ))}
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 text-center text-xs font-black">
            <span className="rounded bg-white/10 px-2 py-2">RLS</span>
            <span className="rounded bg-white/10 px-2 py-2">MinIO</span>
            <span className="rounded bg-white/10 px-2 py-2">Qdrant</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function AccessStrip() {
  return (
    <section className="border-y border-line bg-white px-4 py-4">
      <div className="mx-auto grid max-w-7xl gap-3 md:grid-cols-3">
        <ProofPoint icon={<ShieldCheck aria-hidden size={18} />} title="Every field has a citation" />
        <ProofPoint icon={<Boxes aria-hidden size={18} />} title="Self-hostable BYOC stack" />
        <ProofPoint icon={<Database aria-hidden size={18} />} title="RAG-ready visual page index" />
      </div>
    </section>
  );
}

function SectionShell({
  children,
  eyebrow,
  id,
  title,
}: {
  children: React.ReactNode;
  eyebrow: string;
  id: string;
  title: string;
}) {
  return (
    <section className="mx-auto max-w-7xl px-4 py-12 md:py-16" id={id}>
      <div className="mb-6">
        <p className="text-xs font-black uppercase tracking-wide text-sky">{eyebrow}</p>
        <h2 className="display-font mt-2 text-3xl font-black md:text-5xl">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function FeatureCard({ feature }: { feature: Feature }) {
  return (
    <article className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className={`mb-4 inline-grid h-10 w-10 place-items-center rounded-md ${feature.accent}`}>
        {feature.icon}
      </div>
      <h3 className="text-lg font-black">{feature.title}</h3>
      <p className="mt-2 text-sm leading-6 text-muted">{feature.description}</p>
    </article>
  );
}

function ProofPoint({ icon, title }: { icon: JSX.Element; title: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-line bg-white px-4 py-3 shadow-sm">
      <span className="grid h-9 w-9 place-items-center rounded-md bg-[#edf5ff] text-sky">{icon}</span>
      <span className="text-sm font-black">{title}</span>
    </div>
  );
}

function Tag({ label }: { label: string }) {
  return (
    <span className="rounded-md border border-line bg-[#f8fafc] px-3 py-1 text-xs font-black text-muted">
      {label}
    </span>
  );
}
