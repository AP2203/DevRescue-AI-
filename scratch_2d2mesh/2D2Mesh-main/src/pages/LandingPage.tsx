import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Grid, OrbitControls, Sparkles } from "@react-three/drei";
import type { Group, Mesh } from "three";
import { useTheme } from "../hooks/useTheme";
import { Logo } from "../components/layout/AppShell";
import { Icon } from "../components/ui/Icon";

/* ═══════════════════════════════════════════════════════════════
   HERO 3D PREVIEW (procedural, no model required)
   ═══════════════════════════════════════════════════════════════ */

function HeroModel() {
  const group = useRef<Group>(null);
  const ringA = useRef<Mesh>(null);
  const ringB = useRef<Mesh>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (group.current) {
      group.current.rotation.y = t * 0.25;
    }
    if (ringA.current) {
      ringA.current.rotation.z = t * 0.4;
      ringA.current.rotation.x = Math.sin(t * 0.5) * 0.4 + 0.6;
    }
    if (ringB.current) {
      ringB.current.rotation.z = -t * 0.3;
      ringB.current.rotation.y = Math.cos(t * 0.4) * 0.5;
    }
  });

  return (
    <Float speed={1.6} rotationIntensity={0.35} floatIntensity={1.1}>
      <group ref={group}>
        {/* Core geometry */}
        <mesh castShadow receiveShadow>
          <icosahedronGeometry args={[1, 1]} />
          <meshStandardMaterial
            color="#7c3aed"
            metalness={0.65}
            roughness={0.22}
            flatShading
          />
        </mesh>
        {/* Wireframe shell */}
        <mesh scale={1.28}>
          <icosahedronGeometry args={[1, 1]} />
          <meshBasicMaterial color="#22d3ee" wireframe transparent opacity={0.5} />
        </mesh>
        {/* Orbiting rings */}
        <mesh ref={ringA} rotation={[0.6, 0, 0]}>
          <torusGeometry args={[1.7, 0.015, 16, 100]} />
          <meshBasicMaterial color="#a78bfa" transparent opacity={0.85} />
        </mesh>
        <mesh ref={ringB} rotation={[-0.4, 0.4, 0]}>
          <torusGeometry args={[2.05, 0.01, 16, 100]} />
          <meshBasicMaterial color="#22d3ee" transparent opacity={0.55} />
        </mesh>
        <pointLight position={[4, 4, 4]} intensity={8} color="#a855f7" />
        <pointLight position={[-4, -3, 3]} intensity={5} color="#22d3ee" />
      </group>
    </Float>
  );
}

function HeroPreview() {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-ink-900/60 shadow-card backdrop-blur-xl">
      {/* Header bar */}
      <div className="flex items-center gap-2 border-b border-white/8 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
        <span className="ml-3 hidden rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400 sm:block">
          model.gltf — {`<mesh>`} generation preview
        </span>
        <span className="ml-auto flex items-center gap-1.5 rounded-md bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
          <span className="glow-dot h-1.5 w-1.5 bg-emerald-400" /> Render ready
        </span>
      </div>

      {/* Canvas */}
      <div className="relative h-80 sm:h-96 lg:h-[420px]">
        <div className="absolute inset-0 bg-aurora" aria-hidden />
        <Canvas camera={{ position: [4.2, 2.4, 4.4], fov: 42 }} dpr={[1, 2]}>
          <ambientLight intensity={0.35} />
          <directionalLight position={[6, 8, 5]} intensity={1.6} />
          <HeroModel />
          <Sparkles count={90} scale={6} size={2.2} speed={0.45} color="#a78bfa" opacity={0.65} />
          <Grid
            position={[0, -1.9, 0]}
            cellSize={0.5}
            cellThickness={0.5}
            cellColor="#3f3f4f"
            sectionSize={2}
            sectionThickness={1}
            sectionColor="#6d28d9"
            fadeDistance={18}
            fadeStrength={2}
            infiniteGrid
          />
          <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.9} />
        </Canvas>

        {/* Live overlay chips */}
        <div className="pointer-events-none absolute left-4 top-4 space-y-2">
          <PreviewChip>
            <Icon name="cpu" className="h-3.5 w-3.5" /> Stable Fast 3D · 1024
          </PreviewChip>
          <PreviewChip>
            <Icon name="layers" className="h-3.5 w-3.5" /> 84K tris · PBR texture
          </PreviewChip>
        </div>

        {/* Rotating hint */}
        <div className="pointer-events-none absolute bottom-4 right-4 flex items-center gap-2 rounded-lg border border-white/10 bg-ink-950/60 px-3 py-1.5 text-[11px] text-slate-400 backdrop-blur">
          <Icon name="rotate" className="h-3.5 w-3.5 text-brand-300" /> Drag to inspect
        </div>
      </div>
    </div>
  );
}

function PreviewChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-ink-950/70 px-2.5 py-1 font-mono text-[10px] text-slate-300 backdrop-blur">
      {children}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════════
   LANDING PAGE
   ═══════════════════════════════════════════════════════════════ */

const features = [
  {
    icon: "cpu" as const,
    title: "Diffusion-grade reconstruction",
    description:
      "Neural geometry, material and texture synthesis trained on millions of objects — a single photo becomes a production mesh in minutes.",
  },
  {
    icon: "layers" as const,
    title: "Clean, game-ready topology",
    description:
      "Watertight, remeshed and simplified models with proper UVs — drop them straight into Unity, Unreal, Blender or web viewers.",
  },
  {
    icon: "verify" as const,
    title: "PBR materials & textures",
    description:
      "Albedo, normals and roughness baked from your source image with optional upscaling up to 2048px.",
  },
  {
    icon: "zap" as const,
    title: "Optimized for the web",
    description:
      "Lossless GLB export with Draco compression. Your models stay fast to load, from sketchfab-style embeds to AR scenes.",
  },
];

const steps = [
  { step: "01", title: "Upload an image", text: "Drag in a JPG, PNG or WEBP of any object, product, character or building." },
  { step: "02", title: "Configure your build", text: "Pick resolution, texture quality and remeshing level. Auto presets do the rest." },
  { step: "03", title: "AI reconstructs geometry", text: "The pipeline infers depth, shape and materials through multiple neural stages." },
  { step: "04", title: "Download & use anywhere", text: "Export GLB or GLTF and integrate into any 3D, game or AR engine in seconds." },
];

const supportedFormats = [
  { ext: "JPG", full: "Joint Photographic Experts Group", icon: "image" as const },
  { ext: "PNG", full: "Portable Network Graphics", icon: "image" as const },
  { ext: "WEBP", full: "Web Picture format", icon: "image" as const },
  { ext: "GLB", full: "Binary glTF · primary export", icon: "cube" as const },
  { ext: "GLTF", full: "glTF 2.0 · JSON + resources", icon: "cube" as const },
  { ext: "INTERNAL", full: "OpenUSD / OBJ on request", icon: "layers" as const },
];

const examples = [
  { key: "product", label: "Product & Industrial", emoji: "🛋️" },
  { key: "character", label: "Characters & Creatures", emoji: "🧸" },
  { key: "arch", label: "Architectural & Landscape", emoji: "🏔️" },
];

const plans = [
  {
    name: "Starter",
    monthly: 0,
    yearly: 0,
    description: "For trying the pipeline and casual projects.",
    features: ["10 generations / month", "512px texture output", "GLB + GLTF download", "Community support"],
    cta: "Start free",
    highlight: false,
  },
  {
    name: "Pro",
    monthly: 24,
    yearly: 19,
    description: "For creators shipping real 3D content.",
    features: [
      "Unlimited generations",
      "2048px PBR textures",
      "Remesh & simplify tools",
      "Batch & queue processing",
      "Priority GPU queue",
      "Discord support",
    ],
    cta: "Start Pro trial",
    highlight: true,
  },
  {
    name: "Studio",
    monthly: 79,
    yearly: 64,
    description: "For teams and studios at scale.",
    features: [
      "Everything in Pro",
      "5 seats included",
      "Custom AI models",
      "API & webhooks",
      "SLA + dedicated support",
    ],
    cta: "Contact sales",
    highlight: false,
  },
];

const faqs = [
  {
    q: "What image types can I convert?",
    a: "You can upload JPG, PNG and WEBP files up to 10 MB. The best results come from well-lit photos of a single object against a clean background, captured from a clear angle.",
  },
  {
    q: "How long does generation take?",
    a: "Most models finish in 45–90 seconds on the standard GPU queue. Resolution, texture quality and remeshing settings affect the total time — you can track every stage in real time.",
  },
  {
    q: "What output formats do I get?",
    a: "Every generation is exported as open-standard GLB and GLTF with embedded PBR textures, ready for Unity, Unreal, Blender, web viewers and AR frameworks. Additional formats like OBJ or USDZ are available on Studio plans.",
  },
  {
    q: "Is my source image used to train AI models?",
    a: "No. Your uploads are processed privately to generate your model and are never used to train or fine-tune the reconstruction models. You can delete the source image at any time.",
  },
  {
    q: "Can I use the generated models commercially?",
    a: "Yes. You keep full commercial rights to every model you generate, on all paid plans.",
  },
  {
    q: "Do I need a GPU or special software?",
    a: "No. Everything runs in the browser and on our GPU cluster. The 3D viewer works in any modern browser—desktop or mobile—with touch controls built in.",
  },
];

const testimonials = [
  {
    quote:
      "I went from a product photo to a rig-ready GLB in under two minutes. The mesh cleanup is legitimately impressive.",
    name: "Maya Chen",
    role: "Product Designer",
  },
  {
    quote:
      "Easily the best image-to-3D experience we've evaluated. The viewer alone is worth it for internal review rounds.",
    name: "Jon Bell",
    role: "Indie Game Developer",
  },
  {
    quote:
      "Our team ships AR variants of every SKU now. Vision3D cut the whole pipeline down to an upload.",
    name: "Priya Nair",
    role: "E-commerce Lead",
  },
];

/* ─── Landing header (navigation) ─── */

function LandingHeader({ onCtaClick }: { onCtaClick: () => void }) {
  const { resolvedTheme, toggleTheme } = useTheme();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-ink-950/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Logo />

        <nav className="hidden items-center gap-6 md:flex" aria-label="Sections">
          {[
            ["#how", "How it works"],
            ["#technology", "Technology"],
            ["#features", "Features"],
            ["#formats", "Formats"],
            ["#pricing", "Pricing"],
            ["#faq", "FAQ"],
          ].map(([href, label]) => (
            <a key={href} href={href} className="text-sm font-medium text-slate-400 transition-colors hover:text-white">
              {label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Toggle theme"
            onClick={toggleTheme}
            className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
          >
            <Icon name={resolvedTheme === "dark" ? "sun" : "moon"} className="h-5 w-5" />
          </button>
          <Link
            to="/login"
            className="hidden rounded-xl border border-white/12 px-4 py-2 text-sm font-medium text-slate-200 transition-colors hover:bg-white/5 hover:text-white sm:block"
          >
            Sign in
          </Link>
          <Link
            to="/register"
            className="rounded-xl bg-brand-gradient px-4 py-2 text-sm font-semibold text-white shadow-glow transition-all hover:brightness-110"
            onClick={onCtaClick}
          >
            Get started
          </Link>
          <button
            type="button"
            aria-label="Open menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 hover:bg-white/5 md:hidden"
          >
            <Icon name={open ? "close" : "menu"} />
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-white/5 px-4 py-3 md:hidden" aria-label="Mobile sections">
          {[
            ["#how", "How it works"],
            ["#technology", "Technology"],
            ["#features", "Features"],
            ["#pricing", "Pricing"],
            ["#faq", "FAQ"],
          ].map(([href, label]) => (
            <a key={href} href={href} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2 text-sm font-medium text-slate-300 hover:bg-white/5">
              {label}
            </a>
          ))}
        </nav>
      )}
    </header>
  );
}

/* ─── Sections ─── */

function SectionHeading({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-300">
        <span className="mr-1.5 inline-block h-1 w-4 rounded-full bg-brand-500 align-middle" />
        {eyebrow}
      </p>
      <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h2>
      {subtitle && <p className="mt-4 text-slate-400">{subtitle}</p>}
    </div>
  );
}

function BeforeAfter() {
  return (
    <section id="how" className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
      <SectionHeading
        eyebrow="Before → After"
        title="One photo in. A full 3D model out."
        subtitle="The AI reconstructs depth, volume and material from a single 2D image — no multi-angle capture needed."
      />

      <div className="mt-12 grid items-stretch gap-6 lg:grid-cols-2">
        {/* Before */}
        <div className="panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
            <span className="flex items-center gap-2 text-sm font-medium text-slate-300">
              <Icon name="image" className="h-4 w-4 text-slate-400" /> Source image
            </span>
            <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400">2D</span>
          </div>
          <div className="relative flex h-64 items-center justify-center overflow-hidden bg-ink-800/60 sm:h-80">
            <div className="absolute inset-6 rounded-2xl bg-brand-gradient-soft blur-2xl" aria-hidden />
            <div className="relative w-40 h-52 sm:w-48 sm:h-60 rounded-2xl border border-white/10 bg-gradient-to-b from-white/20 to-white/5 shadow-2xl flex items-center justify-center">
              <Icon name="image" className="h-14 w-14 text-white/40" strokeWidth={1.2} />
            </div>
            <div className="absolute bottom-4 left-4 flex items-center gap-1.5 rounded-lg bg-ink-950/70 px-2.5 py-1 text-[11px] text-slate-400 backdrop-blur">
              <span className="glow-dot h-1.5 w-1.5 bg-slate-400" /> Flat · no depth
            </div>
          </div>
        </div>

        {/* After */}
        <div className="panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
            <span className="flex items-center gap-2 text-sm font-medium text-slate-300">
              <Icon name="cube" className="h-4 w-4 text-brand-300" /> Generated model
            </span>
            <span className="rounded-md bg-brand-500/10 px-2 py-0.5 font-mono text-[10px] text-brand-300">3D · GLB</span>
          </div>
          <div className="relative flex h-64 items-center justify-center overflow-hidden bg-ink-800/60 sm:h-80">
            <div className="absolute inset-0 bg-aurora" aria-hidden />
            <Canvas camera={{ position: [3.4, 1.8, 3.4], fov: 40 }} dpr={[1, 2]}>
              <ambientLight intensity={0.4} />
              <directionalLight position={[4, 6, 4]} intensity={1.4} />
              <Float speed={1.2} rotationIntensity={0.3} floatIntensity={0.8}>
                <mesh>
                  <boxGeometry args={[1, 1.3, 1]} />
                  <meshStandardMaterial color="#7c3aed" metalness={0.5} roughness={0.25} />
                </mesh>
              </Float>
              <Sparkles count={40} scale={4} size={2} speed={0.4} color="#22d3ee" opacity={0.6} />
              <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={1.4} />
            </Canvas>
            <div className="absolute bottom-4 left-4 flex items-center gap-1.5 rounded-lg bg-ink-950/70 px-2.5 py-1 text-[11px] text-slate-300 backdrop-blur">
              <span className="glow-dot h-1.5 w-1.5 bg-emerald-400" /> Volumetric · textured
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="relative border-y border-white/5 bg-ink-900/40">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <SectionHeading
          eyebrow="Workflow"
          title="How it works"
          subtitle="Four steps between a photo and a production-ready model."
        />
        <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((item, i) => (
            <li key={item.step} className="group relative">
              <div className="panel panel-hover h-full p-6">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-brand-300">{item.step}</span>
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-sm font-semibold text-slate-300 group-hover:border-brand-400/40 group-hover:text-white">
                    {i + 1}
                  </span>
                </div>
                <h3 className="mt-4 font-display text-lg font-semibold text-white">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{item.text}</p>
              </div>
              {i < steps.length - 1 && (
                <Icon
                  name="arrowRight"
                  className="absolute -right-4 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 text-slate-600 lg:block"
                />
              )}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Technology() {
  const pipeline = [
    { label: "Image understanding", detail: "feature extraction · CLIP embeddings", tone: "from-accent-500/80 to-brand-600/80" },
    { label: "Depth & normal estimation", detail: "predicted view-space geometry", tone: "from-brand-600/80 to-brand-500/80" },
    { label: "Shape reconstruction", detail: "SDF / TriangleMesh regression", tone: "from-brand-500/80 to-accent-400/80" },
    { label: "UV unwrap & texturing", detail: "seamless PBR atlas baking", tone: "from-accent-400/80 to-brand-400/80" },
  ];

  return (
    <section id="technology" className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
      <div className="grid items-center gap-12 lg:grid-cols-2">
        <div>
          <SectionHeading
            eyebrow="AI Pipeline"
            title="Built on state-of-the-art reconstruction models"
            subtitle="Vision3D pipelines Stable Fast 3D and Hunyuan3D-2 adapters behind one simple upload, orchestrating deterministic results and streaming progress at every stage."
          />
          <div className="mt-10 space-y-0">
            {pipeline.map((stage, i) => (
              <div key={stage.label} className="relative pl-5">
                {i < pipeline.length - 1 && (
                  <span className="absolute left-[5px] top-6 h-full w-px bg-gradient-to-b from-brand-500/50 to-transparent" aria-hidden />
                )}
                <span className={`absolute left-0 top-1.5 flex h-[11px] w-[11px] rounded-full bg-gradient-to-br ${stage.tone} shadow-glow`} aria-hidden />
                <div className="flex items-center justify-between gap-4 py-2">
                  <div>
                    <p className="text-sm font-semibold text-white">{stage.label}</p>
                    <p className="font-mono text-[11px] text-slate-500">{stage.detail}</p>
                  </div>
                  <span className="font-mono text-xs text-slate-600">{`stage ${i + 1} / 4`}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Code panel */}
        <div className="panel overflow-hidden">
          <div className="flex items-center gap-2 border-b border-white/8 px-4 py-3">
            <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
            <span className="ml-2 font-mono text-[11px] text-slate-500">adapter_factory.ts</span>
          </div>
          <pre className="overflow-x-auto p-5 font-mono text-[12px] leading-relaxed">
            <code>
              <span className="text-slate-500">{"// pluggable adapter pattern"}</span>
              {"\n"}
              <span className="text-brand-300">const</span> <span className="text-accent-300">model</span>{" "}
              <span className="text-slate-400">=</span> <span className="text-brand-300">await</span> <span className="text-slate-200">getModel</span>
              <span className="text-slate-400">({ `{` }</span>
              {"\n"}
              {"  "}device: <span className="text-accent-300">"cuda"</span>,
              {"\n"}
              {"  "}resolution: <span className="text-emerald-300">2048</span>,
              {"\n"}
              {"  "}texture: <span className="text-accent-300">"pbr"</span>,
              {"\n"}
              <span className="text-slate-400">{`}`});</span>
              {"\n\n"}
              <span className="text-slate-200">await</span> <span className="text-slate-200">model</span>.
              <span className="text-brand-300">generate</span>
              <span className="text-slate-400">(</span>
              <span className="text-slate-200">image</span>, <span className="text-slate-400">{`{ onProgress }`}</span>
              <span className="text-slate-400">);</span>
              {"\n"}
              <span className="text-slate-500">// ✔ returns GLB + stats</span>
            </code>
          </pre>
        </div>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="border-t border-white/5 bg-ink-900/40">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <SectionHeading eyebrow="Capabilities" title="The full 3D workspace, in your browser" />
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <div key={feature.title} className="panel panel-hover group p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3">
                <Icon name={feature.icon} className="h-6 w-6" strokeWidth={1.7} />
              </div>
              <h3 className="mt-4 font-display text-base font-semibold text-white">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Formats() {
  return (
    <section id="formats" className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
      <div className="grid items-center gap-12 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <SectionHeading
            eyebrow="Compatibility"
            title="Supported formats"
            subtitle="Bring us your image in any standard raster format. We hand back open, engine-ready 3D files."
          />
          <div className="mt-8 space-y-4 text-sm text-slate-400">
            <p className="flex items-start gap-3">
              <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" strokeWidth={2.4} />
              Textures are embedded and compressed — no dangling files.
            </p>
            <p className="flex items-start gap-3">
              <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" strokeWidth={2.4} />
              Waterfall exports preserve quads, normals and UV seams.
            </p>
            <p className="flex items-start gap-3">
              <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" strokeWidth={2.4} />
              Drag-and-drop the result into Unity, Unreal, Blender or any glTF viewer.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {supportedFormats.map((f) => (
            <div key={f.ext} className="panel panel-hover flex flex-col items-center gap-2 p-5 text-center">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04]">
                <Icon name={f.icon} className="h-5 w-5 text-brand-300" />
              </span>
              <span className="font-mono text-sm font-semibold text-white">{f.ext}</span>
              <span className="text-[11px] leading-snug text-slate-500">{f.full}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Examples() {
  return (
    <section className="border-t border-white/5 bg-ink-900/40">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <SectionHeading eyebrow="Inspiration" title="Example generated models" subtitle="A look at what creators ship with Vision3D AI." />
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {examples.map((ex) => (
            <div key={ex.key} className="panel panel-hover group overflow-hidden">
              <div className="relative flex h-52 items-center justify-center overflow-hidden bg-ink-800/50">
                <div className="absolute inset-0 bg-brand-gradient-soft opacity-60 blur-2xl transition-opacity group-hover:opacity-100" aria-hidden />
                <span className="relative text-6xl drop-shadow-[0_8px_24px_rgba(124,58,237,0.35)] transition-transform duration-300 group-hover:scale-110">
                  {ex.emoji}
                </span>
                <div className="pointer-events-none absolute bottom-3 right-3 rounded-md bg-ink-950/70 px-2 py-0.5 font-mono text-[10px] text-slate-400 backdrop-blur">
                  {'→'} GLB · 45s
                </div>
              </div>
              <div className="p-5">
                <h3 className="font-display text-base font-semibold text-white">{ex.label}</h3>
                <p className="mt-1 text-sm text-slate-500">
                  {ex.key === "product" && "Furniture, gadgets, footwear and packaging from product photos."}
                  {ex.key === "character" && "Soft toys, figurines and creatures reconstructed from a single frame."}
                  {ex.key === "arch" && "Terrain, buildings and props captured as clean low-poly geometry."}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {testimonials.map((t) => (
            <figure key={t.name} className="panel p-6">
              <Icon name="star" className="h-4 w-4 text-amber-400" />
              <blockquote className="mt-3 text-sm leading-relaxed text-slate-300">“{t.quote}”</blockquote>
              <figcaption className="mt-4 flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-gradient text-xs font-bold text-white">
                  {t.name.split(" ").map((n) => n[0]).join("")}
                </span>
                <div>
                  <p className="text-sm font-semibold text-white">{t.name}</p>
                  <p className="text-xs text-slate-500">{t.role}</p>
                </div>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  const [yearly, setYearly] = useState(true);
  return (
    <section id="pricing" className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
      <SectionHeading eyebrow="Pricing" title="Simple plans, serious output" subtitle="Start free, scale when your pipeline takes off." />

      {/* Billing toggle */}
      <div className="mt-10 flex items-center justify-center gap-4">
        <span className={!yearly ? "text-white" : "text-slate-500"}>Monthly</span>
        <button
          type="button"
          role="switch"
          aria-checked={yearly}
          onClick={() => setYearly((v) => !v)}
          className="relative h-7 w-14 rounded-full border border-white/10 bg-ink-700 transition-colors"
        >
          <span
            className={`absolute top-1 h-5 w-5 rounded-full bg-brand-gradient shadow-glow transition-transform ${yearly ? "translate-x-[2rem]" : "translate-x-1"}`}
          />
        </button>
        <span className={yearly ? "text-white" : "text-slate-500"}>
          Yearly <span className="ml-1 rounded-md bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">save 20%</span>
        </span>
      </div>

      <div className="mt-10 grid gap-6 lg:grid-cols-3">
        {plans.map((plan) => {
          const price = yearly ? plan.yearly : plan.monthly;
          return (
            <div
              key={plan.name}
              className={
                plan.highlight
                  ? "relative rounded-2xl border border-brand-500/40 bg-gradient-to-b from-brand-500/10 to-transparent p-6 shadow-glow backdrop-blur-xl"
                  : "panel panel-hover flex flex-col p-6"
              }
            >
              {plan.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-gradient px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-white shadow-glow">
                  Most popular
                </span>
              )}
              <h3 className="font-display text-lg font-semibold text-white">{plan.name}</h3>
              <p className="mt-1 text-sm text-slate-400">{plan.description}</p>
              <div className="mt-6 flex items-end gap-1">
                <span className="font-display text-4xl font-bold text-white">${price}</span>
                <span className="pb-1 text-sm text-slate-500">/ month</span>
              </div>
              <ul className="mt-6 flex-1 space-y-3">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-slate-300">
                    <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" strokeWidth={2.4} />
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                to="/register"
                className={
                  plan.highlight
                    ? "mt-8 flex items-center justify-center gap-2 rounded-xl bg-brand-gradient py-2.5 text-sm font-semibold text-white shadow-glow transition-all hover:brightness-110"
                    : "mt-8 flex items-center justify-center gap-2 rounded-xl border border-white/12 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:bg-white/5 hover:text-white"
                }
              >
                {plan.cta}
              </Link>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Faq() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  return (
    <section id="faq" className="border-t border-white/5 bg-ink-900/40">
      <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
        <SectionHeading eyebrow="FAQ" title="Frequently asked questions" />
        <div className="mt-10 space-y-3">
          {faqs.map((faq, i) => {
            const open = openIndex === i;
            return (
              <div key={faq.q} className="panel overflow-hidden">
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => setOpenIndex(open ? null : i)}
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                >
                  <span className="font-medium text-white">{faq.q}</span>
                  <span
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/10 text-slate-400 transition-transform ${open ? "rotate-45" : ""}`}
                    aria-hidden
                  >
                    <Icon name="plus" className="h-4 w-4" />
                  </span>
                </button>
                {open && (
                  <div className="animate-slide-up px-5 pb-5">
                    <p className="text-sm leading-relaxed text-slate-400">{faq.a}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ─── Footer ─── */

function SiteFooter() {
  const cols: { title: string; links: string[] }[] = [
    { title: "Product", links: ["Generate", "Projects", "Viewer", "Pricing"] },
    { title: "Resources", links: ["Documentation", "API reference", "Tutorials", "Changelog"] },
    { title: "Company", links: ["About", "Blog", "Careers", "Contact"] },
  ];

  return (
    <footer className="border-t border-white/5 bg-ink-950">
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-4 text-sm leading-relaxed text-slate-500">
              Turn any 2D image into a downloadable 3D model with state-of-the-art AI reconstruction.
            </p>
            <div className="mt-6 flex gap-3">
              {(["twitter", "github", "youtube"] as const).map((s) => (
                <a
                  key={s}
                  href="#"
                  aria-label={`Vision3D on ${s}`}
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 text-slate-400 transition-colors hover:border-brand-400/40 hover:text-white"
                >
                  <Icon name={s} className="h-5 w-5" />
                </a>
              ))}
            </div>
          </div>
          {cols.map((col) => (
            <div key={col.title}>
              <h4 className="text-sm font-semibold text-white">{col.title}</h4>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l}>
                    <a href="#" className="text-sm text-slate-500 transition-colors hover:text-white">
                      {l}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-col items-center justify-between gap-3 border-t border-white/8 pt-8 text-sm text-slate-600 sm:flex-row">
          <p>© {new Date().getFullYear()} Vision3D AI. All rights reserved.</p>
          <div className="flex gap-6">
            <a href="#" className="hover:text-slate-400">Privacy</a>
            <a href="#" className="hover:text-slate-400">Terms</a>
            <a href="#" className="hover:text-slate-400">Security</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ─── Page ─── */

export function LandingPage() {
  return (
    <div className="min-h-screen bg-ink-950 text-slate-200">
      <div className="pointer-events-none fixed inset-0 z-0 bg-aurora" aria-hidden />
      <LandingHeader onCtaClick={() => {}} />

      {/* HERO */}
      <section className="relative z-10 mx-auto max-w-7xl px-4 pb-16 pt-16 sm:px-6 sm:pt-24">
        <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_1fr]">
          <div className="text-center lg:text-left">
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-200 backdrop-blur">
              <Icon name="sparkles" className="h-3.5 w-3.5" />
              Neural image-to-3D reconstruction
            </span>
            <h1 className="mt-6 font-display text-4xl font-bold leading-[1.05] tracking-tight text-white sm:text-6xl">
              Turn Images
              <br />
              Into <span className="text-gradient">3D</span>
            </h1>
            <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-slate-400 lg:mx-0">
              Upload a single photo and Vision3D AI reconstructs a clean, textured, game-ready 3D
              model — right in your browser. Export GLB or GLTF, integrate anywhere.
            </p>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start">
              <Link
                to="/register"
                className="group flex w-full items-center justify-center gap-2 rounded-xl bg-brand-gradient px-6 py-3 text-base font-semibold text-white shadow-glow-lg transition-all hover:brightness-110 sm:w-auto"
              >
                <Icon name="upload" className="h-5 w-5 transition-transform group-hover:-translate-y-0.5" />
                Upload Image
              </Link>
              <Link
                to="/login"
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-6 py-3 text-base font-medium text-slate-200 backdrop-blur transition-all hover:border-brand-400/40 hover:bg-white/[0.07] hover:text-white sm:w-auto"
              >
                <Icon name="play" className="h-5 w-5 text-brand-300" />
                Try Demo
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-slate-500 lg:justify-start">
              <span className="flex items-center gap-1.5">
                <Icon name="check" className="h-3.5 w-3.5 text-emerald-400" strokeWidth={2.4} /> No GPU required
              </span>
              <span className="flex items-center gap-1.5">
                <Icon name="check" className="h-3.5 w-3.5 text-emerald-400" strokeWidth={2.4} /> Free to start
              </span>
              <span className="flex items-center gap-1.5">
                <Icon name="check" className="h-3.5 w-3.5 text-emerald-400" strokeWidth={2.4} /> Commercial rights
              </span>
            </div>
          </div>

          <HeroPreview />
        </div>
      </section>

      <BeforeAfter />
      <HowItWorks />
      <Technology />
      <Features />
      <Formats />
      <Examples />
      <Pricing />
      <Faq />

      {/* Final CTA */}
      <section className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <div className="relative overflow-hidden rounded-3xl border border-brand-500/30 bg-gradient-to-b from-brand-500/15 to-transparent p-10 text-center sm:p-16">
          <div className="absolute inset-0 bg-aurora" aria-hidden />
          <div className="relative">
            <h2 className="font-display text-3xl font-bold text-white sm:text-4xl">
              Bring your images to life in 3D
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-slate-400">
              No GPU, no technical setup. Just upload, watch the AI reconstruct, and download a
              production-ready model.
            </p>
            <Link
              to="/register"
              className="mt-8 inline-flex items-center gap-2 rounded-xl bg-brand-gradient px-7 py-3.5 text-base font-semibold text-white shadow-glow-lg transition-all hover:brightness-110"
            >
              <Icon name="sparkles" className="h-5 w-5" />
              Start generating free
            </Link>
          </div>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}