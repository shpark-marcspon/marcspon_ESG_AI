import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const workspaceRoot = path.resolve(scriptDir, "../../..");

const source = JSON.parse(
  fs.readFileSync(
    path.join(workspaceRoot, "packages/common/public/token.json"),
    "utf8",
  ),
);

const tailwind = await import("../theme-tokens.ts");
const chakraColors =
  await import("../../common/src/generated/tokens/colors.ts");
const chakraTextStyles =
  await import("../../common/src/generated/tokens/text-styles.ts");

const errors = [];
const warnings = [];
const isHex = (value) =>
  /^#(?:[\da-f]{3,4}|[\da-f]{6}|[\da-f]{8})$/i.test(value);

const toColorKey = (key) => key.replace(/-(\d+)$/, (_, step) => `.${step}`);
const toSemanticKey = (key) => key.replaceAll("-", ".").replaceAll(" ", "");

for (const [sourceKey, token] of Object.entries(source.colors.colorSchema)) {
  const key = toColorKey(sourceKey);
  if (tailwind.colorSchema[key] !== token.value) {
    errors.push(
      `Tailwind color mismatch: ${key} (${tailwind.colorSchema[key]} !== ${token.value})`,
    );
  }
}

for (const [key, value] of Object.entries(tailwind.colorSchema)) {
  if (!isHex(value)) errors.push(`Invalid Tailwind HEX: ${key}=${value}`);
}

for (const [sourceKey, modes] of Object.entries(source.colors.semanticTokens)) {
  const key = toSemanticKey(sourceKey);
  const sourceValue = modes.light?.value ?? modes["mode 1"]?.value;
  const copied = tailwind.semanticColors[key]?.default;
  if (sourceValue && copied !== sourceValue) {
    errors.push(
      `Tailwind semantic mismatch: ${key} (${copied} !== ${sourceValue})`,
    );
  }
}

for (const [key, value] of Object.entries(chakraColors.colorSchema)) {
  if (!isHex(value))
    warnings.push(`Invalid generated Chakra HEX: ${key}=${value}`);
}

for (const [key, value] of Object.entries(chakraTextStyles.textStyles)) {
  if (JSON.stringify(tailwind.textStyles[key]) !== JSON.stringify(value)) {
    errors.push(
      `Tailwind text style differs from current Chakra runtime: ${key}`,
    );
  }
}

if (warnings.length) {
  console.warn(warnings.join("\n"));
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exitCode = 1;
} else {
  console.log(
    `Theme snapshot OK: ${Object.keys(tailwind.colorSchema).length} colors, ${Object.keys(tailwind.semanticColors).length} semantic colors, ${Object.keys(tailwind.textStyles).length} text styles`,
  );
}
