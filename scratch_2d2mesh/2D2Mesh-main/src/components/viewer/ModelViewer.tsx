import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useLoader } from "@react-three/fiber";
import { OrbitControls, Grid, ContactShadows } from "@react-three/drei";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";
import { cn, formatNumber } from "../../lib/format";
import { useAppStore } from "../../store/appStore";
import { Icon } from "../ui/Icon";
import type { ModelStats } from "../../types/project";

export type DetailedDiagnostics = {
  vertices: number;
  triangles: number;
  faces: number;
  meshes: number;
  materials: number;
  hasTexture: boolean;
  textureDimensions?: [number, number] | null;
  hasUVs: boolean;
  hasNormals: boolean;
  boundingBoxMin?: [number, number, number];
  boundingBoxMax?: [number, number, number];
  boundingSphereRadius?: number;
  invalidVertices: number;
  degenerateFaces: number;
};

function computeDetailedDiagnostics(scene: THREE.Object3D): DetailedDiagnostics {
  let vertices = 0;
  let triangles = 0;
  let meshes = 0;
  const materialSet = new Set<string>();
  let hasTexture = false;
  let hasUVs = false;
  let hasNormals = false;
  let textureDimensions: [number, number] | null = null;
  let invalidVertices = 0;

  scene.traverse((object) => {
    const mesh = object as THREE.Mesh;
    if (mesh.isMesh) {
      meshes += 1;
      const geometry = mesh.geometry as THREE.BufferGeometry;
      const position = geometry.getAttribute("position");
      const uv = geometry.getAttribute("uv");
      const normal = geometry.getAttribute("normal");

      if (position) {
        vertices += position.count;
        for (let i = 0; i < position.count; i++) {
          const x = position.getX(i);
          const y = position.getY(i);
          const z = position.getZ(i);
          if (isNaN(x) || isNaN(y) || isNaN(z) || !isFinite(x) || !isFinite(y) || !isFinite(z)) {
            invalidVertices += 1;
          }
        }
      }

      if (geometry.index) triangles += geometry.index.count / 3;
      else if (position) triangles += position.count / 3;

      if (uv && uv.count > 0) hasUVs = true;
      if (normal && normal.count > 0) hasNormals = true;

      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const material of materials) {
        materialSet.add(material.uuid);
        const anyMat = material as THREE.MeshStandardMaterial;
        if (anyMat.map) {
          hasTexture = true;
          if (anyMat.map.image && anyMat.map.image.width) {
            textureDimensions = [anyMat.map.image.width, anyMat.map.image.height];
          }
        }
      }
    }
  });

  const box = new THREE.Box3().setFromObject(scene);
  const min = box.min.toArray() as [number, number, number];
  const max = box.max.toArray() as [number, number, number];
  const sphere = box.getBoundingSphere(new THREE.Sphere());

  return {
    vertices,
    triangles,
    faces: triangles,
    meshes,
    materials: materialSet.size,
    hasTexture,
    textureDimensions,
    hasUVs,
    hasNormals,
    boundingBoxMin: min,
    boundingBoxMax: max,
    boundingSphereRadius: sphere.radius,
    invalidVertices,
    degenerateFaces: 0,
  };
}

function fitScene(scene: THREE.Object3D): { scale: number; center: THREE.Vector3 } {
  const box = new THREE.Box3().setFromObject(scene);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 1e-6);
  return { scale: 2.0 / maxDim, center };
}

type LoadedModelProps = {
  url: string;
  wireframe: boolean;
  solidPreview: boolean;
  showBBox: boolean;
  onStats: (stats: DetailedDiagnostics) => void;
};

function LoadedModel({ url, wireframe, solidPreview, showBBox, onStats }: LoadedModelProps) {
  const gltf = useLoader(GLTFLoader, url);
  const scene = useMemo(() => gltf.scene.clone(true), [gltf]);
  const { scale, center } = useMemo(() => fitScene(scene), [scene]);

  // Dispose cloned resources on unmount / URL change to avoid GPU memory leaks.
  useEffect(() => {
    return () => {
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        if (mesh.isMesh) {
          mesh.geometry?.dispose();
          const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          for (const material of materials) {
            const mat = material as THREE.Material;
            const record = mat as unknown as Record<string, unknown>;
            for (const key of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap", "emissiveMap", "alphaMap", "bumpMap", "specularMap"]) {
              const tex = record[key];
              if (tex && typeof (tex as THREE.Texture).dispose === "function") {
                (tex as THREE.Texture).dispose();
              }
            }
            mat.dispose();
          }
        }
      });
    };
  }, [scene]);

  useMemo(() => {
    scene.traverse((object) => {
      const mesh = object as THREE.Mesh;
      if (!mesh.isMesh) return;

      const geometry = mesh.geometry as THREE.BufferGeometry;

      if (!geometry.getAttribute("normal")) {
        geometry.computeVertexNormals();
      }

      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const material of materials) {
        const mat = material as THREE.MeshStandardMaterial;

        if (mat.map) {
          mat.map.colorSpace = THREE.SRGBColorSpace;
          mat.map.needsUpdate = true;
        }

        mat.side = THREE.FrontSide;
        mat.depthWrite = true;
        mat.transparent = false;
        mat.needsUpdate = true;
      }
    });

    onStats(computeDetailedDiagnostics(scene));
  }, [scene, onStats]);

  useMemo(() => {
    const fallbackMat = new THREE.MeshStandardMaterial({
      color: "#cbd5e1",
      roughness: 0.45,
      metalness: 0.1,
      wireframe,
    });

    scene.traverse((object) => {
      const mesh = object as THREE.Mesh;
      if (!mesh.isMesh) return;

      if (solidPreview) {
        mesh.material = fallbackMat;
      } else {
        const originalMats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const mat of originalMats) {
          if ("wireframe" in mat) (mat as THREE.MeshStandardMaterial).wireframe = wireframe;
        }
      }
    });
  }, [scene, wireframe, solidPreview]);

  return (
    <group position={[-center.x, -center.y, -center.z]} scale={scale}>
      <primitive object={scene} />
      {showBBox && <boxHelper args={[scene, "#38bdf8"]} />}
    </group>
  );
}

function SceneHelpers({ showGrid, showAxes, lighting }: { showGrid: boolean; showAxes: boolean; lighting: boolean }) {
  return (
    <>
      {showGrid && (
        <Grid
          position={[0, -1.05, 0]}
          cellSize={0.5}
          cellThickness={0.6}
          cellColor="#3f3f4f"
          sectionSize={2.5}
          sectionThickness={1.2}
          sectionColor="#6d28d9"
          fadeDistance={30}
          fadeStrength={1.5}
          infiniteGrid
        />
      )}
      {showAxes && <axesHelper args={[1.6]} />}
      {lighting && <ContactShadows position={[0, -1.03, 0]} opacity={0.5} scale={8} blur={2.6} far={3} />}
    </>
  );
}

export function ModelViewer({
  modelUrl,
  fallbackStats,
  className,
  allowFullscreen = true,
}: {
  modelUrl: string;
  fallbackStats?: ModelStats | null;
  className?: string;
  allowFullscreen?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewer = useAppStore((state) => state.viewer);
  const setViewer = useAppStore((state) => state.setViewer);
  const [showInfo, setShowInfo] = useState(false);
  const [resetSignal, setResetSignal] = useState(0);
  const [stats, setStats] = useState<DetailedDiagnostics | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleViewer = (key: keyof typeof viewer) => () => setViewer({ [key]: !viewer[key] });

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      void containerRef.current.requestFullscreen();
    } else {
      void document.exitFullscreen();
    }
  };

  useMemo(() => {
    const onChange = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative h-[540px] overflow-hidden rounded-2xl border border-white/10 bg-[radial-gradient(circle_at_50%_30%,#1a1a28,#07070c)] shadow-card",
        isFullscreen && "rounded-none border-0",
        className,
      )}
    >
      {/* Background layers */}
      <div className="absolute inset-0 bg-aurora opacity-70" aria-hidden />
      <div className="scanlines absolute inset-0" aria-hidden />

      <Canvas
        key={`viewer-${resetSignal}`}
        camera={{ position: [2.2, 1.6, 2.6], fov: 45 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={viewer.lighting ? 0.6 : 0.15} />
        <hemisphereLight intensity={viewer.lighting ? 0.4 : 0} color="#c7d2fe" groundColor="#334155" />
        <directionalLight position={[5, 8, 4]} intensity={viewer.lighting ? 1.5 : 0} castShadow />
        <directionalLight position={[-5, 3, -4]} intensity={viewer.lighting ? 0.5 : 0} color="#a5b4fc" />
        <SceneHelpers showGrid={viewer.showGrid} showAxes={viewer.showAxes} lighting={viewer.lighting} />
        <LoadedModel
          url={modelUrl}
          wireframe={viewer.wireframe}
          solidPreview={viewer.solidPreview}
          showBBox={viewer.showBBox}
          onStats={setStats}
        />
        <OrbitControls
          makeDefault
          enablePan
          enableZoom
          autoRotate={viewer.autoRotate}
          autoRotateSpeed={2.0}
          minDistance={1.0}
          maxDistance={14.0}
          target={[0, 0, 0]}
        />
      </Canvas>

      {/* Right toolbar */}
      <div className="absolute right-3 top-3 z-10 flex flex-col gap-2">
        <ToolbarButton active={viewer.autoRotate} onClick={toggleViewer("autoRotate")} title="Auto-rotate">
          <Icon name="rotate" />
        </ToolbarButton>
        <ToolbarButton active={viewer.wireframe} onClick={toggleViewer("wireframe")} title="Toggle wireframe">
          <Icon name="wireframe" />
        </ToolbarButton>
        <ToolbarButton active={viewer.solidPreview} onClick={toggleViewer("solidPreview")} title="Solid preview (neutral material)">
          <Icon name="cube" />
        </ToolbarButton>
        <ToolbarButton active={viewer.showGrid} onClick={toggleViewer("showGrid")} title="Toggle grid">
          <Icon name="grid" />
        </ToolbarButton>
        <ToolbarButton active={viewer.showBBox} onClick={toggleViewer("showBBox")} title="Toggle bounding box">
          <Icon name="layers" />
        </ToolbarButton>
        <ToolbarButton active={viewer.showAxes} onClick={toggleViewer("showAxes")} title="Show axes">
          <Icon name="move" />
        </ToolbarButton>
        <ToolbarButton active={viewer.lighting} onClick={toggleViewer("lighting")} title="Toggle lighting">
          <Icon name="light" />
        </ToolbarButton>
        <ToolbarButton active={showInfo} onClick={() => setShowInfo((v) => !v)} title="Model information">
          <Icon name="info" />
        </ToolbarButton>
        <ToolbarButton onClick={() => setResetSignal((v) => v + 1)} title="Reset camera">
          <Icon name="refresh" />
        </ToolbarButton>
        {allowFullscreen && (
          <ToolbarButton active={isFullscreen} onClick={toggleFullscreen} title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}>
            <Icon name={isFullscreen ? "fullscreenExit" : "fullscreen"} />
          </ToolbarButton>
        )}
      </div>

      {/* Stats summary */}
      <div className="absolute bottom-3 left-3 z-10 rounded-xl border border-white/10 bg-ink-950/70 p-3 text-xs text-slate-200 backdrop-blur-xl">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1">
          <Stat label="Vertices" value={formatNumber((stats ?? fallbackStats)?.vertices ?? 0)} />
          <Stat label="Triangles" value={formatNumber((stats ?? fallbackStats)?.triangles ?? 0)} />
          <Stat label="Faces" value={formatNumber((stats ?? fallbackStats)?.faces ?? 0)} />
          <Stat label="Texture" value={stats?.hasTexture || fallbackStats?.has_texture ? "Yes" : "No"} />
        </dl>
      </div>

      {/* Model information panel */}
      {showInfo && stats && (
        <div className="absolute left-3 top-3 z-20 w-72 rounded-2xl border border-white/12 bg-ink-950/85 p-4 text-xs text-slate-200 backdrop-blur-2xl shadow-card space-y-3 animate-scale-in">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h4 className="flex items-center gap-1.5 font-semibold text-white">
              <Icon name="cube" className="h-4 w-4 text-brand-300" /> Model information
            </h4>
            <button
              type="button"
              onClick={() => setShowInfo(false)}
              aria-label="Close model information"
              className="rounded-lg p-1 text-slate-400 transition-colors hover:text-white"
            >
              <Icon name="close" className="h-4 w-4" />
            </button>
          </div>
          <div className="space-y-1.5 font-mono text-[11px]">
            <DiagRow label="Vertices" value={formatNumber(stats.vertices)} />
            <DiagRow label="Triangles" value={formatNumber(stats.triangles)} />
            <DiagRow label="Meshes" value={String(stats.meshes)} />
            <DiagRow label="Materials" value={String(stats.materials)} />
            <DiagRow label="Normals" value={stats.hasNormals ? "Valid" : "Missing"} alert={!stats.hasNormals} />
            <DiagRow label="UV coordinates" value={stats.hasUVs ? "Valid" : "Missing"} alert={!stats.hasUVs} />
            <DiagRow
              label="Texture"
              value={stats.hasTexture ? `Yes ${stats.textureDimensions ? `(${stats.textureDimensions[0]}×${stats.textureDimensions[1]})` : ""}` : "No"}
            />
            <DiagRow label="Bounding radius" value={`${stats.boundingSphereRadius?.toFixed(3) ?? "—"}u`} />
          </div>
          <div className="grid grid-cols-2 gap-1.5 border-t border-white/10 pt-2.5 font-mono text-[10px] text-slate-500">
            <span>min ({stats.boundingBoxMin?.map((n) => n.toFixed(2)).join(", ") ?? "—"})</span>
            <span>max ({stats.boundingBoxMax?.map((n) => n.toFixed(2)).join(", ") ?? "—"})</span>
          </div>
        </div>
      )}

      <div className="pointer-events-none absolute bottom-3 right-3 z-10 text-[11px] text-slate-500">
        Left-drag rotate · Scroll zoom · Right-drag pan
      </div>
    </div>
  );
}

function ToolbarButton({
  children,
  onClick,
  title,
  active,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-pressed={active}
      aria-label={title}
      onClick={onClick}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-xl border backdrop-blur-xl transition-all active:scale-95",
        active
          ? "border-brand-400/60 bg-brand-500/80 text-white shadow-glow"
          : "border-white/10 bg-ink-950/70 text-slate-300 hover:bg-ink-800 hover:text-white",
      )}
    >
      {children}
    </button>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-semibold text-white">{value}</dd>
    </div>
  );
}

function DiagRow({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500">{label}:</span>
      <span className={cn("font-medium", alert ? "font-bold text-red-400" : "text-slate-200")}>{value}</span>
    </div>
  );
}