/**
 * VARTA Research Assistant — Frontend Client Application
 * Communicates with FastAPI REST API endpoints:
 * - POST /session (Create session)
 * - DELETE /session/{id} (Close session)
 * - POST /chat (Send inquiry with session tracking)
 * - GET /health (Health check)
 */

(function () {
  'use strict';

  // Application State
  const state = {
    sessionId: null,
    turnCount: 0,
    isProcessing: false,
    activeReviewRegion: 'active',
    selectedDatasets: [], // [] means all datasets; ['sagar_reddit_dataset'] means scoped
    availableDatasets: [], // list of dataset items from /datasets/list
    messages: [] // { role: 'user' | 'assistant', text: '', citations: [], timestamp: '' }
  };

  // DOM Elements
  const elements = {
    sessionDisplay: document.getElementById('active-session-display'),
    turnCountBadge: document.getElementById('turn-count-badge'),
    btnUploadDataset: document.getElementById('btn-upload-dataset'),
    datasetFileInput: document.getElementById('dataset-file-input'),
    // Dataset Picker Elements
    datasetPickerContainer: document.getElementById('dataset-picker-container'),
    datasetChipsList: document.getElementById('dataset-chips-list'),
    chipAllDatasets: document.getElementById('chip-all-datasets'),
    chipAllCount: document.getElementById('chip-all-count'),
    datasetPickerStatus: document.getElementById('dataset-picker-status'),
    btnNewChat: document.getElementById('btn-new-chat'),
    btnExportChat: document.getElementById('btn-export-chat'),
    messagesContainer: document.getElementById('messages-container'),
    welcomeCard: document.getElementById('welcome-card'),
    loadingIndicator: document.getElementById('loading-indicator'),
    chatForm: document.getElementById('chat-form'),
    messageInput: document.getElementById('message-input'),
    btnSend: document.getElementById('btn-send'),
    errorToast: document.getElementById('error-toast'),
    toastTitle: document.getElementById('toast-title'),
    toastMessage: document.getElementById('toast-message'),
    toastClose: document.getElementById('toast-close'),
    successToast: document.getElementById('success-toast'),
    successToastTitle: document.getElementById('success-toast-title'),
    successToastMessage: document.getElementById('success-toast-message'),
    successToastClose: document.getElementById('success-toast-close'),
    uploadModal: document.getElementById('upload-modal'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    btnModalDismiss: document.getElementById('btn-modal-dismiss'),
    uploadFilenameBadge: document.getElementById('upload-filename-badge'),
    uploadFilenameText: document.getElementById('upload-filename-text'),
    stepUploading: document.getElementById('step-uploading'),
    stepProcessing: document.getElementById('step-processing'),
    stepIndexing: document.getElementById('step-indexing'),
    stepReady: document.getElementById('step-ready'),
    uploadStatusBox: document.getElementById('upload-status-box'),
    uploadStatusIcon: document.getElementById('upload-status-icon'),
    uploadStatusMsg: document.getElementById('upload-status-msg'),
    modalFooter: document.getElementById('modal-footer'),
    sampleChips: document.querySelectorAll('.sample-chip'),
    // Preprocessing Review Modal Elements
    btnReviewQueue: document.getElementById('btn-review-queue'),
    reviewPendingBadge: document.getElementById('review-pending-badge'),
    reviewModal: document.getElementById('review-modal'),
    btnCloseReviewModal: document.getElementById('btn-close-review-modal'),
    btnReviewDone: document.getElementById('btn-review-done'),
    reviewProgressText: document.getElementById('review-progress-text'),
    reviewProgressFill: document.getElementById('review-progress-fill'),
    reviewRecordsList: document.getElementById('review-records-list'),
    statKeepCount: document.getElementById('stat-keep-count'),
    statExcludeCount: document.getElementById('stat-exclude-count'),
    statPendingCount: document.getElementById('stat-pending-count'),
    reviewSummaryStat: document.getElementById('review-summary-stat'),
    reviewActiveContextTag: document.getElementById('review-active-context-tag'),
    reviewDatasetHealthTag: document.getElementById('review-dataset-health-tag'),
    reviewHealthSubtext: document.getElementById('review-health-subtext'),
    auditMasterCount: document.getElementById('audit-master-count'),
    auditKeptCount: document.getElementById('audit-kept-count'),
    auditExcludedCount: document.getElementById('audit-excluded-count'),
    auditBorderlineCount: document.getElementById('audit-borderline-count'),
    reviewAuditSummaryMsg: document.getElementById('review-audit-summary-msg'),
    preprocessingStagesList: document.getElementById('preprocessing-stages-list'),
    regionFilterChips: document.querySelectorAll('.region-chip')
  };

  // ========================================================================
  // Initialization & Session Management
  // ========================================================================

  async function initApp() {
    setupEventListeners();
    await createNewSession();
    await updateReviewBadge();
    await loadAvailableDatasets();
  }

  async function createNewSession() {
    try {
      showLoading(true, 'Initializing research session...');
      const response = await fetch('/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        throw new Error(`Failed to initialize session (HTTP ${response.status})`);
      }

      const data = await response.json();
      state.sessionId = data.session_id;
      state.turnCount = 0;
      state.messages = [];

      updateSessionUI();
      clearMessagesStream();
    } catch (err) {
      showToast('Session Error', err.message || 'Unable to connect to backend server.');
    } finally {
      showLoading(false);
    }
  }

  async function endCurrentSession() {
    if (!state.sessionId) return;
    try {
      await fetch(`/session/${state.sessionId}`, { method: 'DELETE' });
    } catch (err) {
      console.warn('Error closing session:', err);
    }
  }

  function updateSessionUI() {
    if (elements.sessionDisplay) {
      elements.sessionDisplay.textContent = state.sessionId || 'Not Connected';
    }
    if (elements.turnCountBadge) {
      elements.turnCountBadge.textContent = `${state.turnCount} turn${state.turnCount === 1 ? '' : 's'}`;
    }
  }

  function clearMessagesStream() {
    if (!elements.messagesContainer) return;
    elements.messagesContainer.innerHTML = '';
    if (elements.welcomeCard) {
      elements.messagesContainer.appendChild(elements.welcomeCard);
      elements.welcomeCard.style.display = 'block';
    }
  }

  // ========================================================================
  // Event Listeners
  // ========================================================================

  function setupEventListeners() {
    // Dataset Upload Button & File Input
    if (elements.btnUploadDataset && elements.datasetFileInput) {
      elements.btnUploadDataset.addEventListener('click', () => {
        elements.datasetFileInput.click();
      });
      elements.datasetFileInput.addEventListener('change', handleDatasetUpload);
    }

    // Modal Close Buttons
    if (elements.btnCloseModal) {
      elements.btnCloseModal.addEventListener('click', closeUploadModal);
    }
    if (elements.btnModalDismiss) {
      elements.btnModalDismiss.addEventListener('click', closeUploadModal);
    }
    if (elements.uploadModal) {
      elements.uploadModal.addEventListener('click', (e) => {
        if (e.target === elements.uploadModal) closeUploadModal();
      });
    }

    // Form Submit
    if (elements.chatForm) {
      elements.chatForm.addEventListener('submit', handleFormSubmit);
    }

    // Textarea Auto-resize and Enter key shortcut
    if (elements.messageInput) {
      elements.messageInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          if (elements.chatForm) {
            elements.chatForm.requestSubmit();
          }
        }
      });

      elements.messageInput.addEventListener('input', autoResizeTextarea);
    }

    // New Chat Button
    if (elements.btnNewChat) {
      elements.btnNewChat.addEventListener('click', async function () {
        if (state.isProcessing) return;
        await endCurrentSession();
        await createNewSession();
        showToast('New Session', 'Started a clean research session.', 'info');
      });
    }

    // Export Chat Button
    if (elements.btnExportChat) {
      elements.btnExportChat.addEventListener('click', exportConversationTranscript);
    }

    // Preprocessing Review Queue Modal Triggers
    if (elements.btnReviewQueue) {
      elements.btnReviewQueue.addEventListener('click', openReviewModal);
    }
    if (elements.btnCloseReviewModal) {
      elements.btnCloseReviewModal.addEventListener('click', closeReviewModal);
    }
    if (elements.btnReviewDone) {
      elements.btnReviewDone.addEventListener('click', closeReviewModal);
    }
    if (elements.reviewModal) {
      elements.reviewModal.addEventListener('click', (e) => {
        if (e.target === elements.reviewModal) closeReviewModal();
      });
    }

    // Toast Close Buttons
    if (elements.toastClose) {
      elements.toastClose.addEventListener('click', hideToast);
    }
    if (elements.successToastClose) {
      elements.successToastClose.addEventListener('click', hideSuccessToast);
    }

    // Sample Query Chips
    elements.sampleChips.forEach((chip) => {
      chip.addEventListener('click', function () {
        const queryText = this.getAttribute('data-query');
        if (queryText && elements.messageInput && !state.isProcessing) {
          elements.messageInput.value = queryText;
          autoResizeTextarea();
          if (elements.chatForm) {
            elements.chatForm.requestSubmit();
          }
        }
      });
    });

    // Dataset / Region Filter Chips inside Review Modal
    if (elements.regionFilterChips) {
      elements.regionFilterChips.forEach((chip) => {
        chip.addEventListener('click', async function () {
          elements.regionFilterChips.forEach((c) => c.classList.remove('active'));
          this.classList.add('active');
          state.activeReviewRegion = this.getAttribute('data-region') || 'active';
          await fetchAndRenderReviewQueue();
        });
      });
    }
  }

  // ========================================================================
  // Dataset Knowledge Scoping Picker
  // ========================================================================

  async function loadAvailableDatasets() {
    try {
      const response = await fetch('/datasets/list');
      if (!response.ok) return;
      const data = await response.json();
      state.availableDatasets = data.datasets || [];
      renderDatasetChips(data);
    } catch (err) {
      console.warn('Unable to load dataset list:', err);
    }
  }

  function renderDatasetChips(data) {
    if (!elements.datasetChipsList) return;
    const datasets = data.datasets || [];
    const totalChunks = data.total_chunks || 0;

    if (elements.chipAllCount) {
      elements.chipAllCount.textContent = totalChunks.toLocaleString();
    }

    elements.datasetChipsList.innerHTML = '';
    
    // 1. "All Datasets" chip
    const isAllActive = !state.selectedDatasets || state.selectedDatasets.length === 0;
    const allChip = document.createElement('button');
    allChip.type = 'button';
    allChip.className = `dataset-picker-chip ${isAllActive ? 'active' : ''}`;
    allChip.id = 'chip-all-datasets';
    allChip.title = 'Search across all indexed datasets';
    allChip.innerHTML = `
      <span class="chip-check">✓</span>
      <span class="chip-title">All Datasets</span>
      <span class="chip-count">${totalChunks.toLocaleString()}</span>
    `;
    allChip.addEventListener('click', () => {
      state.selectedDatasets = [];
      updateDatasetChipsUI();
    });
    elements.datasetChipsList.appendChild(allChip);

    // 2. Individual dataset chips
    datasets.forEach(ds => {
      const isSelected = state.selectedDatasets.includes(ds.source_dataset);
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = `dataset-picker-chip chip-dataset-scoped ${isSelected ? 'active' : ''}`;
      chip.setAttribute('data-dataset', ds.source_dataset);
      chip.title = `Filter retrieval to '${ds.display_name}' (${ds.chunk_count.toLocaleString()} chunks)`;
      chip.innerHTML = `
        <span class="chip-check">✓</span>
        <span class="chip-title">${escapeHTML(ds.display_name)}</span>
        <span class="chip-count">${ds.chunk_count.toLocaleString()}</span>
      `;
      chip.addEventListener('click', () => {
        toggleDatasetSelection(ds.source_dataset);
      });
      elements.datasetChipsList.appendChild(chip);
    });

    updateDatasetStatusText();
  }

  function toggleDatasetSelection(sourceDataset) {
    const idx = state.selectedDatasets.indexOf(sourceDataset);
    if (idx >= 0) {
      state.selectedDatasets.splice(idx, 1);
    } else {
      state.selectedDatasets.push(sourceDataset);
    }
    updateDatasetChipsUI();
  }

  function updateDatasetChipsUI() {
    if (!elements.datasetChipsList) return;
    const isAll = state.selectedDatasets.length === 0;

    const allChip = elements.datasetChipsList.querySelector('#chip-all-datasets');
    if (allChip) {
      if (isAll) {
        allChip.classList.add('active');
      } else {
        allChip.classList.remove('active');
      }
    }

    const scopedChips = elements.datasetChipsList.querySelectorAll('.chip-dataset-scoped');
    scopedChips.forEach(chip => {
      const ds = chip.getAttribute('data-dataset');
      if (state.selectedDatasets.includes(ds)) {
        chip.classList.add('active');
      } else {
        chip.classList.remove('active');
      }
    });

    updateDatasetStatusText();
  }

  function updateDatasetStatusText() {
    if (!elements.datasetPickerStatus) return;
    if (state.selectedDatasets.length === 0) {
      elements.datasetPickerStatus.textContent = 'Searching across all datasets';
      elements.datasetPickerStatus.style.color = 'var(--text-subtle)';
    } else if (state.selectedDatasets.length === 1) {
      const match = state.availableDatasets.find(d => d.source_dataset === state.selectedDatasets[0]);
      const name = match ? match.display_name : state.selectedDatasets[0];
      elements.datasetPickerStatus.textContent = `Scoped to: ${name}`;
      elements.datasetPickerStatus.style.color = 'var(--accent-primary)';
    } else {
      elements.datasetPickerStatus.textContent = `Scoped to ${state.selectedDatasets.length} datasets`;
      elements.datasetPickerStatus.style.color = 'var(--accent-primary)';
    }
  }

  function autoResizeTextarea() {
    if (!elements.messageInput) return;
    elements.messageInput.style.height = 'auto';
    const newHeight = Math.min(elements.messageInput.scrollHeight, 160);
    elements.messageInput.style.height = `${newHeight}px`;
  }

  // ========================================================================
  // Chat Message Dispatch & Handling
  // ========================================================================

  async function handleFormSubmit(e) {
    e.preventDefault();
    if (state.isProcessing) return;

    const messageText = elements.messageInput.value.trim();
    if (!messageText) return;

    // Reset textarea
    elements.messageInput.value = '';
    autoResizeTextarea();

    // Hide welcome card if present
    if (elements.welcomeCard && elements.welcomeCard.parentNode) {
      elements.welcomeCard.style.display = 'none';
    }

    // Append user message bubble
    appendUserMessage(messageText);

    // Set processing state
    state.isProcessing = true;
    showLoading(true, 'Synthesizing evidence and consulting sources...');
    setComposerDisabled(true);

    try {
      const payload = {
        message: messageText,
        session_id: state.sessionId,
        dataset_filter: state.selectedDatasets && state.selectedDatasets.length > 0 ? state.selectedDatasets : null
      };

      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        let errorDetail = `Server returned status ${response.status}`;
        try {
          const errJson = await response.json();
          if (errJson.detail) errorDetail = errJson.detail;
        } catch (_) {}
        throw new Error(errorDetail);
      }

      const data = await response.json();

      // Sync Session ID if newly assigned
      if (data.session_id) {
        state.sessionId = data.session_id;
      }
      state.turnCount += 1;
      updateSessionUI();

      // Append assistant answer
      appendAssistantMessage(data.answer, data.citations || []);

      // Record in local state for export
      state.messages.push({
        role: 'user',
        text: messageText,
        timestamp: new Date().toISOString()
      });
      state.messages.push({
        role: 'assistant',
        text: data.answer,
        citations: data.citations || [],
        timestamp: new Date().toISOString()
      });

    } catch (err) {
      console.error('Chat error:', err);
      showToast('Inquiry Failed', err.message || 'Error communicating with assistant.');
      appendErrorMessage(`Unable to complete inquiry: ${err.message}`);
    } finally {
      state.isProcessing = false;
      showLoading(false);
      setComposerDisabled(false);
      if (elements.messageInput) {
        elements.messageInput.focus();
      }
      updateReviewBadge();
    }
  }

  // ========================================================================
  // DOM Message Rendering
  // ========================================================================

  function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user-row';

    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message-content-wrapper';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble user-bubble';
    bubble.textContent = text;

    contentWrapper.appendChild(bubble);

    const avatar = document.createElement('div');
    avatar.className = 'avatar avatar-user';
    avatar.textContent = 'You';

    row.appendChild(contentWrapper);
    row.appendChild(avatar);

    elements.messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function appendAssistantMessage(answerText, citations) {
    const row = document.createElement('div');
    row.className = 'message-row assistant-row';

    const avatar = document.createElement('div');
    avatar.className = 'avatar avatar-assistant';
    avatar.textContent = 'V';

    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message-content-wrapper';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble assistant-bubble';
    bubble.innerHTML = formatAssistantText(answerText);

    contentWrapper.appendChild(bubble);

    // Citations Drawer (if citations available)
    if (citations && citations.length > 0) {
      const citationsContainer = buildCitationsSection(citations);
      contentWrapper.appendChild(citationsContainer);
    }

    row.appendChild(avatar);
    row.appendChild(contentWrapper);

    elements.messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function appendErrorMessage(errorMsg) {
    const row = document.createElement('div');
    row.className = 'message-row assistant-row';

    const avatar = document.createElement('div');
    avatar.className = 'avatar avatar-assistant';
    avatar.style.background = '#ef4444';
    avatar.textContent = '!';

    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message-content-wrapper';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble assistant-bubble';
    bubble.style.borderColor = 'rgba(239, 68, 68, 0.4)';
    bubble.innerHTML = `<span style="color: #f87171; font-weight: 500;">⚠️ ${escapeHTML(errorMsg)}</span>`;

    contentWrapper.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(contentWrapper);

    elements.messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function formatAssistantText(rawText) {
    if (!rawText) return '<p>No response content generated.</p>';

    // Escape raw HTML first
    let text = escapeHTML(rawText);

    // Format markdown bold: **text**
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Format inline citation tags: [Doc 1], [Doc 2]
    text = text.replace(/\[Doc\s+(\d+)\]/g, '<span class="citation-inline-badge">[Doc $1]</span>');

    // Split paragraphs and lists
    const lines = text.split('\n');
    const htmlParts = [];
    let inList = false;

    for (let line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        if (inList) { htmlParts.push('</ul>'); inList = false; }
        continue;
      }

      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (!inList) { htmlParts.push('<ul>'); inList = true; }
        htmlParts.push(`<li>${trimmed.substring(2)}</li>`);
      } else if (trimmed.startsWith('### ') || trimmed.startsWith('#### ')) {
        if (inList) { htmlParts.push('</ul>'); inList = false; }
        htmlParts.push(`<p><strong>${trimmed.replace(/^#+\s*/, '')}</strong></p>`);
      } else {
        if (inList) { htmlParts.push('</ul>'); inList = false; }
        htmlParts.push(`<p>${trimmed}</p>`);
      }
    }

    if (inList) htmlParts.push('</ul>');
    return htmlParts.join('');
  }

  function buildCitationsSection(citations) {
    const container = document.createElement('div');
    container.className = 'citations-container';

    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'citations-toggle';
    toggleBtn.innerHTML = `<span>📚 Referenced Sources (${citations.length})</span>`;

    const list = document.createElement('div');
    list.className = 'citations-list';

    citations.forEach((cit, idx) => {
      const card = document.createElement('div');
      card.className = 'citation-card';

      const citId = cit.citation_id || `[Doc ${idx + 1}]`;
      const title = cit.title || 'Document Record';
      const sourceType = cit.source_type || 'Archive';
      const docId = cit.doc_id || cit.parent_doc_id || '';
      const sourceUrl = cit.source_url || (docId && (docId.startsWith('http://') || docId.startsWith('https://')) ? docId : null);

      let linkHtml = '';
      if (sourceUrl && (sourceUrl.startsWith('http://') || sourceUrl.startsWith('https://'))) {
        const cleanUrl = sourceUrl.replace(/\.\d+$/, '');
        linkHtml = `<a href="${escapeHTML(cleanUrl)}" target="_blank" rel="noopener noreferrer" class="citation-source-link" title="${escapeHTML(cleanUrl)}">Source URL ↗</a>`;
      } else if (docId) {
        linkHtml = `<span class="citation-source-link">Doc ID: ${escapeHTML(docId)}</span>`;
      }

      card.innerHTML = `
        <div class="citation-header">
          <span class="citation-badge">${escapeHTML(citId)}</span>
          <span class="citation-type">${escapeHTML(sourceType)}</span>
        </div>
        <div class="citation-title">${escapeHTML(title)}</div>
        ${linkHtml}
      `;

      list.appendChild(card);
    });

    container.appendChild(toggleBtn);
    container.appendChild(list);

    toggleBtn.addEventListener('click', () => {
      const isHidden = list.style.display === 'none';
      list.style.display = isHidden ? 'flex' : 'none';
    });

    return container;
  }

  function escapeHTML(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function scrollToBottom() {
    if (elements.messagesContainer) {
      elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    }
  }

  function showLoading(show, statusText) {
    if (elements.loadingIndicator) {
      elements.loadingIndicator.style.display = show ? 'flex' : 'none';
      if (statusText) {
        const textEl = elements.loadingIndicator.querySelector('.loading-text');
        if (textEl) textEl.textContent = statusText;
      }
    }
    if (show) scrollToBottom();
  }

  function setComposerDisabled(disabled) {
    if (elements.messageInput) elements.messageInput.disabled = disabled;
    if (elements.btnSend) elements.btnSend.disabled = disabled;
  }

  function showToast(title, message) {
    if (!elements.errorToast) return;
    elements.toastTitle.textContent = title;
    elements.toastMessage.textContent = message;
    elements.errorToast.style.display = 'flex';

    setTimeout(() => {
      hideToast();
    }, 6000);
  }

  function hideToast() {
    if (elements.errorToast) {
      elements.errorToast.style.display = 'none';
    }
  }

  function showSuccessToast(title, message) {
    if (!elements.successToast) return;
    elements.successToastTitle.textContent = title;
    elements.successToastMessage.textContent = message;
    elements.successToast.style.display = 'flex';

    setTimeout(() => {
      hideSuccessToast();
    }, 7000);
  }

  function hideSuccessToast() {
    if (elements.successToast) {
      elements.successToast.style.display = 'none';
    }
  }

  // ========================================================================
  // Dataset Upload & Ingestion Pipeline UI Flow
  // ========================================================================

  function openUploadModal(filename) {
    if (elements.uploadFilenameText) {
      elements.uploadFilenameText.textContent = filename;
    }
    if (elements.uploadStatusBox) {
      elements.uploadStatusBox.style.display = 'none';
    }
    if (elements.modalFooter) {
      elements.modalFooter.style.display = 'none';
    }
    if (elements.uploadModal) {
      elements.uploadModal.style.display = 'flex';
    }
  }

  function closeUploadModal() {
    if (elements.uploadModal) {
      elements.uploadModal.style.display = 'none';
    }
  }

  function setStepState(stepEl, status) {
    if (!stepEl) return;
    stepEl.classList.remove('active', 'completed', 'failed');
    const bullet = stepEl.querySelector('.step-bullet');
    if (bullet) {
      bullet.innerHTML = '';
      if (status === 'active') {
        stepEl.classList.add('active');
        const spinner = document.createElement('span');
        spinner.className = 'step-spinner';
        bullet.appendChild(spinner);
      } else if (status === 'completed') {
        stepEl.classList.add('completed');
      } else if (status === 'failed') {
        stepEl.classList.add('failed');
      } else {
        // Pending
        const dot = document.createElement('span');
        dot.className = 'step-dot';
        bullet.appendChild(dot);
      }
    }
  }

  async function handleDatasetUpload(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    const validExtensions = ['.csv', '.json', '.jsonl'];
    const fileName = file.name || 'dataset';
    const fileExt = fileName.substring(fileName.lastIndexOf('.')).toLowerCase();

    if (!validExtensions.includes(fileExt)) {
      showToast('Invalid File Type', `File '${fileName}' is not supported. Please upload a .csv, .json, or .jsonl dataset file.`);
      elements.datasetFileInput.value = '';
      return;
    }

    openUploadModal(fileName);
    setStepState(elements.stepUploading, 'active');
    setStepState(elements.stepProcessing, 'pending');
    setStepState(elements.stepIndexing, 'pending');
    setStepState(elements.stepReady, 'pending');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/dataset/upload', {
        method: 'POST',
        body: formData
      });

      let data = {};
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        try {
          data = await response.json();
        } catch (_) {}
      }

      if (!response.ok) {
        const rawText = !contentType.includes('application/json') ? await response.text().catch(() => '') : '';
        const errorDetail = data.detail || rawText || `Dataset upload failed with status ${response.status}`;
        throw new Error(errorDetail);
      }

      // Step 1: Upload Complete -> Step 2: Processing Active
      setStepState(elements.stepUploading, 'completed');
      setStepState(elements.stepProcessing, 'active');

      // Poll /dataset/status until background ingestion completes
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch('/dataset/status');
          if (!statusRes.ok) return;
          const statusData = await statusRes.json();

          if (statusData.status === 'processing') {
            if (statusData.current_batch > 0) {
              setStepState(elements.stepProcessing, 'completed');
              setStepState(elements.stepIndexing, 'active');
            }
            if (elements.uploadStatusBox) {
              elements.uploadStatusBox.className = 'upload-status-box';
              elements.uploadStatusIcon.textContent = '⏳';
              elements.uploadStatusMsg.textContent = statusData.message || `Processing batch ${statusData.current_batch}...`;
              elements.uploadStatusBox.style.display = 'flex';
            }
          } else if (statusData.status === 'ready') {
            clearInterval(pollInterval);
            setStepState(elements.stepProcessing, 'completed');
            setStepState(elements.stepIndexing, 'completed');
            setStepState(elements.stepReady, 'completed');

            if (elements.uploadStatusBox) {
              elements.uploadStatusBox.className = 'upload-status-box';
              elements.uploadStatusIcon.textContent = '✅';
              elements.uploadStatusMsg.textContent = statusData.message || `Successfully ingested ${statusData.documents_ingested} documents. Ready for research queries.`;
              elements.uploadStatusBox.style.display = 'flex';
            }

            if (elements.modalFooter) {
              elements.modalFooter.style.display = 'flex';
            }

            showSuccessToast(
              'Dataset Ingested & Queryable',
              `${statusData.documents_ingested.toLocaleString()} documents (${statusData.chunks_indexed.toLocaleString()} chunks) added. Total corpus: ${statusData.total_vectors_available.toLocaleString()} vectors.`
            );
            loadAvailableDatasets();
          } else if (statusData.status === 'failed') {
            clearInterval(pollInterval);
            throw new Error(statusData.error || statusData.message || 'Background dataset ingestion failed.');
          }
        } catch (pollErr) {
          clearInterval(pollInterval);
          setStepState(elements.stepProcessing, 'failed');
          setStepState(elements.stepIndexing, 'failed');
          setStepState(elements.stepReady, 'failed');

          if (elements.uploadStatusBox) {
            elements.uploadStatusBox.className = 'upload-status-box error';
            elements.uploadStatusIcon.textContent = '❌';
            elements.uploadStatusMsg.textContent = pollErr.message || 'Dataset processing encountered an issue.';
            elements.uploadStatusBox.style.display = 'flex';
          }

          if (elements.modalFooter) {
            elements.modalFooter.style.display = 'flex';
          }
        }
      }, 1500);

    } catch (err) {
      setStepState(elements.stepUploading, 'completed');
      setStepState(elements.stepProcessing, 'failed');
      setStepState(elements.stepIndexing, 'failed');
      setStepState(elements.stepReady, 'failed');

      if (elements.uploadStatusBox) {
        elements.uploadStatusBox.className = 'upload-status-box error';
        elements.uploadStatusIcon.textContent = '❌';
        elements.uploadStatusMsg.textContent = err.message || 'Dataset processing encountered an issue.';
        elements.uploadStatusBox.style.display = 'flex';
      }

      if (elements.modalFooter) {
        elements.modalFooter.style.display = 'flex';
      }

      showToast('Ingestion Error', err.message);
    } finally {
      elements.datasetFileInput.value = '';
    }
  }

  function exportConversationTranscript() {
    if (!state.messages || state.messages.length === 0) {
      showToast('Export Notice', 'No conversation history in current session to export.');
      return;
    }

    const lines = [
      `# VARTA Research Session Transcript`,
      `**Session ID**: \`${state.sessionId}\``,
      `**Export Date**: ${new Date().toUTCString()}`,
      `**Total Exchanges**: ${state.turnCount}`,
      `\n---\n`
    ];

    state.messages.forEach((msg, idx) => {
      if (msg.role === 'user') {
        lines.push(`### Turn ${Math.floor(idx / 2) + 1} — Researcher`);
        lines.push(`> ${msg.text}\n`);
      } else {
        lines.push(`### VARTA Response`);
        lines.push(`${msg.text}\n`);
        if (msg.citations && msg.citations.length > 0) {
          lines.push(`**Citations & Sources:**`);
          msg.citations.forEach((c) => {
            lines.push(`- **${c.citation_id || '[Doc]'}**: *${c.title || 'Untitled'}* (${c.source_type || 'Doc'}) — \`${c.parent_doc_id || 'N/A'}\``);
          });
          lines.push('');
        }
        lines.push('---\n');
      }
    });

    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `varta_research_session_${state.sessionId || 'log'}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('Export Success', 'Conversation transcript downloaded as Markdown.');
  }

  // ========================================================================
  // Sagar Preprocessing Review Queue Handlers
  // ========================================================================

  async function updateReviewBadge() {
    try {
      const url = state.sessionId ? `/review/records?session_id=${encodeURIComponent(state.sessionId)}` : '/review/records';
      const resp = await fetch(url);
      if (resp.ok) {
        const data = await resp.json();
        if (elements.reviewPendingBadge) {
          if (data.pending_count > 0) {
            elements.reviewPendingBadge.textContent = data.pending_count;
            elements.reviewPendingBadge.style.display = 'inline-flex';
          } else {
            elements.reviewPendingBadge.style.display = 'none';
          }
        }
      }
    } catch (err) {
      console.warn('Could not fetch review queue badge count:', err);
    }
  }

  async function openReviewModal() {
    if (!elements.reviewModal) return;
    elements.reviewModal.style.display = 'flex';
    await fetchAndRenderReviewQueue();
  }

  function closeReviewModal() {
    if (!elements.reviewModal) return;
    elements.reviewModal.style.display = 'none';
    updateReviewBadge();
  }

  async function fetchAndRenderReviewQueue() {
    if (!elements.reviewRecordsList) return;
    elements.reviewRecordsList.innerHTML = '<div class="review-loading-state" style="padding: 24px; text-align: center; color: var(--text-muted);"><span>Loading review queue & dataset health...</span></div>';
    
    try {
      let url = '/review/records';
      if (state.activeReviewRegion === 'active') {
        url = state.sessionId ? `/review/records?session_id=${encodeURIComponent(state.sessionId)}` : '/review/records';
      } else if (state.activeReviewRegion === 'all') {
        url = '/review/records?region=all%20corpus';
      } else {
        url = `/review/records?region=${encodeURIComponent(state.activeReviewRegion)}`;
      }

      const resp = await fetch(url);
      if (!resp.ok) {
        throw new Error(`Failed to load review records (HTTP ${resp.status})`);
      }
      const data = await resp.json();
      renderReviewQueueData(data);
    } catch (err) {
      elements.reviewRecordsList.innerHTML = `<div class="review-loading-state" style="padding: 24px; text-align: center; color: var(--accent-danger);"><span>Failed to load review records: ${err.message}</span></div>`;
    }
  }

  function renderReviewQueueData(data) {
    const total = data.total_records || 0;
    const reviewed = data.reviewed_count || 0;
    const pending = data.pending_count || 0;
    const keep = data.keep_count || 0;
    const exclude = data.exclude_count || 0;

    // Update Active Context Badge
    if (elements.reviewActiveContextTag) {
      elements.reviewActiveContextTag.textContent = data.context_topic || 'Master Corpus (Global)';
    }

    // Update Dataset Health and Preprocessing Transformation Summary
    if (data.audit_stats) {
      const ast = data.audit_stats;
      if (elements.auditMasterCount) elements.auditMasterCount.textContent = (ast.total_master_records || 0).toLocaleString();
      if (elements.auditKeptCount) elements.auditKeptCount.textContent = (ast.auto_kept_count || 0).toLocaleString();
      if (elements.auditExcludedCount) elements.auditExcludedCount.textContent = (ast.auto_excluded_count || 0).toLocaleString();
      if (elements.auditBorderlineCount) elements.auditBorderlineCount.textContent = (ast.borderline_review_count || total).toLocaleString();

      if (elements.reviewDatasetHealthTag) {
        elements.reviewDatasetHealthTag.textContent = ast.quality_status || 'HEALTHY & INDEXED';
      }
      if (elements.reviewHealthSubtext) {
        elements.reviewHealthSubtext.textContent = `FAISS Vector Store: ${ast.vector_index_status || 'Synchronized (384-dim)'}`;
      }
      if (elements.reviewAuditSummaryMsg) {
        elements.reviewAuditSummaryMsg.textContent = ast.summary_message || 'Dataset is clean, standardized, and indexed for high-precision retrieval.';
      }

      // Populate Preprocessing Stages
      if (elements.preprocessingStagesList && ast.preprocessing_stages && ast.preprocessing_stages.length > 0) {
        elements.preprocessingStagesList.innerHTML = ast.preprocessing_stages.map(stg => `
          <div style="padding: 8px 10px; background: var(--bg-card-hover); border-radius: 6px; border: 1px solid var(--border-color); font-size: 11px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
              <strong style="color: var(--text-main);">Stage ${stg.stage_number}: ${escapeHTML(stg.stage_name)}</strong>
              <span style="color: #34d399; font-weight: 600; font-size: 10px;">✓ ${escapeHTML(stg.status)}</span>
            </div>
            <p style="margin: 0 0 2px 0; color: var(--text-muted);">${escapeHTML(stg.description)}</p>
            ${stg.details ? `<small style="color: var(--text-dim); display: block;">${escapeHTML(stg.details)}</small>` : ''}
          </div>
        `).join('');
      }
    }

    // Update Progress and Stats
    if (elements.reviewProgressText) {
      elements.reviewProgressText.textContent = `${reviewed} / ${total} reviewed`;
    }
    if (elements.reviewProgressFill) {
      const pct = total > 0 ? Math.round((reviewed / total) * 100) : 0;
      elements.reviewProgressFill.style.width = `${pct}%`;
    }
    if (elements.statKeepCount) elements.statKeepCount.textContent = keep;
    if (elements.statExcludeCount) elements.statExcludeCount.textContent = exclude;
    if (elements.statPendingCount) elements.statPendingCount.textContent = pending;
    if (elements.reviewSummaryStat) {
      elements.reviewSummaryStat.textContent = `${total} total records in view (${keep} KEEP, ${exclude} EXCLUDE, ${pending} pending)`;
    }

    if (elements.reviewPendingBadge) {
      if (pending > 0) {
        elements.reviewPendingBadge.textContent = pending;
        elements.reviewPendingBadge.style.display = 'inline-flex';
      } else {
        elements.reviewPendingBadge.style.display = 'none';
      }
    }

    if (!data.records || data.records.length === 0) {
      if (!data.context_topic || data.context_topic === 'Master Corpus (Global)') {
        elements.reviewRecordsList.innerHTML = '<div class="review-loading-state" style="padding: 28px; text-align: center; color: var(--text-muted);"><span style="font-size: 26px; display: block; margin-bottom: 8px;">🌐</span><span>Master Dataset loaded and healthy.<br><small style="color: var(--text-dim); margin-top: 6px; display: block;">Click a region button above (e.g. <em>Assam, Mumbai, Bihar, Odisha</em>) or send an inquiry to inspect and review candidate records.</small></span></div>';
      } else {
        elements.reviewRecordsList.innerHTML = `<div class="review-loading-state" style="padding: 28px; text-align: center; color: var(--text-muted);"><span style="font-size: 26px; display: block; margin-bottom: 8px;">✅</span><span>No borderline records require review for context <strong>${escapeHTML(data.context_topic)}</strong>.<br><small style="color: var(--text-dim); margin-top: 6px; display: block;">All candidate records meet high-confidence thresholds.</small></span></div>`;
      }
      return;
    }

    elements.reviewRecordsList.innerHTML = '';
    data.records.forEach((rec) => {
      const card = document.createElement('div');
      const isKeep = rec.final_decision === 'KEEP';
      const isExclude = rec.final_decision === 'EXCLUDE';

      const statusClass = isKeep ? 'status-keep' : (isExclude ? 'status-exclude' : 'status-pending');
      card.className = `review-record-card ${statusClass}`;
      card.id = `review-card-${rec.record_id}`;

      let badgeHtml = '';
      if (isKeep) {
        badgeHtml = '<span class="decision-badge badge-keep">KEEP</span>';
      } else if (isExclude) {
        badgeHtml = '<span class="decision-badge badge-exclude">EXCLUDE</span>';
      } else {
        badgeHtml = '<span class="decision-badge badge-review">PENDING</span>';
      }

      card.innerHTML = `
        <div class="review-card-header">
          <h4 class="review-card-title">${escapeHTML(rec.title || 'Untitled Record')}</h4>
          <div class="review-card-badges">
            <span class="score-badge" title="Algorithmic Relevance Score">Score: ${rec.relevance_score.toFixed(2)}</span>
            ${badgeHtml}
          </div>
        </div>
        <div class="review-meta-row">
          <span class="review-meta-item"><strong>Context:</strong> <code>${escapeHTML(rec.context_topic || data.context_topic || 'Current Context')}</code></span>
          <span class="review-meta-item"><strong>Keywords:</strong> <code>${escapeHTML(rec.matched_keywords || 'None')}</code></span>
          <span class="review-meta-item"><strong>Reason:</strong> <code>${escapeHTML(rec.relevance_reason || 'Relevance Evaluation')}</code></span>
        </div>
        <div class="review-content-preview">
          ${escapeHTML(rec.content_preview || 'No content preview available.')}
        </div>
        <div class="review-card-actions">
          <button class="btn-action-keep ${isKeep ? 'active' : ''}" data-id="${rec.record_id}" title="Include in this research context only">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            <span>KEEP FOR CONTEXT</span>
          </button>
          <button class="btn-action-exclude ${isExclude ? 'active' : ''}" data-id="${rec.record_id}" title="Exclude from this research context only">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
            <span>EXCLUDE FOR CONTEXT</span>
          </button>
        </div>
      `;

      // Event listener for KEEP
      const btnKeep = card.querySelector('.btn-action-keep');
      btnKeep.addEventListener('click', () => submitDecision(rec.record_id, 'KEEP', rec.context_topic || data.context_topic));

      // Event listener for EXCLUDE
      const btnExclude = card.querySelector('.btn-action-exclude');
      btnExclude.addEventListener('click', () => submitDecision(rec.record_id, 'EXCLUDE', rec.context_topic || data.context_topic));

      elements.reviewRecordsList.appendChild(card);
    });
  }

  async function submitDecision(recordId, decision, contextTopic) {
    try {
      const resp = await fetch('/review/decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          record_id: recordId, 
          decision: decision,
          session_id: state.sessionId || null,
          context_topic: contextTopic || null
        })
      });

      if (!resp.ok) {
        throw new Error(`Failed to save decision (HTTP ${resp.status})`);
      }

      const updatedData = await resp.json();
      renderReviewQueueData(updatedData);
      showToast('Decision Saved', `Record marked as ${decision}.`, 'success');
    } catch (err) {
      showToast('Review Error', err.message || 'Could not save review decision.');
    }
  }

  // Launch application
  document.addEventListener('DOMContentLoaded', initApp);
})();
