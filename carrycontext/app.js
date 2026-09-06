const source = document.getElementById('source');
const output = document.getElementById('output');
const generateButton = document.getElementById('generate');
const copyButton = document.getElementById('copy');
const status = document.getElementById('status');

const patterns = {
  decisions: /\b(decided|decision|choose|chosen|we will|we'll|going with|selected|use|keep|drop|不要|决定|选择|采用|保留|删除)\b/i,
  constraints: /\b(must|must not|can't|cannot|should|only|never|require|constraint|rule|必须|不能|只|不要|规则|要求)\b/i,
  actions: /\b(todo|next|need to|will do|implement|build|create|add|fix|follow up|下一步|需要|实现|创建|添加|修复|继续)\b/i,
  questions: /[?？]\s*$/
};

function cleanLines(text) {
  return text
    .split(/\n+/)
    .map(line => line.replace(/^\s*[-*>#\d.]+\s*/, '').trim())
    .filter(line => line.length > 8)
    .filter((line, index, arr) => arr.indexOf(line) === index);
}

function pick(lines, regex, max = 6) {
  return lines.filter(line => regex.test(line)).slice(0, max);
}

function bullets(items, fallback) {
  return items.length ? items.map(item => `- ${item}`).join('\n') : `- ${fallback}`;
}

function summarize(lines) {
  const useful = lines.filter(line => line.length < 320);
  const chosen = useful.slice(-8);
  if (!chosen.length) return 'No source context detected.';
  return chosen.map(line => `- ${line}`).join('\n');
}

function buildCapsule(text) {
  const lines = cleanLines(text);
  const decisions = pick(lines, patterns.decisions);
  const constraints = pick(lines, patterns.constraints);
  const actions = pick(lines, patterns.actions);
  const questions = pick(lines, patterns.questions);

  return `# Context Capsule\n\n## Working Context\n${summarize(lines)}\n\n## Decisions\n${bullets(decisions, 'No explicit decision detected — verify from the working context.')}\n\n## Constraints / Rules\n${bullets(constraints, 'No explicit constraints detected.')}\n\n## Next Actions\n${bullets(actions, 'Continue from the latest unresolved work in the working context.')}\n\n## Open Questions\n${bullets(questions, 'No explicit open question detected.')}\n\n## Continuity Instruction\nUse this capsule as the current project state. Preserve the decisions and constraints above, do not restart the problem from scratch, and continue with the next unresolved action. If something is ambiguous, prefer the most recent context above.`;
}

generateButton.addEventListener('click', () => {
  const text = source.value.trim();
  if (!text) {
    status.textContent = 'Paste a conversation first.';
    source.focus();
    return;
  }

  output.value = buildCapsule(text);
  copyButton.disabled = false;
  status.textContent = `Capsule generated locally from ${text.length.toLocaleString()} characters.`;
});

copyButton.addEventListener('click', async () => {
  if (!output.value) return;
  try {
    await navigator.clipboard.writeText(output.value);
    status.textContent = 'Copied. Paste it into your next AI session.';
  } catch {
    output.select();
    document.execCommand('copy');
    status.textContent = 'Copied. Paste it into your next AI session.';
  }
});
