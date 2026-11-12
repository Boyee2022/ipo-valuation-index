/**
 * Browser + node artifacts for the valuation workbench client bundle.
 *
 * Reproduces the four product conventions a DSH client bundle must satisfy
 * (same as @factorlab/workbench, without depending on the upstream build preset):
 *
 *   1. `window.__ModuleLoader__.load({ id, factory })` — the id is this package's
 *      name, the same string the loader row and the patch entry use;
 *   2. externals are exactly the platform baseline modules the page requires at
 *      runtime, so no duplicate singleton is inlined;
 *   3. CSS Modules are compiled here (lightningcss, same `[hash]_[local]` pattern
 *      the host uses) and injected once as `<style data-plugin-css>`;
 *   4. the module ends with `return module.exports`, so the loader sees a
 *      CommonJS-shaped factory.
 */

import { build } from 'esbuild'
import { readFile } from 'node:fs/promises'
import { basename } from 'node:path'
import { transform } from 'lightningcss'
import manifest from './package.json' with { type: 'json' }

/** The plugin id: package name, loader id, and patch row name are this one string. */
const PACKAGE = manifest.name

/** Platform baseline modules: provided by the frozen browser module table. */
const BASELINE = [
  'react',
  'react/jsx-runtime',
  'react-dom',
  'react-dom/client',
  '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-client-store',
  '@deepseek-ai/dsh-client-ui-slots',
  '@deepseek-ai/dsh-client-ui-primitives',
]

/**
 * Compile one CSS Modules file into a JS module exporting its class map and
 * injecting its stylesheet once.
 */
function cssModules() {
  return {
    name: 'valuation-css-modules',
    setup(context) {
      context.onLoad({ filter: /\.module\.css$/ }, async (args) => {
        const source = await readFile(args.path)
        const { code, exports } = transform({
          filename: args.path,
          code: source,
          cssModules: { pattern: '[hash]_[local]' },
          minify: true,
        })
        const classMap = {}
        for (const [local, exported] of Object.entries(exports ?? {})) classMap[local] = exported.name
        const tagId = `${PACKAGE}/${basename(args.path)}`
        return {
          loader: 'js',
          watchFiles: [args.path],
          contents: [
            `const css = ${JSON.stringify(code.toString())};`,
            `const tagId = ${JSON.stringify(tagId)};`,
            'if (typeof document !== \'undefined\' && document.querySelector(`style[data-plugin-css="${tagId}"]`) === null) {',
            '  const tag = document.createElement(\'style\');',
            `  tag.dataset.plugin = ${JSON.stringify(PACKAGE)};`,
            '  tag.dataset.pluginCss = tagId;',
            '  tag.textContent = css;',
            '  document.head.appendChild(tag);',
            '}',
            `export default ${JSON.stringify(classMap)};`,
          ].join('\n'),
        }
      })
    },
  }
}

await build({
  entryPoints: ['src/client/index.ts'],
  outfile: 'lib/client.js',
  bundle: true,
  format: 'cjs',
  platform: 'browser',
  target: 'es2022',
  sourcemap: true,
  jsx: 'automatic',
  external: BASELINE,
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'info',
  banner: {
    js: `window.__ModuleLoader__.load({ id: ${JSON.stringify(PACKAGE)}, factory: (require) => {\nvar module = { exports: {} }; var exports = module.exports;\nObject.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });`,
  },
  footer: { js: 'return module.exports;\n} });' },
  plugins: [cssModules()],
})

// The host half: this feature is entirely browser-side, so the node entry only
// has to exist for the loader to import the row's module name.
await build({
  entryPoints: ['src/index.ts'],
  outfile: 'lib/index.js',
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'es2024',
  logLevel: 'info',
})
