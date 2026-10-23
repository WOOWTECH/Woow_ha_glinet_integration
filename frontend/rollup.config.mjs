import resolve from "@rollup/plugin-node-resolve";
import terser from "@rollup/plugin-terser";
import typescript from "@rollup/plugin-typescript";

// One ES module, committed into the integration so it installs without a build step.
export default {
  input: "src/woow-glinet-panel.ts",
  output: {
    file: "../custom_components/woow_glinet/frontend/woow-glinet-panel.js",
    format: "es",
    inlineDynamicImports: true,
  },
  plugins: [resolve(), typescript(), terser({ format: { comments: false } })],
};
