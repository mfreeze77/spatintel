"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  buildLayerRenderDirectives,
  layerDirective,
  type LayerState,
  type RenderLayerDirective
} from "../lib/spatial-runtime";
import type { LocalViewerBundle } from "../lib/local-scene-bundle";

type HybridCanvasProps = Readonly<{
  bundle: LocalViewerBundle | null;
  layers: readonly LayerState[];
  reducedMotion: boolean;
  highContrast: boolean;
  clippingEnabled: boolean;
  comparisonSplit: number;
  onSemanticPick: (stableEntityId: string) => void;
}>;

export function HybridCanvas({ bundle, layers, reducedMotion, highContrast, clippingEnabled, comparisonSplit, onSemanticPick }: HybridCanvasProps): React.ReactNode {
  const host = useRef<HTMLDivElement>(null);
  const [fallback, setFallback] = useState<string | null>(null);
  const directives = useMemo(() => buildLayerRenderDirectives(layers, comparisonSplit), [comparisonSplit, layers]);
  const visibleRoles = directives.filter((item) => item.visible).map((item) => item.role).join(",");

  useEffect(() => {
    const container = host.current;
    if (!container) return;

    let disposed = false;
    let animation = 0;
    let observer: ResizeObserver | null = null;
    let pointerTarget: HTMLCanvasElement | null = null;
    let pointerHandler: ((event: PointerEvent) => void) | null = null;
    const disposables: Array<{ dispose(): void }> = [];

    const applyDirective = (
      object: { visible: boolean; userData: Record<string, unknown>; material: unknown },
      directive: RenderLayerDirective
    ): void => {
      object.visible = directive.visible;
      object.userData.authorized = directive.visible;
      object.userData.pickable = directive.pickable;
      object.userData.authorityLabel = directive.authorityLabel;
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      for (const material of materials) {
        if (!material || typeof material !== "object") continue;
        const candidate = material as { opacity?: number; transparent?: boolean; needsUpdate?: boolean };
        candidate.opacity = directive.opacity;
        candidate.transparent = directive.opacity < 1;
        candidate.needsUpdate = true;
      }
    };

    void import("three").then((THREE) => {
      if (disposed) return;
      setFallback(null);
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(55, 1, 0.05, 100);
      camera.position.set(4.2, 3.1, 5.6);
      camera.lookAt(0, 1.2, 0);
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
      renderer.localClippingEnabled = true;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.setClearColor(highContrast ? 0x000000 : 0x101820, 1);
      renderer.domElement.setAttribute("aria-hidden", "true");
      renderer.domElement.dataset.renderer = "native-three-mesh-splat";
      container.replaceChildren(renderer.domElement);

      const metricGeometry = bundle ? new THREE.BufferGeometry() : new THREE.BoxGeometry(4, 2.8, 5);
      if (bundle) {
        metricGeometry.setAttribute("position", new THREE.Float32BufferAttribute(bundle.metric.vertices.flat(), 3));
        metricGeometry.setIndex(bundle.metric.faces.flat());
        if (bundle.metric.colors.length === bundle.metric.vertices.length) metricGeometry.setAttribute("color", new THREE.Float32BufferAttribute(bundle.metric.colors.flat(), 3));
        metricGeometry.computeVertexNormals();
      }
      const metric = new THREE.Mesh(
        metricGeometry,
        new THREE.MeshStandardMaterial({ color: 0x486581, vertexColors: Boolean(bundle?.metric.colors.length), transparent: true, side: THREE.DoubleSide })
      );
      metric.name = "metric:room-101";
      metric.userData = { role: "metric", stableEntityId: "room-101" };
      if (!bundle) metric.position.y = 1.4;
      applyDirective(metric, layerDirective(directives, "metric"));
      scene.add(metric);

      const splatCount = bundle?.visual.positions.length ?? 1500;
      const splatPositions = new Float32Array(splatCount * 3);
      const splatColors = new Float32Array(splatCount * 3);
      for (let i = 0; i < splatCount; i += 1) {
        if (bundle) {
          const position = bundle.visual.positions[i];
          if (!position) throw new Error("VIEWER_BUNDLE_SPLAT_POSITION_MISSING");
          splatPositions.set(position, i * 3);
          splatColors.set(bundle.visual.colors[i] ?? [0.55, 0.65, 0.75], i * 3);
          continue;
        }
        const seed = (i * 2654435761) >>> 0;
        splatPositions[i * 3] = ((seed & 1023) / 1023 - 0.5) * 4;
        splatPositions[i * 3 + 1] = (((seed >>> 10) & 1023) / 1023) * 2.8;
        splatPositions[i * 3 + 2] = (((seed >>> 20) & 1023) / 1023 - 0.5) * 5;
        splatColors[i * 3] = 0.3 + ((seed & 255) / 255) * 0.5;
        splatColors[i * 3 + 1] = 0.45 + (((seed >>> 8) & 255) / 255) * 0.4;
        splatColors[i * 3 + 2] = 0.6 + (((seed >>> 16) & 255) / 255) * 0.35;
      }
      const splatGeometry = new THREE.BufferGeometry();
      splatGeometry.setAttribute("position", new THREE.BufferAttribute(splatPositions, 3));
      splatGeometry.setAttribute("color", new THREE.BufferAttribute(splatColors, 3));
      const splats = new THREE.Points(
        splatGeometry,
        new THREE.PointsMaterial({ size: 0.035, vertexColors: true, transparent: true, depthWrite: false })
      );
      splats.name = "visual:gaussian-splat";
      splats.userData = { role: "visual", stableEntityId: null };
      applyDirective(splats, layerDirective(directives, "visual"));
      scene.add(splats);

      const design = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(4.15, 2.95, 5.15)),
        new THREE.LineBasicMaterial({ color: highContrast ? 0xffff00 : 0xffc857, transparent: true })
      );
      design.position.y = 1.475;
      design.name = "design:room-101";
      design.userData = { role: "design", stableEntityId: "room-101" };
      applyDirective(design, layerDirective(directives, "design"));
      scene.add(design);

      const interactionGeometry = bundle ? new THREE.BufferGeometry() : new THREE.BoxGeometry(4.05, 2.85, 5.05);
      if (bundle) {
        interactionGeometry.setAttribute("position", new THREE.Float32BufferAttribute(bundle.interaction.vertices.flat(), 3));
        interactionGeometry.setIndex(bundle.interaction.faces.flat());
        interactionGeometry.computeVertexNormals();
      }
      const interaction = new THREE.Mesh(
        interactionGeometry,
        new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false })
      );
      if (!bundle) interaction.position.y = 1.425;
      interaction.name = "interaction:room-101";
      interaction.userData = { role: "interaction", stableEntityId: "room-101" };
      const interactionDirective = layerDirective(directives, "interaction");
      applyDirective(interaction, interactionDirective);
      scene.add(interaction);

      const evidence = new THREE.Mesh(
        new THREE.SphereGeometry(0.11, 16, 12),
        new THREE.MeshStandardMaterial({ color: highContrast ? 0xffffff : 0x8de4ff, transparent: true, emissive: highContrast ? 0x555555 : 0x164e63 })
      );
      evidence.position.set(1.55, 1.35, -0.8);
      evidence.name = "evidence:asset-depth-001";
      evidence.userData = { role: "evidence", stableEntityId: "room-101", evidenceId: "asset-depth-001" };
      applyDirective(evidence, layerDirective(directives, "evidence"));
      scene.add(evidence);

      const clippingPlane = new THREE.Plane(new THREE.Vector3(1, 0, 0), 0);
      for (const object of [metric, splats, design, interaction, evidence]) {
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        for (const material of materials) material.clippingPlanes = clippingEnabled ? [clippingPlane] : [];
      }

      scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 2.2));
      const directional = new THREE.DirectionalLight(0xffffff, 2.0);
      directional.position.set(3, 6, 4);
      scene.add(directional);
      const grid = new THREE.GridHelper(12, 24, highContrast ? 0xffffff : 0x5c6770, 0x303a43);
      scene.add(grid);

      const raycaster = new THREE.Raycaster();
      const pointer = new THREE.Vector2();
      const pick = (event: PointerEvent): void => {
        if (!interactionDirective.pickable || interaction.visible !== true || interaction.userData.authorized !== true) return;
        const rect = renderer.domElement.getBoundingClientRect();
        pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
        raycaster.setFromCamera(pointer, camera);
        const hit = raycaster.intersectObject(interaction, false)[0];
        if (hit && hit.object.userData.pickable === true) onSemanticPick(String(hit.object.userData.stableEntityId));
      };
      pointerTarget = renderer.domElement;
      pointerHandler = pick;
      pointerTarget.addEventListener("pointerdown", pointerHandler);

      const resize = (): void => {
        const width = Math.max(container.clientWidth, 1);
        const height = Math.max(container.clientHeight, 1);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height, false);
      };
      observer = new ResizeObserver(resize);
      observer.observe(container);
      resize();
      const render = (): void => {
        renderer.render(scene, camera);
        if (!reducedMotion) animation = requestAnimationFrame(render);
      };
      render();
      disposables.push(
        metric.geometry,
        metric.material,
        splatGeometry,
        splats.material,
        design.geometry,
        design.material,
        interaction.geometry,
        interaction.material,
        evidence.geometry,
        evidence.material,
        renderer
      );
    }).catch(() => setFallback("WebGL rendering is unavailable. Semantic scene navigation and evidence remain available."));

    return () => {
      disposed = true;
      cancelAnimationFrame(animation);
      observer?.disconnect();
      if (pointerTarget && pointerHandler) pointerTarget.removeEventListener("pointerdown", pointerHandler);
      for (const item of disposables) item.dispose();
      container.replaceChildren();
    };
  }, [bundle, clippingEnabled, directives, highContrast, onSemanticPick, reducedMotion]);

  return (
    <div className="hybrid-canvas-shell" data-visible-roles={visibleRoles}>
      <div ref={host} className="hybrid-canvas" data-renderer="native-three-mesh-splat" />
      {fallback ? <p role="status" className="renderer-fallback">{fallback}</p> : null}
      <p className="sr-only">Metric mesh, generated Gaussian point-splat appearance, design intent, disposable interaction geometry, and immutable evidence markers are independently selectable and labeled. Pointer hits originate only from an authorized visible interaction layer and must be re-resolved against metric evidence.</p>
    </div>
  );
}
