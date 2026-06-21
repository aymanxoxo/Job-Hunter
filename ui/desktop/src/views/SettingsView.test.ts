import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import SettingsView from "./SettingsView.vue";

const configKey = "jobhunter.desktopConfig.v1";
const secureStatusKey = "jobhunter.secureStatus.v1";

async function mountView() {
  setActivePinia(createPinia());
  return mount(SettingsView, {
    attachTo: document.body,
  });
}

describe("SettingsView", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    localStorage.clear();
  });

  it("lets the user select providers, connectors, max results, and delay", async () => {
    const wrapper = await mountView();

    await wrapper.get("[data-testid='provider-select']").setValue("openrouter");
    await wrapper.get("[data-testid='connector-mock']").setValue(true);
    await wrapper.get("[data-testid='connector-adzuna']").setValue(false);
    await wrapper.get("[data-testid='max-results']").setValue("35");
    await wrapper.get("[data-testid='delay-range']").setValue("4");

    expect((wrapper.get("[data-testid='provider-select']").element as HTMLSelectElement).value).toBe("openrouter");
    expect((wrapper.get("[data-testid='connector-mock']").element as HTMLInputElement).checked).toBe(true);
    expect((wrapper.get("[data-testid='connector-adzuna']").element as HTMLInputElement).checked).toBe(false);
    expect(wrapper.text()).toContain("35");
    expect(wrapper.text()).toContain("4s");
  });

  it("persists and restores non-secret settings only", async () => {
    const wrapper = await mountView();

    await wrapper.get("[data-testid='provider-select']").setValue("gemini");
    await wrapper.get("[data-testid='connector-mock']").setValue(true);
    await wrapper.get("[data-testid='max-results']").setValue("25");
    await wrapper.get("[data-testid='delay-range']").setValue("3");
    await wrapper.get("[data-testid='save-settings']").trigger("click");

    const saved = JSON.parse(localStorage.getItem(configKey) ?? "{}");
    expect(saved.ai.provider).toBe("gemini");
    expect(saved.connectors.mock.enabled).toBe(true);
    expect(saved.connectors.mock.max_results).toBe(25);
    expect(saved.connectors.adzuna.delay_min).toBe(3);
    expect(saved.auth).toEqual({
      gemini_api_key_env: "GEMINI_API_KEY",
      openrouter_api_key_env: "OPENROUTER_API_KEY",
    });

    wrapper.unmount();
    const restored = await mountView();
    expect((restored.get("[data-testid='provider-select']").element as HTMLSelectElement).value).toBe("gemini");
    expect((restored.get("[data-testid='connector-mock']").element as HTMLInputElement).checked).toBe(true);
    expect((restored.get("[data-testid='max-results']").element as HTMLInputElement).value).toBe("25");
  });

  it("masks API keys and never writes the secret into persisted config", async () => {
    const wrapper = await mountView();
    const secret = "sk-test-super-secret";

    await wrapper.get("[data-testid='provider-select']").setValue("gemini");
    const input = wrapper.get("[data-testid='api-key']");
    expect(input.attributes("type")).toBe("password");

    await input.setValue(secret);
    await wrapper.get("[data-testid='save-api-key']").trigger("click");
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).not.toContain(secret);
    expect(wrapper.html()).not.toContain(secret);
    expect((wrapper.get("[data-testid='api-key']").element as HTMLInputElement).value).toBe("");
    expect(localStorage.getItem(configKey) ?? "").not.toContain(secret);
    expect(localStorage.getItem(secureStatusKey) ?? "").not.toContain(secret);
    expect(wrapper.text()).toContain("Saved to OS secure store");
  });

  it("shows deferred OAuth and LinkedIn auth controls as disabled", async () => {
    const wrapper = await mountView();

    expect(wrapper.get("[data-testid='connect-oauth']").attributes("disabled")).toBeDefined();
    expect(wrapper.get("[data-testid='connect-linkedin']").attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("Deferred");
  });
});
