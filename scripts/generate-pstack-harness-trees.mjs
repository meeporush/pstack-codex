#!/usr/bin/env node

import { chmodSync, existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, posix, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PSTACK = join(ROOT, "upstream", "pstack");
const SKILLS = join(PSTACK, "skills");
const TREE = "codex";
const OUT = join(ROOT, "harness", "pstack", TREE);
const ADAPTER = "docs/harness/codex.md";
const GUIDE = "docs/guide";
const COMMAND = "node scripts/generate-pstack-harness-trees.mjs";
const { repository, commit } = JSON.parse(readFileSync(join(ROOT, "UPSTREAM.json"), "utf8"));
const LINK = /\]\(([^)\s]+)\)/g;
const EXPLICIT_INVOCATION_POLICY = "\npolicy:\n  allow_implicit_invocation: false\n";
// Checklist ordering is specific to the workflow router. The review matrix
// compares this override with the shared preamble before enabling it.
const PREAMBLE_OVERRIDES = {
  "poteto-mode": `In Codex, read [the Codex adapter](../../${ADAPTER}) first. Then read the selected playbook and open its checklist before inspecting project files.`,
};

const TERMS = [
  { key: "`Task`", re: /`Task`|\bTask (tool|subagent|call)/ },
  { key: "`AskQuestion`", re: /AskQuestion/ },
  { key: "todolist", re: /\btodo ?list\b/i },
  { key: "generalPurpose", re: /generalPurpose/ },
  { key: "poteto-agent", re: /poteto-agent/ },
  { key: "comment-sicko", re: /comment-sicko/ },
  { key: "`readonly: true`", re: /readonly: (true|false)|readonly\/Ask/ },
  { key: "`environment: \"cloud\"`", re: /environment: "(cloud|local)"/ },
  { key: "cloud_base_branch", re: /cloud_base_branch/ },
  { key: "`run_in_background: true`", re: /run_in_background/ },
  { key: "`resume`", re: /`resume`/ },
  { key: "`file_attachments`", re: /file_attachments/ },
  { key: "claude-", re: /\bclaude-[a-z]+-\d/ },
  { key: "grok-", re: /\bgrok-\d/ },
  { key: "gpt-", re: /\bgpt-\d/ },
  { key: "inherit-parent", re: /inherit-parent/ },
  { key: "pstack-models.mdc", re: /pstack-models\.mdc/ },
  { key: ".cursor/skills/", re: /\.cursor\/skills/ },
  { key: "~/.cursor/plugins/", re: /\.cursor\/plugins|\.cursor-plugin/ },
  { key: ".cursor/rules/", re: /\.cursor\/rules|always-applied rule/ },
  { key: "agent-transcripts", re: /agent-transcripts|\.cursor\/projects/ },
  { key: "Cursor-only features", re: /Bugbot|Cursor [Aa]utomation|cursor\.(sh|com)\/automations|[Cc]loud [Aa]gent|built-in PR tool/ },
];
const ROUTE_KEY = "Run another pstack skill";
const SKILL_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    if (name === ".DS_Store" || name === "node_modules") return [];
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

function file(path) {
  return { bytes: readFileSync(path), executable: (statSync(path).mode & 0o111) !== 0 };
}

const skills = readdirSync(SKILLS).filter((name) => existsSync(join(SKILLS, name, "SKILL.md")));

function classify(skill) {
  const dir = join(SKILLS, skill);
  const others = skills.filter((name) => name !== skill).join("|");
  const route = new RegExp(`the \\*\\*(?<bold>${others})\\*\\* skill|\`/(?<command>${others})\``, "g");
  const linksToSkill = (line, name) => line.includes(`(../${name}/`);
  const namesBareSkill = (line) =>
    [...line.matchAll(route)].some(({ groups }) => !linksToSkill(line, groups.bold ?? groups.command));
  const usesCursorNames = new Set();
  for (const path of walk(dir).filter((path) => path.endsWith(".md"))) {
    const text = readFileSync(path, "utf8");
    for (const term of TERMS) if (term.re.test(text)) usesCursorNames.add(term.key);
    if (text.split("\n").some(namesBareSkill)) usesCursorNames.add(ROUTE_KEY);
  }
  const text = readFileSync(join(dir, "SKILL.md"), "utf8");
  const wrap = usesCursorNames.size > 0 && /^# /m.test(text);
  const frontmatter = text.match(/^---\n([\s\S]*?)\n---/)?.[1] ?? "";
  return { usesCursorNames, wrap, frontmatter };
}

const classes = new Map(skills.map((skill) => [skill, classify(skill)]));
const problems = [];
const users = new Map();
for (const [skill, { usesCursorNames, wrap, frontmatter }] of classes) {
  if (usesCursorNames.size > 0 && !wrap) problems.push(`skills/${skill}/SKILL.md uses Cursor names but has no H1`);
  for (const key of usesCursorNames) users.set(key, [...(users.get(key) ?? []), skill]);
  // Match the folder and frontmatter names so Codex resolves the same skill as Cursor.
  const name = frontmatter.match(/^name:(.*)$/m)?.[1].trim().replace(/^(["'])(.*)\1$/, "$2");
  if (name !== skill) problems.push(`skills/${skill}/SKILL.md has name ${JSON.stringify(name ?? "")}, not its folder name ${skill}`);
  if (!SKILL_NAME.test(skill) || skill.length > 64) problems.push(`skills/${skill} is not lowercase words joined by hyphens, at most 64 characters`);
}
const adapter = readFileSync(join(ROOT, ADAPTER), "utf8");
for (const [key, using] of users) {
  if (!adapter.includes(key)) problems.push(`Codex adapter has no mapping for ${key}, used by ${using.join(", ")}`);
}
for (const problem of problems) console.log(`FAIL ${problem}`);
if (problems.length > 0) process.exit(1);

// Resolve local Markdown links against the installed tree.
function resolve(from, href) {
  const target = href.replace(/[#?].*/, "");
  if (!target || /^(?:[a-z][a-z0-9+.-]*:|\/|<)/i.test(target)) return undefined;
  return posix.join(posix.dirname(from), decodeURIComponent(target)).replace(/\/$/, "");
}

function has(files, path) {
  return files.has(path) || [...files.keys()].some((key) => key.startsWith(`${path}/`));
}

function render() {
  // Keep the shared reference material available inside the project-local install.
  const copies = [
    ...walk(SKILLS),
    ...walk(join(PSTACK, "agents")),
    ...walk(join(PSTACK, GUIDE)),
    join(PSTACK, "README.md"),
  ];
  const files = new Map(copies.map((path) => [relative(PSTACK, path), file(path)]));
  const manifest = file(join(ROOT, "docs/harness/codex-plugin.json"));
  const { name: pluginName } = JSON.parse(manifest.bytes.toString("utf8"));
  files.set(ADAPTER, file(join(ROOT, ADAPTER)));
  files.set(".codex-plugin/plugin.json", manifest);
  files.set("LICENSE", file(join(PSTACK, "LICENSE")));
  files.set("NOTICE", file(join(ROOT, "NOTICE")));
  const line =
    `In Codex, read [the Codex adapter](../../${ADAPTER}) once per session before you follow this skill. ` +
    "It maps the Cursor names in pstack skills to Codex.";
  for (const [skill, { wrap, frontmatter }] of classes) {
    const path = `skills/${skill}/SKILL.md`;
    const text = files.get(path).bytes.toString("utf8");
    if (wrap) {
      const preamble = PREAMBLE_OVERRIDES[skill] ?? line;
      files.get(path).bytes = Buffer.from(text.replace(/^(# .*)\n+/m, `$1\n\n${preamble}\n\n`));
    }
    const metadata = `skills/${skill}/agents/openai.yaml`;
    if (files.has(metadata)) throw new Error(`Review upstream Codex metadata at ${metadata}`);
    const displayName = `${pluginName}:${skill}`;
    let metadataText = `interface:\n  display_name: ${JSON.stringify(displayName)}\n`;
    if (/^disable-model-invocation:\s*true\s*$/m.test(frontmatter)) {
      metadataText += EXPLICIT_INVOCATION_POLICY;
    }
    files.set(metadata, { bytes: Buffer.from(metadataText), executable: false });
  }
  for (const [path, entry] of files) {
    if (!path.endsWith(".md")) continue;
    const text = entry.bytes.toString("utf8").replace(LINK, (link, href) => {
      const target = resolve(path, href);
      if (!target || target.split("/")[0] === ".." || has(files, target) || !existsSync(join(PSTACK, target))) return link;
      const kind = statSync(join(PSTACK, target)).isDirectory() ? "tree" : "blob";
      return `](${repository}/${kind}/${commit}/pstack/${target}${href.slice(href.search(/[#?]|$/))})`;
    });
    entry.bytes = Buffer.from(text);
  }
  return files;
}

// Links to upstream files omitted from the install already point at the pinned revision.
const files = render();
const dangling = [];
for (const [path, entry] of files) {
  if (!path.endsWith(".md")) continue;
  for (const [, href] of entry.bytes.toString("utf8").matchAll(LINK)) {
    const target = resolve(path, href);
    if (target && !has(files, target)) dangling.push(`harness/pstack/${TREE}/${path} links to ${href}, which is not in the tree`);
  }
}
for (const link of dangling) console.log(`FAIL ${link}`);
if (dangling.length > 0) process.exit(1);

if (process.argv.includes("--check")) {
  const onDisk = new Map(existsSync(OUT) ? walk(OUT).map((path) => [relative(OUT, path), file(path)]) : []);
  const drifted = [...new Set([...files.keys(), ...onDisk.keys()])].sort().filter((path) => {
    const [want, have] = [files.get(path), onDisk.get(path)];
    return !want || !have || !want.bytes.equals(have.bytes) || want.executable !== have.executable;
  });
  for (const path of drifted.slice(0, 20)) console.log(`harness/pstack/${TREE}/${path}`);
  if (drifted.length > 0) {
    console.log(`harness/pstack is out of date. Run \`${COMMAND}\` and commit the result.`);
    process.exit(1);
  }
  console.log("harness/pstack is up to date.");
} else {
  if (existsSync(OUT) && lstatSync(OUT).isSymbolicLink()) throw new Error(`Generated output is a symlink: ${OUT}`);
  rmSync(OUT, { recursive: true, force: true });
  for (const [path, { bytes, executable }] of files) {
    mkdirSync(dirname(join(OUT, path)), { recursive: true });
    writeFileSync(join(OUT, path), bytes);
    chmodSync(join(OUT, path), executable ? 0o755 : 0o644);
  }
  const wrapped = [...classes.values()].filter(({ wrap }) => wrap).length;
  console.log(`${skills.length} skills, ${wrapped} SKILL.md files with the adapter line`);
}
