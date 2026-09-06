const workflowName = document.getElementById('workflowName');
const stepsInput = document.getElementById('steps');
const buildButton = document.getElementById('build');
const workspace = document.getElementById('workspace');
const stepCards = document.getElementById('stepCards');
const summary = document.getElementById('summary');
const exportBox = document.getElementById('export');
const copyButton = document.getElementById('copy');
const status = document.getElementById('status');
const cardTemplate = document.getElementById('cardTemplate');

let model = [];

function cleanSteps(value) {
  return value
    .split('\n')
    .map(step => step.trim())
    .filter(Boolean)
    .slice(0, 30);
}

function inferDefaults(text) {
  const t = text.toLowerCase();
  const write = /(send|publish|delete|approve|pay|purchase|update|edit|create|submit|book|deploy|refund|email|message|写|发送|删除|批准|支付|更新|提交|部署)/.test(t);
  const sensitive = /(salary|medical|health|password|credential|legal|contract|personal|customer data|payment|财务|医疗|密码|合同|个人|客户数据)/.test(t);
  const judgment = /(decide|assess|evaluate|negotiate|strategy|review|diagnose|approve|判断|评估|审核|策略|决定)/.test(t);
  const hard = /(send|publish|delete|pay|purchase|sign|approve|deploy|refund|发送|发布|删除|支付|签署|批准|部署)/.test(t);

  return {
    judgment: judgment ? 'high' : 'low',
    sensitivity: sensitive ? 'high' : 'low',
    access: write ? 'write' : 'none',
    reversibility: hard ? 'hard' : 'easy'
  };
}

function classify(step) {
  const highImpact = step.reversibility === 'hard' || step.access === 'write';

  if ((step.sensitivity === 'high' && highImpact) ||
      (step.access === 'write' && step.reversibility === 'hard') ||
      (step.judgment === 'high' && step.reversibility === 'hard')) {
    return {
      mode: 'Human-gated',
      className: 'human-gated',
      recommendation: 'Require explicit human approval before execution.',
      controls: 'Keep an audit trail, preview the action, and make ownership clear before the step can change an external system.'
    };
  }

  if (step.judgment === 'high' || step.sensitivity === 'high' || step.access === 'read') {
    return {
      mode: 'Copilot',
      className: 'copilot',
      recommendation: 'Let AI prepare or recommend; keep a human responsible for the decision.',
      controls: 'Constrain data access, show the evidence used, and require a person to accept or revise the result.'
    };
  }

  return {
    mode: 'Agent-ready',
    className: 'agent-ready',
    recommendation: 'Good candidate for bounded autonomous execution.',
    controls: 'Define success criteria, timeout/failure handling, and a safe retry or rollback path.'
  };
}

function render() {
  stepCards.innerHTML = '';

  model.forEach((step, index) => {
    const node = cardTemplate.content.cloneNode(true);
    const card = node.querySelector('.card');
    const result = classify(step);

    node.querySelector('.step-number').textContent = index + 1;
    node.querySelector('.step-title').textContent = step.text;

    const badge = node.querySelector('.badge');
    badge.textContent = result.mode;
    badge.className = `badge ${result.className}`;

    node.querySelector('.recommendation').textContent = result.recommendation;
    node.querySelector('.controls').textContent = result.controls;

    node.querySelectorAll('select').forEach(select => {
      const field = select.dataset.field;
      select.value = step[field];
      select.addEventListener('change', event => {
        model[index][field] = event.target.value;
        render();
      });
    });

    stepCards.appendChild(node);
  });

  renderSummary();
  renderExport();
}

function renderSummary() {
  const counts = { 'Agent-ready': 0, Copilot: 0, 'Human-gated': 0 };
  model.forEach(step => counts[classify(step).mode] += 1);
  summary.innerHTML = `
    <span>${counts['Agent-ready']} Agent-ready</span>
    <span>${counts.Copilot} Copilot</span>
    <span>${counts['Human-gated']} Human-gated</span>
  `;
}

function renderExport() {
  const name = workflowName.value.trim() || 'Untitled workflow';
  const lines = [`# Agent Readiness Map — ${name}`, '', 'Generated with Agent Ready Map.', ''];

  model.forEach((step, index) => {
    const result = classify(step);
    lines.push(`## ${index + 1}. ${step.text}`);
    lines.push(`- Operating mode: **${result.mode}**`);
    lines.push(`- Judgment: ${step.judgment}`);
    lines.push(`- Data sensitivity: ${step.sensitivity}`);
    lines.push(`- System access: ${step.access}`);
    lines.push(`- Reversibility: ${step.reversibility}`);
    lines.push(`- Recommendation: ${result.recommendation}`);
    lines.push(`- Controls: ${result.controls}`);
    lines.push('');
  });

  lines.push('> This is a workflow-design aid, not a security or compliance certification.');
  exportBox.value = lines.join('\n');
}

buildButton.addEventListener('click', () => {
  const steps = cleanSteps(stepsInput.value);
  if (!steps.length) {
    stepsInput.focus();
    return;
  }

  model = steps.map(text => ({ text, ...inferDefaults(text) }));
  workspace.classList.remove('hidden');
  render();
  workspace.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

workflowName.addEventListener('input', () => {
  if (model.length) renderExport();
});

copyButton.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(exportBox.value);
    status.textContent = 'Copied. Share the map with the people who own this workflow.';
  } catch {
    exportBox.select();
    document.execCommand('copy');
    status.textContent = 'Copied.';
  }
});
