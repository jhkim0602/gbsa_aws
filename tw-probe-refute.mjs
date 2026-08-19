import { compile } from "tailwindcss";
import fs from "node:fs";
import path from "node:path";
const root = "/Users/junghwan/orca/workspaces/GBSA_AWS_PROJECT-main/dolphin";
const input = `@import "tailwindcss";\n@import "@iep/design-system/theme.css";`;
const compiler = await compile(input, {
  base: root,
  loadStylesheet: async (id, base) => {
    let file;
    if (id === "tailwindcss") file = path.join(root, "node_modules/tailwindcss/index.css");
    else if (id.startsWith("tailwindcss/")) file = path.join(root, "node_modules", id);
    else if (id === "@iep/design-system/theme.css") file = path.join(root, "packages/design-system/theme.css");
    else file = path.resolve(base, id);
    return { path: file, base: path.dirname(file), content: fs.readFileSync(file, "utf8") };
  },
});
const candidates = process.argv.slice(2);
const css = compiler.build(candidates);
console.log(css);
