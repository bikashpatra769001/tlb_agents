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
}

// Constants
const ALLOWED_URLS = [
  'https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx',
  'https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx'
] as const;

const ACTION_BUTTONS: ActionButton[] = [
  { id: 'summarize', label: 'Summarize', icon: '📝', query: 'Please provide a concise summary of this page' },
  { id: 'apply_ec', label: 'Apply EC', icon: '📋', query: 'How do I apply for EC on this page? Please provide step-by-step instructions.' },
  { id: 'apply_cc', label: 'Apply CC', icon: '📄', query: 'How do I apply for CC on this page? Please provide step-by-step instructions.' }
];

// State
let pageContent: PageContent | null = null;
let currentTab: chrome.tabs.Tab | null = null;

// DOM Elements
const readContentBtn = document.getElementById('readContentBtn') as HTMLButtonElement;
const extractDetailsBtn = document.getElementById('extractDetailsBtn') as HTMLButtonElement;
const sendButton = document.getElementById('sendButton') as HTMLButtonElement;
const queryInput = document.getElementById('queryInput') as HTMLTextAreaElement;
const chatMessages = document.getElementById('chatMessages') as HTMLDivElement;

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
      readContentBtn.disabled = true;
      queryInput.disabled = true;
      sendButton.disabled = true;
      return false;
    }

    addSystemMessage('✅ Bhulekh website detected. You can load page content.');
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

function displayExtractionData(data: ExtractionData): void {
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
  chatMessages.appendChild(container);
  scrollToBottom();
}

function displayActionButtons(): void {
  const buttonsContainer = document.createElement('div');
  buttonsContainer.className = 'action-buttons-container';

  ACTION_BUTTONS.forEach(action => {
    const button = document.createElement('button');
    button.className = 'action-button';
    button.dataset.actionId = action.id;
    button.innerHTML = `${action.icon} ${action.label}`;

    button.addEventListener('click', async function () {
      const allActionButtons = buttonsContainer.querySelectorAll('.action-button') as NodeListOf<HTMLButtonElement>;
      allActionButtons.forEach(btn => btn.disabled = true);

      addUserMessage(`${action.icon} ${action.label}`);

      try {
        if (!currentTab?.url || !currentTab?.title) {
          throw new Error('No active tab found');
        }

        const response = await fetch('http://localhost:8000/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
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

      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        addBotMessage(`Sorry, I encountered an error: ${errorMessage}`);
      } finally {
        allActionButtons.forEach(btn => btn.disabled = false);
      }
    });

    buttonsContainer.appendChild(button);
  });

  chatMessages.appendChild(buttonsContainer);
  scrollToBottom();
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

// Event Handlers
async function handleLoadContent(): Promise<void> {
  try {
    if (!currentTab?.url || !isUrlAllowed(currentTab.url)) {
      addSystemMessage('❌ This extension only works on the Bhulekh website.');
      return;
    }

    readContentBtn.disabled = true;
    addSystemMessage('📖 Reading page content...');

    const results = await chrome.scripting.executeScript({
      target: { tabId: currentTab.id! },
      func: getPageContent
    });

    pageContent = results[0].result as PageContent;

    // Load content to backend for context
    const loadResponse = await fetch('http://localhost:8000/load-content', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: currentTab.url,
        title: currentTab.title,
        content: pageContent
      } as LoadContentRequest)
    });

    if (!loadResponse.ok) {
      throw new Error(`Failed to load content: HTTP ${loadResponse.status}`);
    }

    // Get explanation from Claude
    addSystemMessage('🤖 Getting explanation from Claude...');

    const explainResponse = await fetch('http://localhost:8000/explain', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: currentTab.url,
        title: currentTab.title,
        content: pageContent
      } as LoadContentRequest)
    });

    if (explainResponse.ok) {
      const result: ExplainResponse = await explainResponse.json();
      addBotMessage(result.explanation);
      displayActionButtons();
      addSystemMessage('✅ You can now ask follow-up questions!');

      queryInput.disabled = false;
      sendButton.disabled = false;
      queryInput.focus();
    } else {
      throw new Error(`Failed to get explanation: HTTP ${explainResponse.status}`);
    }

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    addSystemMessage(`❌ Error: ${errorMessage}`);
  } finally {
    readContentBtn.disabled = false;
  }
}

async function handleExtractDetails(): Promise<void> {
  try {
    if (!currentTab?.url || !isUrlAllowed(currentTab.url)) {
      addSystemMessage('❌ This extension only works on the Bhulekh website.');
      return;
    }

    extractDetailsBtn.disabled = true;
    addSystemMessage('📊 Fetching extracted details from database...');

    const response = await fetch('http://localhost:8000/get-extraction', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: currentTab.url,
        title: currentTab.title,
        content: { text: '', html: '' } // Not needed for this endpoint, but required by type
      } as LoadContentRequest)
    });

    if (response.ok) {
      const result: ExtractionResponse = await response.json();
      addSystemMessage('✅ Extraction data loaded successfully!');
      displayExtractionData(result.data);
    } else if (response.status === 404) {
      addSystemMessage('❌ No extraction found for this page. Please click "Help me understand" first to extract data.');
    } else if (response.status === 503) {
      addSystemMessage('❌ Database not available. Please configure Supabase connection.');
    } else {
      throw new Error(`HTTP ${response.status}`);
    }

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    addSystemMessage(`❌ Error: ${errorMessage}`);
  } finally {
    extractDetailsBtn.disabled = false;
  }
}

async function sendMessage(): Promise<void> {
  const query = queryInput.value.trim();
  if (!query || !pageContent) return;

  if (!currentTab?.url || !isUrlAllowed(currentTab.url)) {
    addBotMessage('❌ This extension only works on the Bhulekh website.');
    return;
  }

  addUserMessage(query);
  queryInput.value = '';
  sendButton.disabled = true;

  try {
    const response = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: query,
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

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    addBotMessage(`Sorry, I encountered an error: ${errorMessage}`);
  } finally {
    sendButton.disabled = false;
    queryInput.focus();
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', function () {
  // Initial state
  queryInput.disabled = true;
  sendButton.disabled = true;

  // Check permissions
  checkUrlPermission();

  // Event listeners
  readContentBtn.addEventListener('click', handleLoadContent);
  extractDetailsBtn.addEventListener('click', handleExtractDetails);
  sendButton.addEventListener('click', sendMessage);

  queryInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});
