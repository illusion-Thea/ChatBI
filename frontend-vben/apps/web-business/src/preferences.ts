import { defineOverridesPreferences } from '@vben/preferences';
export const overridesPreferences = defineOverridesPreferences({
  app: { name: 'QueryX', defaultHomePath: '/overview', enableCheckUpdates: false },
  logo: { source: '/queryx-logo.svg', showText: true, logoMode: 'icon' },
  transition: { enable: false, loading: false, progress: false },
  theme: { mode: 'light', semiDarkSidebar: false, radius: '0.25' },
  copyright: { enable: false },
  widget: { themeToggle: false, notification: false, lockScreen: false, languageToggle: false, timezone: false },
});
export const preferencesExtension = undefined;
