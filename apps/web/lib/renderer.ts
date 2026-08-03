import type { Camera, Object3D, Scene, WebGLRenderer } from "three";
import type { WebGPURenderer } from "three/webgpu";

export interface SpatialRendererAdapter {
  readonly adapterId: string;
  readonly capabilities: ReadonlySet<"mesh" | "splat" | "picking" | "clipping" | "occlusion" | "webxr">;
  mount(container: HTMLElement): Promise<void>;
  render(): void;
  resize(width: number, height: number, devicePixelRatio: number): void;
  setLayerVisibility(layerId: string, visible: boolean): void;
  dispose(): void;
}

export interface ThreeRendererContext {
  readonly scene: Scene;
  readonly camera: Camera;
  readonly renderer: WebGLRenderer | WebGPURenderer;
  readonly objectsByLayer: ReadonlyMap<string, readonly Object3D[]>;
}

export type ThreeContextFactory = (container: HTMLElement) => Promise<ThreeRendererContext>;

export class ThreeCompatibleRendererAdapter implements SpatialRendererAdapter {
  readonly adapterId = "three-compatible-v1";
  readonly capabilities = new Set<"mesh" | "splat" | "picking" | "clipping" | "occlusion">([
    "mesh", "splat", "picking", "clipping", "occlusion"
  ]);
  private context: ThreeRendererContext | null = null;
  constructor(private readonly createContext: ThreeContextFactory) {}

  async mount(container: HTMLElement): Promise<void> {
    if (this.context) throw new Error("RENDERER_ALREADY_MOUNTED");
    this.context = await this.createContext(container);
  }

  render(): void {
    if (!this.context) return;
    this.context.renderer.render(this.context.scene, this.context.camera);
  }

  resize(width: number, height: number, devicePixelRatio: number): void {
    if (!this.context) return;
    this.context.renderer.setPixelRatio(Math.min(Math.max(devicePixelRatio, 1), 2));
    this.context.renderer.setSize(Math.max(width, 1), Math.max(height, 1), false);
  }

  setLayerVisibility(layerId: string, visible: boolean): void {
    for (const object of this.context?.objectsByLayer.get(layerId) ?? []) object.visible = visible;
  }

  dispose(): void {
    if (!this.context) return;
    this.context.renderer.dispose();
    this.context = null;
  }
}

export class AccessibleFallbackRenderer implements SpatialRendererAdapter {
  readonly adapterId = "accessible-fallback-v1";
  readonly capabilities = new Set<"picking">(["picking"]);
  private root: HTMLElement | null = null;

  async mount(container: HTMLElement): Promise<void> {
    const root = document.createElement("div");
    root.className = "fallback-renderer";
    root.setAttribute("role", "img");
    root.setAttribute("aria-label", "Textual spatial-scene fallback. Use the scene tree and evidence panel to inspect entities.");
    root.textContent = "3D rendering is unavailable. Semantic scene navigation remains available.";
    container.replaceChildren(root);
    this.root = root;
  }
  render(): void {}
  resize(): void {}
  setLayerVisibility(): void {}
  dispose(): void { this.root?.remove(); this.root = null; }
}
