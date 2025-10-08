document.addEventListener('DOMContentLoaded', function () {
  const readContentBtn = document.getElementById('readContentBtn');
  const sendButton = document.getElementById('sendButton');
  const queryInput = document.getElementById('queryInput');
  const chatMessages = document.getElementById('chatMessages');

  let pageContent = null;
  let currentTab = null;
  const ALLOWED_URLS = [
    'https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx',
    'https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx'
  ];

  // Action buttons configuration - easy to extend with new buttons
  const ACTION_BUTTONS = [
    { id: 'summarize', label: 'Summarize', icon: '📝', query: 'Please provide a concise summary of this page' },
    { id: 'apply_ec', label: 'Apply EC', icon: '📋', query: 'How do I apply for EC on this page? Please provide step-by-step instructions.' },
    { id: 'apply_cc', label: 'Apply CC', icon: '📄', query: 'How do I apply for CC on this page? Please provide step-by-step instructions.' }
  ];

  // Check if current page is allowed
  function isUrlAllowed(url) {
    return ALLOWED_URLS.some(allowedUrl => url.startsWith(allowedUrl));
  }

  async function checkUrlPermission() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      currentTab = tab;

      if (!isUrlAllowed(tab.url)) {
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

  // Initialize permission check
  checkUrlPermission();

  // Load page content and get explanation
  readContentBtn.addEventListener('click', async function () {
    try {
      // Double-check URL permission
      if (!currentTab || !isUrlAllowed(currentTab.url)) {
        addSystemMessage('❌ This extension only works on the Bhulekh website.');
        return;
      }

      // Disable button during loading
      readContentBtn.disabled = true;
      addSystemMessage('📖 Reading page content...');

      // Execute script to get page content
      const results = await chrome.scripting.executeScript({
        target: { tabId: currentTab.id },
        function: getPageContent
      });

      pageContent = results[0].result;

      // First, load content to backend for context (for follow-up questions)
      const loadResponse = await fetch('http://localhost:8000/load-content', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: currentTab.url,
          title: currentTab.title,
          content: pageContent
        })
      });

      if (!loadResponse.ok) {
        throw new Error(`Failed to load content: HTTP ${loadResponse.status}`);
      }

      // Now get the explanation from Claude
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
        })
      });

      if (explainResponse.ok) {
        const result = await explainResponse.json();

        // Display the explanation as a bot message
        addBotMessage(result.explanation);

        // Display action buttons for quick actions
        displayActionButtons();

        addSystemMessage('✅ You can now ask follow-up questions!');

        // Enable chat input for follow-up questions
        queryInput.disabled = false;
        sendButton.disabled = false;
        queryInput.focus();
      } else {
        throw new Error(`Failed to get explanation: HTTP ${explainResponse.status}`);
      }

    } catch (error) {
      addSystemMessage(`❌ Error: ${error.message}`);
    } finally {
      readContentBtn.disabled = false;
    }
  });

  // Send chat message
  sendButton.addEventListener('click', sendMessage);

  // Send message on Enter (but allow Shift+Enter for new lines)
  queryInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  async function sendMessage() {
    const query = queryInput.value.trim();
    if (!query || !pageContent) return;

    // Double-check URL permission
    if (!currentTab || !isUrlAllowed(currentTab.url)) {
      addBotMessage('❌ This extension only works on the Bhulekh website.');
      return;
    }

    // Add user message to chat
    addUserMessage(query);
    queryInput.value = '';
    sendButton.disabled = true;

    try {
      // Send query to Python endpoint
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          url: currentTab.url,
          title: currentTab.title
        })
      });

      if (response.ok) {
        const result = await response.json();
        addBotMessage(result.response);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }

    } catch (error) {
      addBotMessage(`Sorry, I encountered an error: ${error.message}`);
    } finally {
      sendButton.disabled = false;
      queryInput.focus();
    }
  }

  function addUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.textContent = message;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
  }

  function addBotMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    messageDiv.textContent = message;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
  }

  function addSystemMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system-message';
    messageDiv.textContent = message;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
  }

  function displayPageContent(content, title) {
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message content-message';

    // Create content preview
    const textContent = content.text || '';
    const wordCount = textContent.split(' ').length;
    const preview = textContent.length > 300 ? textContent.substring(0, 300) + '...' : textContent;

    contentDiv.innerHTML = `
      <div class="content-header">
        <strong>📄 Page Content Loaded</strong>
        <div class="content-stats">${wordCount} words • ${title}</div>
      </div>
      <div class="content-preview">${preview}</div>
    `;

    chatMessages.appendChild(contentDiv);
    scrollToBottom();
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Display action buttons after explanation
  function displayActionButtons() {
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'action-buttons-container';

    ACTION_BUTTONS.forEach(action => {
      const button = document.createElement('button');
      button.className = 'action-button';
      button.dataset.actionId = action.id;
      button.innerHTML = `${action.icon} ${action.label}`;

      button.addEventListener('click', async function () {
        // Disable all action buttons
        const allActionButtons = buttonsContainer.querySelectorAll('.action-button');
        allActionButtons.forEach(btn => btn.disabled = true);

        // Add user message showing what action was clicked
        addUserMessage(`${action.icon} ${action.label}`);

        // Send the predefined query to backend
        try {
          const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              query: action.query,
              url: currentTab.url,
              title: currentTab.title
            })
          });

          if (response.ok) {
            const result = await response.json();
            addBotMessage(result.response);
          } else {
            throw new Error(`HTTP ${response.status}`);
          }

        } catch (error) {
          addBotMessage(`Sorry, I encountered an error: ${error.message}`);
        } finally {
          // Re-enable action buttons
          allActionButtons.forEach(btn => btn.disabled = false);
        }
      });

      buttonsContainer.appendChild(button);
    });

    chatMessages.appendChild(buttonsContainer);
    scrollToBottom();
  }

  // Initially disable input until content is loaded
  queryInput.disabled = true;
  sendButton.disabled = true;
});

// Function to be injected into the page
function getPageContent() {
  // Get text content, removing script and style elements
  const scripts = document.querySelectorAll('script, style');
  scripts.forEach(el => el.remove());

  return {
    text: document.body.innerText || document.body.textContent || '',
    html: document.documentElement.outerHTML
  };
}