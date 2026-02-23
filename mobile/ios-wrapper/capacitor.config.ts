import type { CapacitorConfig } from "@capacitor/cli";

const configuredUrl = String(process.env.NEXTSTEP_WEBAPP_URL || "").trim();

const defaultUrl = "https://script.google.com/macros/s/REPLACE_WITH_DEPLOYMENT_ID/exec";
const webAppUrl = configuredUrl || defaultUrl;

const config: CapacitorConfig = {
  appId: "ca.nextstep.admissions",
  appName: "Next Step Admissions",
  webDir: "www",
  bundledWebRuntime: false,
  server: {
    url: webAppUrl,
    cleartext: false,
    allowNavigation: [
      "script.google.com",
      "*.googleusercontent.com",
      "accounts.google.com"
    ]
  },
  ios: {
    contentInset: "automatic",
    limitsNavigationsToAppBoundDomains: false,
    preferredContentMode: "mobile",
    scrollEnabled: true
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 0
    },
    StatusBar: {
      style: "DARK"
    },
    Keyboard: {
      resize: "body",
      resizeOnFullScreen: true
    }
  }
};

export default config;
