# DevRescue AI — Autonomous Bug Investigation & Repair Console

> **"Broken code, rescued in seconds."**  
> An autonomous cyber console & terminal for continuous software reliability.

DevRescue AI is an autonomous engineering platform where a collective of five specialized AI agents investigates GitHub bugs, synthesizes surgically minimal patches, executes adversarial regression tests, and opens verified pull requests for human review.

---

## ⚡ UI/UX Design Direction: "Hacker / Terminal Cyber-Console"

The interface has been completely transformed into a sleek, high-density **developer console and cyber-terminal**:

- **Color Scheme**: Deep dark `#090A0F` canvas, `#11141D` surface cards, `#171B26` elevated panels, and glowing cyber accents:
  - **Electric Emerald** (`#10B981`): Active states, healthy repos, passed tests, and primary buttons.
  - **Neon Cyan** (`#06B6D4`): Pull requests, AST analysis, and deployment monitors.
  - **Telemetry Amber** (`#F59E0B`): Running investigations and warnings.
  - **Neon Crimson/Rose** (`#F43F5E`): Bug loci, deletions, and critical alerts.
- **Typography**:
  - Primary UI & Headlines: **Inter** with clean tracking and bold weights.
  - Telemetry & Code: **JetBrains Mono** & **IBM Plex Mono** for terminal logs, diff line numbers, metrics, and commands.
- **Theming & Color Modes**:
  - One-click **Light Mode / Dark Mode** toggle available across top navigation, console topbars, and Settings.
  - Light mode provides a clean, high-contrast developer palette with crisp white surfaces, slate typography, and emerald accents.
  - Dark mode provides the deep cyber console with `#090A0F` canvas, CRT scanline effects, and neon glowing telemetry.
- **Components**:
  - Modern cards with depth, subtle borders, `rounded-xl`, and glowing hover states.
  - Dark command inputs with glowing emerald focus rings.
  - High-density telemetry HUD metric cards with digital readouts.
  - Real-time terminal with CRT scanlines toggle, window controls, and colored agent log levels.
  - Monaco/VS Code-style dark diff viewer with side-by-side / unified toggles and git delta pills.
  - Futuristic 5-agent pipeline timeline with glowing progress tracks and status nodes.

---

## 🚀 The 5 Specialized AI Agents

1. **The Detective** (`01`): Telemetry & Stacktrace Triaging. Ingests crash dumps and reproduces bugs in ephemeral microVMs.
2. **The Analyst** (`02`): Root Cause & Invariant Proving. Evaluates control flow graphs, AST invariants, and race conditions.
3. **The Coder** (`03`): Patch Synthesis & Minimal Diffs. Writes minimal, idiomatic patches conforming to repository formatting.
4. **The Tester** (`04`): Stress Emulation & CI Verification. Runs 100+ concurrent stress workers to certify 100% green tests.
5. **The Reporter** (`05`): PR Explanation & Changelog Drafting. Deploys semantic GitHub pull requests with Conventional Commits.

---

## 🛠️ Getting Started

```bash
# 1. Install dependencies
npm install

# 2. Run the development server
npm run dev

# 3. Build for production
npm run build
```
