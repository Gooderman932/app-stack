import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.poorduде.budgetmeal',
  appName: 'Budget Meal Platform',
  webDir: 'dist',
  android: {
    buildOptions: {
      keystorePath: 'keystore/upload-key.jks',
      keystoreAlias: 'upload',
    },
  },
  plugins: {
    StatusBar: {
      style: 'Dark',
      backgroundColor: '#1a1a2e',
    },
  },
};

export default config;
