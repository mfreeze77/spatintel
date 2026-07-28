"use client";

import { useEffect, useRef, useState } from "react";

type HybridCanvasProps = Readonly<{
  reducedMotion: boolean;
  highContrast: boolean;
  clippingEnabled: boolean;
  comparisonSplit: number;
  onSemanticPick: (stableEntityId: string) => void;
}>;

export function HybridCanvas({ reducedMotion, highContrast, clippingEnabled, comparisonSplit, onSemanticPick }: HybridCanvasProps): React.ReactNode {
  const host = useRef<HTMLDivElement>(null);
  const [fallback, setFallback] = useState<string | null>(null);
  useEffect(() => {
    const container = host.current;
    if (!container) return;
    let disposed = false;
    let animation = 0;
    const disposables: Array<{ dispose(): void }> = [];
    void import("three").then((THREE) => {
      if (disposed) return;
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(55, 1, 0.05, 100);
      camera.position.set(4.2, 3.1, 5.6);
      camera.lookAt(0, 1.2, 0);
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
      renderer.localClippingEnabled = true;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.setClearColor(highContrast ? 0x000000 : 0x101820, 1);
      renderer.domElement.setAttribute("aria-hidden", "true");
      container.replaceChildren(renderer.domElement);

      const metric = new THREE.Mesh(
        new THREE.BoxGeometry(4, 2.8, 5),
        new THREE.MeshStandardMaterial({ color: 0x486581, transparent: true, opacity: 0.42, side: THREE.DoubleSide })
      );
      metric.name = "metric:room-101";
      metric.userData = { role: "metric", stableEntityId: "room-101", authorityLabel: "observed metric evidence" };
      metric.position.y = 1.4;
      scene.add(metric);

      const splatPositions = new Float32Array(1500 * 3);
      const splatColors = new Float32Array(1500 * 3);
      for (let i = 0; i < 1500; i += 1) {
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
      const splats = new THREE.Points(splatGeometry, new THREE.PointsMaterial({ size: 0.035, vertexColors: true, transparent: true, opacity: 0.58 * comparisonSplit, depthWrite: false }));
      splats.name = "visual:gaussian-splat";
      splats.userData = { role: "visual", stableEntityId: null, authorityLabel: "generated visual reconstruction" };
      scene.add(splats);

      const design = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(4.15, 2.95, 5.15)),
        new THREE.LineBasicMaterial({ color: highContrast ? 0xffff00 : 0xffc857, transparent: true, opacity: 0.85 })
      );
      design.position.y = 1.475;
      design.name = "design:room-101";
      design.userData = { role: "design", stableEntityId: "room-101", authorityLabel: "design intent" };
      scene.add(design);

      const interaction = new THREE.Mesh(
        new THREE.BoxGeometry(4.05, 2.85, 5.05),
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.03, depthWrite: false })
      );
      interaction.position.y = 1.425;
      interaction.name = "interaction:room-101";
      interaction.userData = { role: "interaction", stableEntityId: "room-101", authorityLabel: "disposable non-authoritative proxy" };
      scene.add(interaction);

      const clippingPlane = new THREE.Plane(new THREE.Vector3(1, 0, 0), 0);
      for (const object of [metric, splats, design, interaction]) {
        const material = object.material;
        if (Array.isArray(material)) material.forEach((item) => { item.clippingPlanes = clippingEnabled ? [clippingPlane] : []; });
        else material.clippingPlanes = clippingEnabled ? [clippingPlane] : [];
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
        const rect = renderer.domElement.getBoundingClientRect();
        pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
        raycaster.setFromCamera(pointer, camera);
        const hit = raycaster.intersectObject(interaction, false)[0];
        if (hit) onSemanticPick(String(hit.object.userData.stableEntityId));
      };
      renderer.domElement.addEventListener("pointerdown", pick);

      const resize = (): void => {
        const width = Math.max(container.clientWidth, 1);
        const height = Math.max(container.clientHeight, 1);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height, false);
      };
      const observer = new ResizeObserver(resize);
      observer.observe(container);
      resize();
      const render = (): void => {
        renderer.render(scene, camera);
        if (!reducedMotion) animation = requestAnimationFrame(render);
      };
      render();
      disposables.push(metric.geometry, metric.material, splatGeometry, splats.material, design.geometry, design.material, interaction.geometry, interaction.material, renderer);
      return () => {
        observer.disconnect(); renderer.domElement.removeEventListener("pointerdown", pick);
      };
    }).catch(() => setFallback("WebGL rendering is unavailable. Semantic scene navigation and evidence remain available."));
    return () => {
      disposed = true;
      cancelAnimationFrame(animation);
      for (const item of disposables) item.dispose();
      container.replaceChildren();
    };
  }, [clippingEnabled, comparisonSplit, highContrast, onSemanticPick, reducedMotion]);

  return (
    <div className="hybrid-canvas-shell">
      <div ref={host} className="hybrid-canvas" data-renderer="native-three-mesh-splat" />
      {fallback ? <p role="status" className="renderer-fallback">{fallback}</p> : null}
      <p className="sr-only">Metric mesh, generated Gaussian point-splat appearance, design intent, and disposable interaction geometry are rendered as separate layers. Pointer hits originate only from the interaction layer and must be re-resolved against metric evidence.</p>
    </div>
  );
}
