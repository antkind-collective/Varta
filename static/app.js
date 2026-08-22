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
    messages: [] // { role: 'user' | 'assistant', text: '', citations: [], timestamp: '' }
  };

  // DOM Elements
  const elements = {
    sessionDisplay: document.getElementById('active-session-display'),
    turnCountBadge: document.getElementById('turn-count-badge'),
    btnUploadDataset: document.getElementById('btn-upload-dataset'),
    datasetFileInput: document.getElementById('dataset-file-input'),
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
    sampleChips: document.querySelectorAll('.sample-chip')
  };

  // ========================================================================
  // Initialization & Session Management
  // ========================================================================

  async function initApp() {
    setupEventListeners();
    await createNewSession();
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
        session_id: state.sessionId
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
      // Step 1: Uploading -> Step 2: Processing visual progression
      setTimeout(() => {
        setStepState(elements.stepUploading, 'completed');
        setStepState(elements.stepProcessing, 'active');
      }, 500);

      const response = await fetch('/dataset/upload', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Dataset upload failed with status ${response.status}`);
      }

      // Step 3 & 4: Indexing & Ready
      setStepState(elements.stepProcessing, 'completed');
      setStepState(elements.stepIndexing, 'completed');
      setStepState(elements.stepReady, 'completed');

      if (elements.uploadStatusBox) {
        elements.uploadStatusBox.className = 'upload-status-box';
        elements.uploadStatusIcon.textContent = '✅';
        elements.uploadStatusMsg.textContent = data.message || `Successfully ingested ${data.documents_ingested} documents. Ready for research queries.`;
        elements.uploadStatusBox.style.display = 'flex';
      }

      if (elements.modalFooter) {
        elements.modalFooter.style.display = 'flex';
      }

      showSuccessToast('Dataset Ingested & Queryable', `${data.documents_ingested} documents (${data.chunks_indexed} chunks) added. Total corpus: ${data.total_vectors_available.toLocaleString()} vectors.`);
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

  // Launch application
  document.addEventListener('DOMContentLoaded', initApp);
})();
