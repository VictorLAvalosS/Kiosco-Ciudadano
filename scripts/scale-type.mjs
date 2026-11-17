import fs from "node:fs";

const path = new URL("../src/index.css", import.meta.url);
let css = fs.readFileSync(path, "utf8");

const STEPS = [
  [6, 13, 14.5],
  [8, 14.75, 17],
  [10, 15.75, 18.5],
  [12, 16.75, 19.5],
  [15, 18, 21],
  [18, 20, 23.5],
  [25, 24, 31],
  [36, 30, 40],
  [70, 44, 74],
];

function fluid(raw) {
  const n = Number(raw);
  let min;
  let max;
  if (n <= STEPS[0][0]) {
    [, min, max] = STEPS[0];
  } else if (n >= STEPS.at(-1)[0]) {
    min = n * 0.72;
    max = n * 1.04;
  } else {
    let index = 0;
    while (STEPS[index + 1][0] < n) index += 1;
    const [from, fromMin, fromMax] = STEPS[index];
    const [to, toMin, toMax] = STEPS[index + 1];
    const t = (n - from) / (to - from);
    min = fromMin + (toMin - fromMin) * t;
    max = fromMax + (toMax - fromMax) * t;
  }
  if (max - min < 1.25) max = min + 1.25;
  const a = (max - min) / 12;
  const b = Math.max(0, min - a * 4.8);
  const num = (value) => String(Math.round(value * 100) / 100);
  return `clamp(${num(min)}px, ${num(a)}vw + ${num(b)}px, ${num(max)}px)`;
}

const before = (css.match(/font-size:\s*\d+(?:\.\d+)?px/g) || []).length;
css = css.replace(/font-size:\s*(\d+(?:\.\d+)?)px/g, (_, n) => `font-size: ${fluid(n)}`);

let shorthand = 0;
css = css.replace(/font:\s*([^;{}]+)/g, (full, value) => {
  if (value.includes("clamp(")) return full;
  if (!/(\d+(?:\.\d+)?)px/.test(value)) return full;
  shorthand += 1;
  const next = value.replace(/(\d+(?:\.\d+)?)px(\/[0-9.]+)?/, (_, n, lh) => `${fluid(n)}${lh || ""}`);
  return `font: ${next}`;
});

const leftover = (css.match(/(?<![\d.])(?<!clamp\([^)]{0,80})\d+(?:\.\d+)?px/g) || []).length;
fs.writeFileSync(path, css);
console.log(JSON.stringify({ fontSizeRules: before, shorthandRules: shorthand, leftoverPxTokens: leftover }));
