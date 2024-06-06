import {legacyPlugin} from '@web/dev-server-legacy';
import { rollupPluginHTML as html } from '@web/rollup-plugin-html';
import { hmrPlugin } from '@open-wc/dev-server-hmr';

const mode = process.env.MODE || 'dev';
if (!['dev', 'prod'].includes(mode)) {
  throw new Error(`MODE must be "dev" or "prod", was "${mode}"`);
}

export default {
  nodeResolve: {exportConditions: mode === 'dev' ? ['development'] : []},
  //webSocketServer: {options: { path: sockPath }},
  open: false,
  preserveSymlinks: true,
  watch: true,
  output: {dir: 'public'},
  rootDir: 'public/',
  basePath: '/static',
  plugins: [
    hmrPlugin({
      include: ['src/**/*'],
    }),
    legacyPlugin({
      polyfills: {
        // Manually imported in index.html file
        webcomponents: false,
      },
    }),
  ],
};
