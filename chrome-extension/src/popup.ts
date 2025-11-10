// Wrap in IIFE to avoid global scope conflicts with sidebar.ts
(function() {

// Types
interface PageContent {
  text: string;
  html: string;
}

interface ActionButton {
  id: string;
  label: string;
  icon: string;
  query: string;
}

interface ChatRequest {
  query: string;
  url: string;
  title: string;
}

interface LoadContentRequest {
  url: string;
  title: string;
  content: PageContent;
}

interface ExplainResponse {
  explanation: string;
}

interface ChatResponse {
  response: string;
}

interface ExtractionData {
  location: {
    district: string;
    tehsil: string;
    village: string;
    khatiyan_number: string;
  };
  owner_details: {
    owner_name: string;
    father_name: string;
    caste: string;
    other_owners: string;
  };
  plot_information: {
    total_plots: string;
    plot_numbers: string;
    total_area: string;
    land_type: string;
  };
  additional_info: {
    special_comments: string;
  };
  metadata: {
    model_name: string;
    extraction_time_ms: number;
    created_at: string;
  };
}

interface ExtractionResponse {
  status: string;
  data: ExtractionData;
  url: string;
  extraction_id: number;
}

interface SummaryResponse {
  status: string;
  url: string;
  title: string;
  html_summary: string;
  generation_time_ms: number;
  extraction_id: number;  // For feedback submission
  cached: boolean;        // Show cache indicator
}

// Constants
// const API_BASE_URL = 'https://wyt8w11xp0.execute-api.ap-south-1.amazonaws.com';
const API_BASE_URL = 'http://0.0.0.0:8000'
const ALLOWED_URLS = [
  'https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx',
  'https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx'
] as const;
const TESTER_ID_STORAGE_KEY = 'bhulekha_tester_id';

const ACTION_BUTTONS: ActionButton[] = [
  { id: 'summarize', label: 'Summarize', icon: '📝', query: 'Please provide a concise summary of this page' },
  { id: 'apply_ec', label: 'Apply EC', icon: '📋', query: 'How do I apply for EC on this page? Please provide step-by-step instructions.' },
  { id: 'apply_cc', label: 'Apply CC', icon: '📄', query: 'How do I apply for CC on this page? Please provide step-by-step instructions.' }
];

// State
let pageContent: PageContent | null = null;
let currentTab: chrome.tabs.Tab | null = null;
let testerId: string | null = null;
let pendingFeedback: {
  extractionId: number;
  feedback: string;
  isSummary: boolean;
  button: HTMLButtonElement;
} | null = null;

// DOM Elements
const extractDetailsBtn = document.getElementById('extractDetailsBtn') as HTMLButtonElement;
const chatMessages = document.getElementById('chatMessages') as HTMLDivElement;
const loadingOverlay = document.getElementById('loadingOverlay') as HTMLDivElement;
const loadingText = document.querySelector('.loading-text') as HTMLDivElement;

// Tester ID Storage Functions
async function getTesterId(): Promise<string | null> {
  return new Promise((resolve) => {
    chrome.storage.sync.get([TESTER_ID_STORAGE_KEY], (result) => {
      resolve(result[TESTER_ID_STORAGE_KEY] || null);
    });
  });
}

async function setTesterId(id: string): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.sync.set({ [TESTER_ID_STORAGE_KEY]: id }, () => {
      testerId = id;
      resolve();
    });
  });
}

async function clearTesterId(): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.sync.remove([TESTER_ID_STORAGE_KEY], () => {
      testerId = null;
      resolve();
    });
  });
}

// Loading Spinner Functions
function showLoading(message: string = 'Loading...'): void {
  if (loadingText) {
    loadingText.textContent = message;
  }
  if (loadingOverlay) {
    loadingOverlay.style.display = 'flex';
  }
}

function hideLoading(): void {
  if (loadingOverlay) {
    loadingOverlay.style.display = 'none';
  }
}

// Feedback Modal Functions
function showFeedbackModal(isSummary: boolean): void {
  const modal = document.getElementById('feedbackModal') as HTMLDivElement;
  const modalTitle = document.getElementById('feedbackModalTitle') as HTMLHeadingElement;
  const modalPrompt = document.getElementById('feedbackModalPrompt') as HTMLParagraphElement;
  const commentInput = document.getElementById('feedbackCommentInput') as HTMLTextAreaElement;

  if (!modal) return;

  // Update modal text based on feedback type
  if (isSummary) {
    modalTitle.textContent = 'What wasn\'t helpful?';
    modalPrompt.textContent = 'Please help us improve the summary (optional):';
    commentInput.placeholder = 'e.g., Missing information about plot boundaries, Safety score seems inaccurate...';
  } else {
    modalTitle.textContent = 'What went wrong?';
    modalPrompt.textContent = 'Please help us improve by describing what was extracted incorrectly (optional):';
    commentInput.placeholder = 'e.g., Owner name is wrong - it should be \'Ram Kumar\' not \'Rama Kumar\'...';
  }

  // Clear previous input
  commentInput.value = '';

  // Show modal
  modal.style.display = 'flex';
}

function hideFeedbackModal(): void {
  const modal = document.getElementById('feedbackModal') as HTMLDivElement;
  if (modal) {
    modal.style.display = 'none';
  }
  pendingFeedback = null;
}

// Helper Functions
function isUrlAllowed(url: string): boolean {
  return ALLOWED_URLS.some(allowedUrl => url.startsWith(allowedUrl));
}

async function checkUrlPermission(): Promise<boolean> {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentTab = tab;

    if (!tab.url || !isUrlAllowed(tab.url)) {
      addSystemMessage('❌ This extension only works on the Bhulekh website.');
      addSystemMessage('Please navigate to one of these URLs:');
      ALLOWED_URLS.forEach(url => addSystemMessage(`• ${url}`));
      return false;
    }

    addSystemMessage('✅ Bhulekh website detected. Loading page content...');
    return true;
  } catch (error) {
    addSystemMessage('❌ Error checking page permissions.');
    return false;
  }
}

function addUserMessage(message: string): void {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message user-message';
  messageDiv.textContent = message;
  chatMessages.appendChild(messageDiv);
  scrollToBottom();
}

function addBotMessage(message: string): void {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message bot-message';
  messageDiv.textContent = message;
  chatMessages.appendChild(messageDiv);
  scrollToBottom();
}

function addSystemMessage(message: string): void {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message system-message';
  messageDiv.textContent = message;
  chatMessages.appendChild(messageDiv);
  scrollToBottom();
}

function scrollToBottom(): void {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function displayExtractionData(data: ExtractionData, extractionId: number): void {
  const container = document.createElement('div');
  container.className = 'extraction-display';

  let html = '<div class="extraction-section">';

  // Location Information
  html += '<h4>📍 Location Information</h4>';
  html += '<table class="extraction-table">';
  html += `<tr><td><strong>District:</strong></td><td>${data.location.district || 'N/A'}</td></tr>`;
  html += `<tr><td><strong>Tehsil:</strong></td><td>${data.location.tehsil || 'N/A'}</td></tr>`;
  html += `<tr><td><strong>Village:</strong></td><td>${data.location.village || 'N/A'}</td></tr>`;
  html += `<tr><td><strong>Khatiyan Number:</strong></td><td>${data.location.khatiyan_number || 'N/A'}</td></tr>`;
  html += '</table>';

  // Owner Details
  html += '<h4>👤 Owner Details</h4>';
  html += '<table class="extraction-table">';
  html += `<tr><td><strong>Owner Name:</strong></td><td>${data.owner_details.owner_name || 'N/A'}</td></tr>`;
  html += `<tr><td><strong>Father\'s Name:</strong></td><td>${data.owner_details.father_name || 'N/A'}</td></tr>`;
  if (data.owner_details.caste && data.owner_details.caste !== 'Not found') {
    html += `<tr><td><strong>Caste:</strong></td><td>${data.owner_details.caste}</td></tr>`;
  }
  if (data.owner_details.other_owners && data.owner_details.other_owners !== 'Not found') {
    html += `<tr><td><strong>Other Owners:</strong></td><td>${data.owner_details.other_owners}</td></tr>`;
  }
  html += '</table>';

  // Plot Information
  html += '<h4>🗺️ Plot Information</h4>';
  html += '<table class="extraction-table">';
  html += `<tr><td><strong>Total Plots:</strong></td><td>${data.plot_information.total_plots || 'N/A'}</td></tr>`;
  html += `<tr><td><strong>Plot Numbers:</strong></td><td>${data.plot_information.plot_numbers || 'N/A'}</td></tr>`;
  html += `<tr><td><strong>Total Area:</strong></td><td>${data.plot_information.total_area || 'N/A'}</td></tr>`;
  html += `<tr><td><strong>Land Type:</strong></td><td>${data.plot_information.land_type || 'N/A'}</td></tr>`;
  html += '</table>';

  // Additional Information
  if (data.additional_info.special_comments && data.additional_info.special_comments !== 'Not found') {
    html += '<h4>📝 Special Comments</h4>';
    html += `<p class="special-comments">${data.additional_info.special_comments}</p>`;
  }

  // Metadata
  html += '<div class="extraction-metadata">';
  html += `<small>Extracted by: ${data.metadata.model_name} | Time: ${data.metadata.extraction_time_ms}ms</small>`;
  html += '</div>';

  html += '</div>';

  container.innerHTML = html;

  // Add feedback buttons
  const feedbackContainer = document.createElement('div');
  feedbackContainer.className = 'feedback-container';
  feedbackContainer.innerHTML = `
    <div class="feedback-prompt">Is this extraction accurate?</div>
    <div class="feedback-buttons">
      <button class="feedback-btn thumbs-up" data-extraction-id="${extractionId}" data-feedback="correct">
        👍 Correct
      </button>
      <button class="feedback-btn thumbs-down" data-extraction-id="${extractionId}" data-feedback="wrong">
        👎 Wrong
      </button>
    </div>
  `;

  container.appendChild(feedbackContainer);
  chatMessages.appendChild(container);

  // Add event listeners to feedback buttons
  const feedbackButtons = feedbackContainer.querySelectorAll('.feedback-btn') as NodeListOf<HTMLButtonElement>;
  feedbackButtons.forEach(button => {
    button.addEventListener('click', handleFeedbackClick);
  });

  scrollToBottom();
}

function displaySummaryWithFeedback(
  htmlSummary: string,
  extractionId: number,
  cached: boolean
): void {
  const container = document.createElement('div');
  container.className = 'message bot-message html-summary';

  // Cache indicator
  if (cached) {
    const cacheTag = document.createElement('div');
    cacheTag.className = 'cache-indicator';
    cacheTag.style.cssText = 'background: #e3f2fd; padding: 5px 10px; border-radius: 3px; margin-bottom: 10px; font-size: 0.9em;';
    cacheTag.innerHTML = '📦 <small>Cached summary (loaded from database)</small>';
    container.appendChild(cacheTag);
  }

  // HTML summary content
  const summaryDiv = document.createElement('div');
  summaryDiv.innerHTML = htmlSummary;
  container.appendChild(summaryDiv);

  // Feedback buttons
  const feedbackContainer = document.createElement('div');
  feedbackContainer.className = 'feedback-container';
  feedbackContainer.innerHTML = `
    <div class="feedback-prompt">Is this summary helpful and accurate?</div>
    <div class="feedback-buttons">
      <button class="feedback-btn thumbs-up" data-extraction-id="${extractionId}" data-feedback="correct">
        👍 Helpful
      </button>
      <button class="feedback-btn thumbs-down" data-extraction-id="${extractionId}" data-feedback="wrong">
        👎 Not Helpful
      </button>
    </div>
  `;

  container.appendChild(feedbackContainer);
  chatMessages.appendChild(container);

  // Attach event listeners
  const feedbackButtons = feedbackContainer.querySelectorAll('.feedback-btn') as NodeListOf<HTMLButtonElement>;
  feedbackButtons.forEach(button => {
    button.addEventListener('click', handleSummaryFeedbackClick);
  });

  scrollToBottom();
}

function displayStructuredSummary(result: any): void {
  const container = document.createElement('div');
  container.className = 'message bot-message structured-summary';

  let html = '';

  // 1. Summary Section
  if (result.summary || result.explanation) {
    html += '<div class="summary-section" style="margin-bottom: 20px;">';
    html += '<h3 style="color: #1976d2; margin-bottom: 10px;">📋 Summary</h3>';
    html += `<p style="line-height: 1.6;">${result.summary || result.explanation}</p>`;
    html += '</div>';
  }

  // 2. Owner Details Section
  if (result.owner_details || result.owner) {
    const owner = result.owner_details || result.owner || {};
    html += '<div class="owner-section" style="margin-bottom: 20px;">';
    html += '<h3 style="color: #1976d2; margin-bottom: 10px;">👤 Owner Details</h3>';
    html += '<table class="extraction-table" style="width: 100%; border-collapse: collapse;">';

    if (owner.owner_name || owner.name) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Owner Name:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${owner.owner_name || owner.name}</td></tr>`;
    }
    if (owner.father_name) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Father's Name:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${owner.father_name}</td></tr>`;
    }
    if (owner.caste && owner.caste !== 'Not found') {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Caste:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${owner.caste}</td></tr>`;
    }
    if (owner.other_owners && owner.other_owners !== 'None mentioned') {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Co-owners:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${owner.other_owners}</td></tr>`;
    }

    html += '</table>';
    html += '</div>';
  }

  // 3. Plot Information Section
  if (result.plot_information || result.plots || result.land_details) {
    const plots = result.plot_information || result.plots || result.land_details || {};
    html += '<div class="plot-section" style="margin-bottom: 20px;">';
    html += '<h3 style="color: #1976d2; margin-bottom: 10px;">🗺️ Plot Information</h3>';
    html += '<table class="extraction-table" style="width: 100%; border-collapse: collapse;">';

    if (plots.total_plots || plots.plot_count) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Total Plots:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${plots.total_plots || plots.plot_count}</td></tr>`;
    }
    if (plots.total_area || plots.area) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Total Area:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${plots.total_area || plots.area}</td></tr>`;
    }
    if (plots.land_type || plots.type) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Land Type:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${plots.land_type || plots.type}</td></tr>`;
    }
    if (plots.plot_numbers) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Plot Numbers:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${plots.plot_numbers}</td></tr>`;
    }

    html += '</table>';
    html += '</div>';
  }

  // 4. Location Information Section (if available)
  if (result.location) {
    const location = result.location;
    html += '<div class="location-section" style="margin-bottom: 20px;">';
    html += '<h3 style="color: #1976d2; margin-bottom: 10px;">📍 Location</h3>';
    html += '<table class="extraction-table" style="width: 100%; border-collapse: collapse;">';

    if (location.district) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>District:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${location.district}</td></tr>`;
    }
    if (location.tehsil || location.tahasil) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Tehsil:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${location.tehsil || location.tahasil}</td></tr>`;
    }
    if (location.village) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Village:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${location.village}</td></tr>`;
    }
    if (location.khatiyan_number || location.khata_number) {
      html += `<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Khatiyan Number:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">${location.khatiyan_number || location.khata_number}</td></tr>`;
    }

    html += '</table>';
    html += '</div>';
  }

  // 5. Next Steps Section
  html += '<div class="next-steps-section" style="margin-bottom: 20px; background: #f5f5f5; padding: 15px; border-radius: 5px;">';
  html += '<h3 style="color: #1976d2; margin-bottom: 10px;">🎯 Next Steps</h3>';
  html += '<ul style="margin: 0; padding-left: 20px; line-height: 1.8;">';
  html += '<li>Verify the ownership details with the actual land records</li>';
  html += '<li>Check for any pending mutations or legal disputes</li>';
  html += '<li>Visit the land physically to verify boundaries</li>';
  html += '<li>Consult with a legal expert before any transactions</li>';
  html += '<li>Use the action buttons below to apply for EC (Encumbrance Certificate) or CC (Caste Certificate)</li>';
  html += '</ul>';
  html += '</div>';

  // If the response has html_summary, display it as fallback
  if (result.html_summary && !result.summary && !result.owner_details && !result.plot_information) {
    html = result.html_summary;
  }

  container.innerHTML = html;
  chatMessages.appendChild(container);
  scrollToBottom();
}

async function handleActionButtonClick(actionId: string): Promise<void> {
  const action = ACTION_BUTTONS.find(a => a.id === actionId);
  if (!action) return;

  if (!pageContent) {
    addSystemMessage('❌ Page content is still loading. Please wait a moment.');
    return;
  }

  if (!currentTab?.url || !currentTab?.title) {
    addSystemMessage('❌ No active tab found.');
    return;
  }

  const allActionButtons = document.querySelectorAll('.action-button') as NodeListOf<HTMLButtonElement>;
  allActionButtons.forEach(btn => btn.disabled = true);

  addUserMessage(`${action.icon} ${action.label}`);

  // Show loading spinner with custom message
  showLoading(actionId === 'summarize' ? 'Generating summary...' : 'Processing request...');

  try {
    // Use new API endpoint for summarize button, /chat for others
    if (action.id === 'summarize') {
      // Read current page content for summarization
      const results = await chrome.scripting.executeScript({
        target: { tabId: currentTab.id! },
        func: getPageContent
      });

      const currentPageContent = results[0].result as PageContent;

      // Call the new summarization API for Chrome extension
      const response = await fetch(`${API_BASE_URL}/api/v2/od/summarize_ror_ext`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tester-ID': testerId || 'anonymous',
        },
        body: JSON.stringify({
          html_content: currentPageContent.html,
          translation_model: 'claude-sonnet-4-5',
          summarization_model: 'claude-haiku-4-5'
        })
      });

      if (response.ok) {
        const result = await response.json();

        // Display the summary using structured format
        displayStructuredSummary(result);
      } else {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
    } else {
      // Use /chat endpoint for other action buttons
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tester-ID': testerId || 'anonymous',
        },
        body: JSON.stringify({
          query: action.query,
          url: currentTab.url,
          title: currentTab.title
        } as ChatRequest)
      });

      if (response.ok) {
        const result: ChatResponse = await response.json();
        addBotMessage(result.response);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    }

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    addBotMessage(`Sorry, I encountered an error: ${errorMessage}`);
  } finally {
    hideLoading();
    allActionButtons.forEach(btn => btn.disabled = false);
  }
}

// Function to be injected into the page
function getPageContent(): PageContent {
  const scripts = document.querySelectorAll('script, style');
  scripts.forEach(el => el.remove());

  return {
    text: document.body.innerText || document.body.textContent || '',
    html: document.documentElement.outerHTML
  };
}

// Feedback handler
async function handleFeedbackClick(event: Event): Promise<void> {
  const button = event.currentTarget as HTMLButtonElement;
  const extractionId = parseInt(button.dataset.extractionId || '0');
  const feedback = button.dataset.feedback as string;

  if (!extractionId) {
    addSystemMessage('❌ Error: Extraction ID not found');
    return;
  }

  // If thumbs down (wrong), show modal for comment
  if (feedback === 'wrong') {
    pendingFeedback = {
      extractionId,
      feedback,
      isSummary: false,
      button
    };
    showFeedbackModal(false);
    return;
  }

  // Thumbs up - immediate submit
  await submitFeedback(extractionId, feedback, null, false, button);
}

async function submitFeedback(
  extractionId: number,
  feedback: string,
  userComment: string | null,
  isSummary: boolean,
  button: HTMLButtonElement
): Promise<void> {
  try {
    // Disable all feedback buttons
    const allFeedbackButtons = document.querySelectorAll('.feedback-btn') as NodeListOf<HTMLButtonElement>;
    allFeedbackButtons.forEach(btn => btn.disabled = true);

    // Show loading spinner
    showLoading('Submitting feedback...');

    const endpoint = isSummary ? '/submit-summary-feedback' : '/submit-feedback';
    const requestBody: any = {
      extraction_id: extractionId,
      feedback: feedback
    };

    if (userComment && userComment.trim()) {
      requestBody.user_comment = userComment.trim();
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Tester-ID': testerId || 'anonymous',
      },
      body: JSON.stringify(requestBody)
    });

    if (response.ok) {
      const result = await response.json();
      addSystemMessage(`✅ ${result.message}. Thank you for your feedback!`);

      // Update button appearance to show which was clicked
      button.classList.add('selected');
      if (isSummary) {
        button.textContent = feedback === 'correct' ? '✓ Marked Helpful' : '✗ Marked Not Helpful';
      } else {
        button.textContent = feedback === 'correct' ? '✓ Marked Correct' : '✗ Marked Wrong';
      }
    } else {
      throw new Error(`HTTP ${response.status}`);
    }

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    addSystemMessage(`❌ Error submitting feedback: ${errorMessage}`);

    // Re-enable buttons on error
    const allFeedbackButtons = document.querySelectorAll('.feedback-btn') as NodeListOf<HTMLButtonElement>;
    allFeedbackButtons.forEach(btn => btn.disabled = false);
  } finally {
    hideLoading();
  }
}

async function handleSummaryFeedbackClick(event: Event): Promise<void> {
  const button = event.currentTarget as HTMLButtonElement;
  const extractionId = parseInt(button.dataset.extractionId || '0');
  const feedback = button.dataset.feedback as string;

  if (!extractionId) {
    addSystemMessage('❌ Error: Extraction ID not found');
    return;
  }

  // If thumbs down (wrong/not helpful), show modal for comment
  if (feedback === 'wrong') {
    pendingFeedback = {
      extractionId,
      feedback,
      isSummary: true,
      button
    };
    showFeedbackModal(true);
    return;
  }

  // Thumbs up - immediate submit
  await submitFeedback(extractionId, feedback, null, true, button);
}

// Event Handlers
async function handleLoadContent(): Promise<void> {
  try {
    if (!currentTab?.url || !isUrlAllowed(currentTab.url)) {
      addSystemMessage('❌ This extension only works on the Bhulekh website.');
      return;
    }

    showLoading('Reading page content...');
    addSystemMessage('📖 Reading page content...');

    const results = await chrome.scripting.executeScript({
      target: { tabId: currentTab.id! },
      func: getPageContent
    });

    pageContent = results[0].result as PageContent;

    showLoading('Generating summary from Land experts...');
    addSystemMessage('🤖 Generating summary from Land experts...');

    // Call the new summarization API directly
    const response = await fetch(`${API_BASE_URL}/api/v2/od/summarize_ror_ext`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Tester-ID': testerId || 'anonymous',
      },
      body: JSON.stringify({
        html_content: pageContent.html,
        translation_model: 'claude-sonnet-4-5',
        summarization_model: 'claude-haiku-4-5'
      })
    });

    if (response.ok) {
      const result = await response.json();

      // Display the summary using structured format
      displayStructuredSummary(result);
      addSystemMessage('✅ Summary generated! Use the action buttons below for more actions.');
    } else {
      const errorText = await response.text();
      throw new Error(`Failed to generate summary: HTTP ${response.status} - ${errorText}`);
    }

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    addSystemMessage(`❌ Error: ${errorMessage}`);
  } finally {
    hideLoading();
  }
}

async function handleExtractDetails(): Promise<void> {
  try {
    if (!currentTab?.url || !isUrlAllowed(currentTab.url)) {
      addSystemMessage('❌ This extension only works on the Bhulekh website.');
      return;
    }

    extractDetailsBtn.disabled = true;
    showLoading('Reading page content...');
    addSystemMessage('📊 Reading current page content...');

    // Read current page content to match exact page state
    const results = await chrome.scripting.executeScript({
      target: { tabId: currentTab.id! },
      func: getPageContent
    });

    const currentPageContent = results[0].result as PageContent;

    showLoading('Fetching extracted details...');
    addSystemMessage('📊 Fetching extracted details from database...');

    const response = await fetch(`${API_BASE_URL}/get-extraction`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Tester-ID': testerId || 'anonymous',
      },
      body: JSON.stringify({
        url: currentTab.url,
        title: currentTab.title,
        content: currentPageContent // Send actual page content for hash matching
      } as LoadContentRequest)
    });

    if (response.ok) {
      const result: ExtractionResponse = await response.json();
      addSystemMessage('✅ Extraction data loaded successfully!');
      displayExtractionData(result.data, result.extraction_id);
    } else if (response.status === 404) {
      addSystemMessage('❌ No extraction found for this page. Data extraction happens automatically when the page loads.');
    } else if (response.status === 503) {
      addSystemMessage('❌ Database not available. Please configure Supabase connection.');
    } else {
      throw new Error(`HTTP ${response.status}`);
    }

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    addSystemMessage(`❌ Error: ${errorMessage}`);
  } finally {
    hideLoading();
    extractDetailsBtn.disabled = false;
  }
}


// Tester Setup Functions
async function initializeTesterSetup(): Promise<void> {
  const modal = document.getElementById('testerSetupModal') as HTMLDivElement;
  const testerIdInput = document.getElementById('testerIdInput') as HTMLInputElement;
  const saveTesterIdBtn = document.getElementById('saveTesterIdBtn') as HTMLButtonElement;

  // Check if tester ID exists
  const existingTesterId = await getTesterId();

  if (existingTesterId) {
    // Tester ID already exists, hide modal and load it
    testerId = existingTesterId;
    modal.style.display = 'none';
    console.log(`Tester ID loaded: ${testerId}`);
  } else {
    // Show modal for first-time setup
    modal.style.display = 'flex';
  }

  // Handle save button click
  saveTesterIdBtn.addEventListener('click', async function () {
    const newTesterId = testerIdInput.value.trim();

    if (!newTesterId) {
      alert('Please enter a tester ID');
      return;
    }

    // Validate tester ID (alphanumeric, underscores, hyphens only)
    if (!/^[a-zA-Z0-9_-]+$/.test(newTesterId)) {
      alert('Tester ID can only contain letters, numbers, underscores, and hyphens');
      return;
    }

    // Save tester ID
    await setTesterId(newTesterId);

    // Hide modal
    modal.style.display = 'none';

    addSystemMessage(`✅ Welcome, ${newTesterId}! Your ID has been saved.`);
  });

  // Handle Enter key in input
  testerIdInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      saveTesterIdBtn.click();
    }
  });
}

// Initialize
document.addEventListener('DOMContentLoaded', async function () {
  // Initialize tester setup (check if ID exists, show modal if needed)
  await initializeTesterSetup();

  // Check permissions and auto-load content
  const isValidUrl = await checkUrlPermission();
  if (isValidUrl) {
    await handleLoadContent();
  }

  // Event listeners for main buttons
  extractDetailsBtn.addEventListener('click', handleExtractDetails);

  // Event listeners for footer action buttons
  const actionButtons = document.querySelectorAll('.action-button') as NodeListOf<HTMLButtonElement>;
  actionButtons.forEach(button => {
    button.addEventListener('click', function() {
      const actionId = this.dataset.action;
      if (actionId) {
        handleActionButtonClick(actionId);
      }
    });
  });

  // Event listeners for feedback modal
  const submitFeedbackBtn = document.getElementById('submitFeedbackBtn') as HTMLButtonElement;
  const skipFeedbackBtn = document.getElementById('skipFeedbackBtn') as HTMLButtonElement;
  const feedbackCommentInput = document.getElementById('feedbackCommentInput') as HTMLTextAreaElement;

  if (submitFeedbackBtn) {
    submitFeedbackBtn.addEventListener('click', async function() {
      if (!pendingFeedback) return;

      const userComment = feedbackCommentInput.value.trim() || null;

      // Save pendingFeedback values before clearing them
      const { extractionId, feedback, isSummary, button } = pendingFeedback;

      // Hide modal (this sets pendingFeedback = null)
      hideFeedbackModal();

      // Submit feedback with comment using saved values
      await submitFeedback(
        extractionId,
        feedback,
        userComment,
        isSummary,
        button
      );
    });
  }

  if (skipFeedbackBtn) {
    skipFeedbackBtn.addEventListener('click', async function() {
      if (!pendingFeedback) return;

      // Save pendingFeedback values before clearing them
      const { extractionId, feedback, isSummary, button } = pendingFeedback;

      // Hide modal (this sets pendingFeedback = null)
      hideFeedbackModal();

      // Submit feedback without comment using saved values
      await submitFeedback(
        extractionId,
        feedback,
        null,
        isSummary,
        button
      );
    });
  }
});

})(); // End IIFE
