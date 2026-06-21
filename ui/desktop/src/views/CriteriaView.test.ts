import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePipelineStore } from "@/stores/pipeline";
import type { CriteriaResult } from "@/stores/pipeline";
import CriteriaView from "./CriteriaView.vue";

const routerMocks = vi.hoisted(() => ({
  push: vi.fn(),
}));

vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: routerMocks.push,
  }),
}));

const storageKey = "jobhunter.criteriaDraft.v1";
const generatedCriteria: CriteriaResult = {
  titles: ["Platform Engineer", "Python Developer"],
  keywords: ["python", "kubernetes", "gcp", "ci/cd"],
  exclude_keywords: [],
  seniority_levels: ["senior"],
  locations: ["remote", "cairo"],
  min_score_threshold: 40,
};

function wrapperText(wrapper: ReturnType<typeof mount>) {
  return wrapper.text().replace(/\s+/g, " ");
}

function inputValues(wrapper: ReturnType<typeof mount>, testId: string) {
  return wrapper.findAll(`[data-testid="${testId}"]`).map((chip) => (chip.element as HTMLInputElement).value);
}

async function mountView(criteriaResponse: Promise<CriteriaResult> = Promise.resolve(generatedCriteria)) {
  setActivePinia(createPinia());
  routerMocks.push.mockReset();
  const store = usePipelineStore();
  vi.spyOn(store, "generateCriteria").mockReturnValue(criteriaResponse);
  return mount(CriteriaView, {
    attachTo: document.body,
  });
}

describe("CriteriaView", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders profile input, provider selector, disabled upload, and generate state", async () => {
    const wrapper = await mountView();

    expect(wrapper.find('[data-testid="profile-input"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="provider-select"]').exists()).toBe(true);
    expect(wrapper.get('[data-testid="upload-control"]').attributes("aria-disabled")).toBe("true");
    expect(wrapper.get('[data-testid="generate-button"]').attributes("disabled")).toBeUndefined();

    await wrapper.get('[data-testid="profile-input"]').setValue("   ");

    expect(wrapper.get('[data-testid="generate-button"]').attributes("disabled")).toBeDefined();
  });

  it("generates editable criteria chips through the provider IPC path", async () => {
    let resolveCriteria: (criteria: CriteriaResult) => void;
    const pendingCriteria = new Promise<CriteriaResult>((resolve) => {
      resolveCriteria = resolve;
    });
    const wrapper = await mountView(pendingCriteria);
    const store = usePipelineStore();

    await wrapper.get('[data-testid="profile-input"]').setValue(
      "Senior .NET DevOps engineer in Cairo. Python, C#, Kubernetes, GCP, CI/CD, remote.",
    );
    await wrapper.get('[data-testid="provider-select"]').setValue("gemini");
    await wrapper.get('[data-testid="generate-button"]').trigger("click");

    expect(wrapperText(wrapper)).toContain("Generating");
    resolveCriteria!(generatedCriteria);
    await vi.waitFor(() => expect(wrapperText(wrapper)).toContain("Generated criteria"));
    expect(store.generateCriteria).toHaveBeenCalledWith({
      profile: "Senior .NET DevOps engineer in Cairo. Python, C#, Kubernetes, GCP, CI/CD, remote.",
      provider: "gemini",
    });
    expect(inputValues(wrapper, "keywords-chip-input")).toEqual(
      expect.arrayContaining(["python", "kubernetes", "gcp", "ci/cd"]),
    );
    expect(inputValues(wrapper, "locations-chip-input")).toEqual(expect.arrayContaining(["remote", "cairo"]));
  });

  it("lets the user add, edit, and remove keyword chips", async () => {
    const wrapper = await mountView();

    await wrapper.get('[data-testid="generate-button"]').trigger("click");
    await vi.waitFor(() => expect(wrapper.find('[data-testid="keywords-add"]').exists()).toBe(true));
    await wrapper.get('[data-testid="keywords-add"]').trigger("click");

    const added = wrapper.findAll('[data-testid="keywords-chip-input"]').at(-1);
    expect(added).toBeTruthy();
    await added!.setValue("platform engineering");
    expect(inputValues(wrapper, "keywords-chip-input")).toContain("platform engineering");

    const first = wrapper.findAll('[data-testid="keywords-chip-input"]')[0];
    await first.setValue("backend api");
    expect(inputValues(wrapper, "keywords-chip-input")).toContain("backend api");

    await wrapper.findAll('[data-testid="keywords-remove"]')[0].trigger("click");
    expect(inputValues(wrapper, "keywords-chip-input")).not.toContain("backend api");
  });

  it("applies refine add and exclude commands", async () => {
    const wrapper = await mountView();

    await wrapper.get('[data-testid="generate-button"]').trigger("click");
    await vi.waitFor(() => expect(wrapper.find('[data-testid="refine-input"]').exists()).toBe(true));
    await wrapper.get('[data-testid="refine-input"]').setValue("focus platform engineering");
    await wrapper.get('[data-testid="refine-send"]').trigger("click");
    await wrapper.get('[data-testid="refine-input"]').setValue("exclude python");
    await wrapper.get('[data-testid="refine-send"]').trigger("click");

    expect(wrapperText(wrapper)).toContain("platform engineering");
    expect(wrapperText(wrapper)).toContain("exclude python");
    expect(wrapperText(wrapper)).toContain("python");
    expect(
      wrapper
        .findAll('[data-testid="keywords-chip-input"]')
        .some((chip) => (chip.element as HTMLInputElement).value === "python"),
    ).toBe(false);
    expect(
      wrapper
        .findAll('[data-testid="exclude_keywords-chip-input"]')
        .some((chip) => (chip.element as HTMLInputElement).value === "python"),
    ).toBe(true);
  });

  it("saves and loads valid criteria while ignoring malformed saved JSON", async () => {
    const wrapper = await mountView();

    await wrapper.get('[data-testid="generate-button"]').trigger("click");
    await vi.waitFor(() => expect(wrapper.find('[data-testid="save-button"]').exists()).toBe(true));
    await wrapper.get('[data-testid="save-button"]').trigger("click");

    expect(JSON.parse(localStorage.getItem(storageKey) ?? "{}").keywords.length).toBeGreaterThan(0);

    wrapper.unmount();
    const restored = await mountView();
    expect(wrapperText(restored)).toContain("Generated criteria");

    restored.unmount();
    localStorage.setItem(storageKey, "{not json");
    const invalid = await mountView();
    expect(wrapperText(invalid)).not.toContain("Generated criteria");
  });

  it("runs the pipeline with selected provider and an augmented profile", async () => {
    const wrapper = await mountView();
    const store = usePipelineStore();
    const runPipeline = vi.spyOn(store, "runPipeline").mockResolvedValue(undefined);

    await wrapper.get('[data-testid="profile-input"]').setValue("Senior Python engineer in Cairo");
    await wrapper.get('[data-testid="provider-select"]').setValue("gemini");
    await wrapper.get('[data-testid="generate-button"]').trigger("click");
    await vi.waitFor(() => expect(wrapper.find('[data-testid="run-search"]').exists()).toBe(true));
    await wrapper.get('[data-testid="run-search"]').trigger("click");

    expect(runPipeline).toHaveBeenCalledWith({
      provider: "gemini",
      profile: expect.stringContaining("User-edited search criteria"),
    });
    expect(runPipeline.mock.calls[0][0].profile).toContain("Senior Python engineer in Cairo");
    expect(routerMocks.push).toHaveBeenCalledWith("/results");
  });

  it("disables Run Search while the pipeline is running", async () => {
    const wrapper = await mountView();
    const store = usePipelineStore();

    await wrapper.get('[data-testid="generate-button"]').trigger("click");
    await vi.waitFor(() => expect(wrapper.find('[data-testid="run-search"]').exists()).toBe(true));
    store.status = "running";
    await wrapper.vm.$nextTick();

    expect(wrapper.get('[data-testid="run-search"]').attributes("disabled")).toBeDefined();
  });
});
