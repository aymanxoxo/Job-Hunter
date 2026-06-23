import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";

import SettingsView from "../SettingsView.vue";

const configKey = "jobhunter.desktopConfig.v1";

vi.mock("vue-router", () => ({
  RouterLink: defineComponent({
    props: {
      to: { type: String, required: true },
    },
    template: '<a :href="to"><slot /></a>',
  }),
  RouterView: defineComponent({
    template: '<main data-testid="route-view" />',
  }),
  useRoute: () => ({ meta: { title: "Settings" } }),
}));

function mountSettings() {
  return mount(SettingsView, { attachTo: document.body });
}

function persistedConfig() {
  const raw = localStorage.getItem(configKey);
  expect(raw).toBeTruthy();
  return JSON.parse(raw ?? "{}");
}

describe("SettingsView DuckDuckGo controls", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("hides DDG controls when DuckDuckGo connector is unchecked by default", () => {
    const wrapper = mountSettings();

    expect(wrapper.get<HTMLInputElement>("[data-testid='connector-duckduckgo']").element.checked).toBe(false);
    expect(wrapper.find("[data-testid='ddg-results-per-query']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='ddg-trust-threshold']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='ddg-trust-check']").exists()).toBe(false);
  });

  it("shows DDG controls after DuckDuckGo connector is checked", async () => {
    const wrapper = mountSettings();

    await wrapper.get("[data-testid='connector-duckduckgo']").setValue(true);

    expect(wrapper.find("[data-testid='ddg-results-per-query']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='ddg-trust-threshold']").exists()).toBe(true);
    expect(wrapper.find("[data-testid='ddg-trust-check']").exists()).toBe(true);
  });

  it("defaults results per query to 10", async () => {
    const wrapper = mountSettings();

    await wrapper.get("[data-testid='connector-duckduckgo']").setValue(true);

    expect(wrapper.get<HTMLInputElement>("[data-testid='ddg-results-per-query']").element.value).toBe("10");
  });

  it("defaults trust threshold to 60", async () => {
    const wrapper = mountSettings();

    await wrapper.get("[data-testid='connector-duckduckgo']").setValue(true);

    expect(wrapper.get<HTMLInputElement>("[data-testid='ddg-trust-threshold']").element.value).toBe("60");
  });

  it("checks trust check by default", async () => {
    const wrapper = mountSettings();

    await wrapper.get("[data-testid='connector-duckduckgo']").setValue(true);

    expect(wrapper.get<HTMLInputElement>("[data-testid='ddg-trust-check']").element.checked).toBe(true);
  });

  it("saves DDG config with backend snake_case field names", async () => {
    const wrapper = mountSettings();

    await wrapper.get("[data-testid='connector-duckduckgo']").setValue(true);
    await wrapper.get("[data-testid='ddg-results-per-query']").setValue(25);
    await wrapper.get("[data-testid='ddg-trust-threshold']").setValue(72);
    await wrapper.get("[data-testid='ddg-trust-check']").setValue(false);
    await wrapper.get("[data-testid='save-settings']").trigger("click");

    const config = persistedConfig();
    expect(config.connectors.duckduckgo.results_per_query).toBe(25);
    expect(config.connectors.duckduckgo.trust_threshold).toBe(72);
    expect(config.connectors.duckduckgo.trust_check_enabled).toBe(false);
  });

  it("loads persisted DDG settings from localStorage", async () => {
    localStorage.setItem(
      configKey,
      JSON.stringify({
        ai: { provider: "ollama" },
        connectors: {
          mock: { enabled: true, max_results: 50, delay_min: 2, delay_max: 2 },
          adzuna: { enabled: false, max_results: 50, delay_min: 2, delay_max: 2 },
          duckduckgo: {
            enabled: true,
            max_results: 50,
            delay_min: 2,
            delay_max: 2,
            results_per_query: 18,
            trust_threshold: 44,
            trust_check_enabled: false,
          },
        },
        auth: {
          gemini_api_key_env: "GEMINI_API_KEY",
          openrouter_api_key_env: "OPENROUTER_API_KEY",
        },
      }),
    );

    const wrapper = mountSettings();
    await wrapper.vm.$nextTick();

    expect(wrapper.get<HTMLInputElement>("[data-testid='connector-duckduckgo']").element.checked).toBe(true);
    expect(wrapper.get<HTMLInputElement>("[data-testid='ddg-results-per-query']").element.value).toBe("18");
    expect(wrapper.get<HTMLInputElement>("[data-testid='ddg-trust-threshold']").element.value).toBe("44");
    expect(wrapper.get<HTMLInputElement>("[data-testid='ddg-trust-check']").element.checked).toBe(false);
  });

  it("writes DuckDuckGo enabled false when connector is unchecked", async () => {
    const wrapper = mountSettings();

    await wrapper.get("[data-testid='save-settings']").trigger("click");

    const config = persistedConfig();
    expect(config.connectors.duckduckgo.enabled).toBe(false);
  });
});
