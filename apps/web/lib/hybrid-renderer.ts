import type { Camera, Intersection, Object3D, Plane, Scene, WebGLRenderer } from "three";
import type { WebGPURenderer } from "three/webgpu";
import { pickInteractionOnly, planResourceAdmission, type HybridRole, type ResourceBudget } from "./spatial-runtime";

export interface HybridRenderable {
  readonly bindingId: string;
  readonly stableEntityId: string | null;
  readonly role: HybridRole | "collision" | "navigation" | "occlusion" | "spatial_audio";
  readonly representationKind: "mesh" | "gaussian_splat" | "semantic";
  readonly object: Object3D;
  readonly triangles: number;
  readonly splats: number;
  readonly gpuBytes: number;
  readonly sourceCommitId: string;
  readonly authorityLabel: string;
}
export interface HybridRendererContext { readonly scene: Scene; readonly camera: Camera; readonly renderer: WebGLRenderer | WebGPURenderer; }
export interface HybridRendererFactory { create(container: HTMLElement): Promise<HybridRendererContext>; loadMesh(bindingId: string, uri: string): Promise<Object3D>; loadGaussianSplat(bindingId: string, uri: string): Promise<Object3D>; }
export class NativeHybridSceneRenderer {
  private context: HybridRendererContext | null = null;
  private readonly objects = new Map<string, HybridRenderable>();
  private clippingPlanes: readonly Plane[] = [];
  constructor(private readonly factory: HybridRendererFactory, private readonly budget: ResourceBudget) {}
  async mount(container: HTMLElement): Promise<void> { if (this.context) throw new Error("RENDERER_ALREADY_MOUNTED"); this.context = await this.factory.create(container); }
  async add(binding: Omit<HybridRenderable, "object"> & { uri: string }): Promise<boolean> {
    if (!this.context) throw new Error("RENDERER_NOT_MOUNTED");
    const admission = planResourceAdmission([...this.objects.values(), binding].map((item) => ({ id: item.bindingId, role: item.role === "collision" || item.role === "navigation" || item.role === "occlusion" || item.role === "spatial_audio" ? "interaction" : item.role, priority: item.role === "metric" ? 0 : item.role === "interaction" ? 1 : 2, triangles: item.triangles, splats: item.splats, gpuBytes: item.gpuBytes, drawCalls: 1 })), this.budget);
    if (!admission.admitted.some((item) => item.id === binding.bindingId)) return false;
    const object = binding.representationKind === "gaussian_splat" ? await this.factory.loadGaussianSplat(binding.bindingId, binding.uri) : await this.factory.loadMesh(binding.bindingId, binding.uri);
    object.userData = { ...object.userData, bindingId: binding.bindingId, stableEntityId: binding.stableEntityId, role: binding.role, authorityLabel: binding.authorityLabel, sourceCommitId: binding.sourceCommitId };
    this.context.scene.add(object); this.objects.set(binding.bindingId, { ...binding, object }); return true;
  }
  setClippingPlanes(planes: readonly Plane[]): void { this.clippingPlanes = [...planes]; if (this.context && "clippingPlanes" in this.context.renderer) this.context.renderer.clippingPlanes = [...planes]; }
  pick(intersections: readonly Intersection<Object3D>[]): Intersection<Object3D> | null {
    const candidates = intersections.map((hit) => ({ ...hit, role: hit.object.userData.role as HybridRole, interactive: hit.object.userData.role === "interaction", stableEntityId: String(hit.object.userData.stableEntityId ?? "") }));
    return pickInteractionOnly(candidates);
  }
  diagnostics(): Record<string, string | null> {
    const roles = ["collision", "navigation", "occlusion", "spatial_audio"];
    return Object.fromEntries(roles.map((role) => [role, [...this.objects.values()].find((item) => item.role === role)?.bindingId ?? null]));
  }
  render(): void { if (this.context) this.context.renderer.render(this.context.scene, this.context.camera); }
  dispose(): void { for (const item of this.objects.values()) this.context?.scene.remove(item.object); this.objects.clear(); this.context?.renderer.dispose(); this.context = null; this.clippingPlanes = []; }
}
