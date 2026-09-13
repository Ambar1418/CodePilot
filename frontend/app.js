// CodePilot Web Application Logic
let token = localStorage.getItem('codepilot_token') || null;
let currentUser = null;
let activeChangeId = null;
let isAuthRegisterMode = false;
let pollingInterval = null;

document.addEventListener('DOMContentLoaded', () => {
  initAuth();
  setupEventListeners();
  loadChanges();
});

// ── Auth Handling ────────────────────────────────────────────────────────────

function initAuth() {
  if (token) {
    fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => {
      if (!res.ok) throw new Error('Token invalid');
      return res.json();
    })
    .then(user => {
      currentUser = user;
      updateAuthUI();
    })
    .catch(() => {
      logout();
    });
  } else {
    updateAuthUI();
  }
}

function updateAuthUI() {
  const userDisplay = document.getElementById('user-display');
  const authBtn = document.getElementById('auth-btn');
  if (currentUser) {
    userDisplay.textContent = currentUser.username;
    authBtn.textContent = 'Logout';
  } else {
    userDisplay.textContent = 'Guest';
    authBtn.textContent = 'Login';
  }
}

function openAuthModal() {
  document.getElementById('auth-modal').classList.remove('hidden');
}

function closeAuthModal() {
  document.getElementById('auth-modal').classList.add('hidden');
  document.getElementById('auth-error').classList.add('hidden');
}

function logout() {
  token = null;
  currentUser = null;
  localStorage.removeItem('codepilot_token');
  updateAuthUI();
  loadChanges();
}

// ── Event Listeners ──────────────────────────────────────────────────────────

function setupEventListeners() {
  document.getElementById('auth-btn').addEventListener('click', () => {
    if (currentUser) logout(); else openAuthModal();
  });

  document.getElementById('auth-toggle-btn').addEventListener('click', (e) => {
    e.preventDefault();
    isAuthRegisterMode = !isAuthRegisterMode;
    document.getElementById('auth-title').textContent = isAuthRegisterMode ? 'Register Account' : 'Login to CodePilot';
    document.getElementById('auth-submit-btn').textContent = isAuthRegisterMode ? 'Register' : 'Login';
    document.getElementById('email-group').classList.toggle('hidden', !isAuthRegisterMode);
    document.getElementById('auth-toggle-text').textContent = isAuthRegisterMode ? 'Already have an account?' : 'Need an account?';
    document.getElementById('auth-toggle-btn').textContent = isAuthRegisterMode ? 'Login' : 'Register';
  });

  document.getElementById('auth-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const username = document.getElementById('auth-username').value.trim();
    const password = document.getElementById('auth-password').value.trim();
    const email = document.getElementById('auth-email').value.trim();
    const errBox = document.getElementById('auth-error');
    errBox.classList.add('hidden');

    const endpoint = isAuthRegisterMode ? '/api/auth/register' : '/api/auth/login';
    const payload = isAuthRegisterMode ? { username, email, password } : { username, password };

    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(async res => {
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Authentication failed');
      return data;
    })
    .then(data => {
      if (isAuthRegisterMode) {
        // Automatically login after registration
        isAuthRegisterMode = false;
        document.getElementById('auth-form').dispatchEvent(new Event('submit'));
        return;
      }
      token = data.access_token;
      localStorage.setItem('codepilot_token', token);
      closeAuthModal();
      initAuth();
    })
    .catch(err => {
      errBox.textContent = err.message;
      errBox.classList.remove('hidden');
    });
  });

  // Task submission
  document.getElementById('task-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const repository_path = document.getElementById('repo-path').value.trim();
    const task = document.getElementById('task-desc').value.trim();
    const sandbox_type = document.getElementById('sandbox-type').value;

    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch('/api/orchestrate', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({ repository_path, task, sandbox_type })
    })
    .then(async res => {
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Orchestration failed');
      return data;
    })
    .then(data => {
      document.getElementById('task-desc').value = '';
      loadChanges();
      selectChange(data.change_id);
    })
    .catch(err => {
      alert(`Error starting task: ${err.message}`);
    });
  });

  document.getElementById('refresh-changes-btn').addEventListener('click', loadChanges);

  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });

  // Approval buttons
  document.getElementById('approve-btn').addEventListener('click', () => {
    if (!activeChangeId) return;
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`/api/changes/${activeChangeId}/approve`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({})
    })
    .then(async res => {
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Approval failed');
      return data;
    })
    .then(data => {
      alert(`Change approved & committed! Hash: ${data.commit_hash || 'N/A'}`);
      selectChange(activeChangeId);
      loadChanges();
    })
    .catch(err => {
      alert(`Approval error: ${err.message}`);
    });
  });

  document.getElementById('reject-btn').addEventListener('click', () => {
    if (!activeChangeId) return;
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`/api/changes/${activeChangeId}/reject`, {
      method: 'POST',
      headers: headers
    })
    .then(async res => {
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Rejection failed');
      return data;
    })
    .then(() => {
      alert('Change rejected and rolled back.');
      selectChange(activeChangeId);
      loadChanges();
    })
    .catch(err => {
      alert(`Rejection error: ${err.message}`);
    });
  });
}

// ── Dashboard & Changes ──────────────────────────────────────────────────────

function loadChanges() {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  fetch('/api/changes', { headers: headers })
  .then(res => res.json())
  .then(changes => {
    const tbody = document.getElementById('changes-table-body');
    if (!Array.isArray(changes) || changes.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No changes recorded yet. Submit a task above.</td></tr>';
      return;
    }
    tbody.innerHTML = changes.map(c => `
      <tr onclick="selectChange('${c.change_id}')" class="${activeChangeId === c.change_id ? 'active-row' : ''}">
        <td class="mono-id">${c.change_id.substring(0, 8)}...</td>
        <td>${c.files_changed && c.files_changed.length ? c.files_changed[0] : 'Task running...'}</td>
        <td><span class="badge badge-${c.status}">${c.status}</span></td>
        <td>${c.attempts}</td>
        <td>${c.files_changed ? c.files_changed.length : 0}</td>
        <td><button class="btn btn-sm btn-outline">View</button></td>
      </tr>
    `).join('');
  })
  .catch(() => {});
}

function selectChange(changeId) {
  activeChangeId = changeId;
  document.getElementById('change-detail-section').classList.remove('hidden');
  document.getElementById('detail-change-id').textContent = changeId;

  fetchChangeDetails(changeId);

  // Set up polling for active running tasks
  if (pollingInterval) clearInterval(pollingInterval);
  pollingInterval = setInterval(() => {
    fetchChangeDetails(changeId);
  }, 2500);
}

function fetchChangeDetails(changeId) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  fetch(`/api/changes/${changeId}`, { headers: headers })
  .then(res => res.json())
  .then(change => {
    updateChangeDetailUI(change);
    // Stop polling if change is terminal
    const terminalStates = ['READY_FOR_APPROVAL', 'COMMITTED', 'REJECTED', 'ROLLED_BACK', 'FAILED', 'CANCELLED'];
    if (terminalStates.includes(change.status) && pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  })
  .catch(() => {});

  // Fetch diff
  fetch(`/api/changes/${changeId}/diff`, { headers: headers })
  .then(res => res.json())
  .then(diffData => {
    renderDiff(diffData);
  })
  .catch(() => {
    document.getElementById('diff-code').textContent = 'No diff available.';
  });

  // Fetch audit logs
  fetch(`/api/changes/${changeId}/logs`, { headers: headers })
  .then(res => res.json())
  .then(logs => {
    renderAuditLogs(logs);
  })
  .catch(() => {});

  // Fetch impact analysis
  fetch(`/api/changes/${changeId}/impact`, { headers: headers })
  .then(res => res.json())
  .then(impact => {
    renderImpactAnalysis(impact);
  })
  .catch(() => {});
}

function renderImpactAnalysis(impact) {
  const riskBadge = document.getElementById('impact-risk-badge');
  if (riskBadge) {
    riskBadge.textContent = impact.risk_level;
    riskBadge.className = `badge badge-risk-${impact.risk_level}`;
  }
  const summaryText = document.getElementById('impact-summary-text');
  if (summaryText) {
    summaryText.textContent = impact.summary;
  }
  const filesBox = document.getElementById('impact-files-box');
  if (filesBox) {
    filesBox.textContent = `Directly Affected (${impact.files_changed_count}):\n` +
      (impact.directly_affected_files || []).join('\n') +
      `\n\nIndirectly Affected:\n` +
      (impact.indirectly_affected_files || []).join('\n');
  }
  const symbolsBox = document.getElementById('impact-symbols-box');
  if (symbolsBox) {
    symbolsBox.textContent = (impact.affected_symbols || []).join('\n') || 'None detected.';
  }
}

function updateChangeDetailUI(change) {
  const badge = document.getElementById('detail-status-badge');
  badge.textContent = change.status;
  badge.className = `badge badge-${change.status}`;

  // Update pipeline progress steps
  const steps = ['CREATED', 'PLANNING', 'SEARCHING', 'CODING', 'VALIDATING', 'READY_FOR_APPROVAL'];
  const currentIndex = steps.indexOf(change.status);
  steps.forEach((s, i) => {
    const el = document.getElementById(`step-${s}`);
    if (el) {
      el.classList.toggle('active', i <= currentIndex);
    }
  });

  // Validation output
  const valBox = document.getElementById('validation-output-box');
  if (change.validation) {
    valBox.innerHTML = `Exit code: ${change.validation.exit_code}\nPassed: ${change.validation.passed}\nDuration: ${change.validation.duration.toFixed(2)}s\n\nSTDOUT:\n${change.validation.stdout || '(none)'}\n\nSTDERR:\n${change.validation.stderr || '(none)'}`;
  } else {
    valBox.textContent = `Status: ${change.status}...`;
  }

  // Debug diagnosis
  const dbgBox = document.getElementById('debug-diagnosis-box');
  if (change.debug_history && change.debug_history.length > 0) {
    dbgBox.textContent = `Attempts: ${change.attempts}\nHistory: ${change.debug_history.length} failed attempt(s).`;
  } else {
    dbgBox.textContent = `Attempts: ${change.attempts}\nNo debug retries required.`;
  }

  // Show approval banner if state is READY_FOR_APPROVAL
  const appBanner = document.getElementById('approval-banner');
  appBanner.classList.toggle('hidden', change.status !== 'READY_FOR_APPROVAL');
}

function renderDiff(diffData) {
  document.getElementById('diff-stats-files').textContent = `${diffData.files_changed ? diffData.files_changed.length : 0} files changed`;
  document.getElementById('diff-stats-additions').textContent = `+${diffData.additions || 0}`;
  document.getElementById('diff-stats-deletions').textContent = `-${diffData.deletions || 0}`;

  const diffCode = document.getElementById('diff-code');
  if (!diffData.diff) {
    diffCode.textContent = 'No diff generated yet.';
    return;
  }

  const lines = diffData.diff.split('\n');
  diffCode.innerHTML = lines.map(line => {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      return `<span class="diff-added">${escapeHtml(line)}</span>`;
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      return `<span class="diff-deleted">${escapeHtml(line)}</span>`;
    }
    return escapeHtml(line);
  }).join('\n');
}

function renderAuditLogs(logs) {
  const tbody = document.getElementById('audit-logs-body');
  if (!Array.isArray(logs) || logs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-muted">No audit logs available.</td></tr>';
    return;
  }
  tbody.innerHTML = logs.map(l => `
    <tr>
      <td>${new Date(l.timestamp).toLocaleTimeString()}</td>
      <td><strong>${l.event_type}</strong></td>
      <td>${l.previous_state || '-'} &rarr; ${l.new_state || '-'}</td>
      <td>${l.attempt}</td>
      <td><span class="${l.success ? 'text-success' : 'text-danger'}">${l.success ? '✓ SUCCESS' : '✗ FAILED'}</span></td>
    </tr>
  `).join('');
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
