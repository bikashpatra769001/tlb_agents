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

  // Load page content
  readContentBtn.addEventListener('click', async function () {
    try {
      // Double-check URL permission
      if (!currentTab || !isUrlAllowed(currentTab.url)) {
        addSystemMessage('❌ This extension only works on the Bhulekh website.');
        return;
      }

      addSystemMessage('Loading page content...');

      // Execute script to get page content
      const results = await chrome.scripting.executeScript({
        target: { tabId: currentTab.id },
        function: getPageContent
      });

      pageContent = results[0].result;

      // Send content to Python endpoint to initialize context
      const response = await fetch('http://localhost:8000/load-content', {
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

      if (response.ok) {
        const result = await response.json();
        addSystemMessage('✅ Page content loaded! You can now ask questions.');

        // Display the webpage content
        displayPageContent(pageContent, currentTab.title);

        queryInput.disabled = false;
        sendButton.disabled = false;
        queryInput.focus();
      } else {
        throw new Error(`HTTP ${response.status}`);
      }

    } catch (error) {
      addSystemMessage(`❌ Error loading content: ${error.message}`);
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