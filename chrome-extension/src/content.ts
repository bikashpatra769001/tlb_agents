// Content script - Injects sidebar into Bhulekha pages
console.log('Bhulekha Extension: Content script loaded');

const SIDEBAR_ID = 'bhulekha-sidebar-container';
const TOGGLE_BUTTON_ID = 'bhulekha-toggle-button';
const SIDEBAR_STATE_KEY = 'bhulekha_sidebar_open';

let sidebarOpen = false;
let sidebarContainer: HTMLDivElement | null = null;
let toggleButton: HTMLButtonElement | null = null;

// Load sidebar state from storage
async function loadSidebarState(): Promise<boolean> {
  return new Promise((resolve) => {
    chrome.storage.local.get([SIDEBAR_STATE_KEY], (result) => {
      resolve(result[SIDEBAR_STATE_KEY] === true);
    });
  });
}

// Save sidebar state to storage
async function saveSidebarState(isOpen: boolean): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.set({ [SIDEBAR_STATE_KEY]: isOpen }, () => {
      resolve();
    });
  });
}

// Create toggle button
function createToggleButton(): HTMLButtonElement {
  const button = document.createElement('button');
  button.id = TOGGLE_BUTTON_ID;
  button.innerHTML = '🌾';
  button.title = 'Toggle Bhulekha Assistant (Ctrl+Shift+B)';

  // Styles for toggle button
  Object.assign(button.style, {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    width: '56px',
    height: '56px',
    borderRadius: '50%',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    fontSize: '24px',
    cursor: 'pointer',
    boxShadow: '0 4px 12px rgba(0, 123, 255, 0.4)',
    zIndex: '999998',
    transition: 'all 0.3s ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: 'Arial, sans-serif'
  });

  // Hover effect
  button.addEventListener('mouseenter', () => {
    button.style.transform = 'scale(1.1)';
    button.style.boxShadow = '0 6px 16px rgba(0, 123, 255, 0.6)';
  });

  button.addEventListener('mouseleave', () => {
    button.style.transform = 'scale(1)';
    button.style.boxShadow = '0 4px 12px rgba(0, 123, 255, 0.4)';
  });

  // Click handler
  button.addEventListener('click', toggleSidebar);

  return button;
}

// Create sidebar container
function createSidebarContainer(): HTMLDivElement {
  const container = document.createElement('div');
  container.id = SIDEBAR_ID;

  // Styles for container
  Object.assign(container.style, {
    position: 'fixed',
    top: '0',
    right: '-550px', // Hidden by default
    width: '550px',
    height: '100vh',
    zIndex: '999999',
    transition: 'right 0.3s ease',
    boxShadow: '-4px 0 12px rgba(0, 0, 0, 0.15)'
  });

  // Create iframe for sidebar
  const iframe = document.createElement('iframe');
  iframe.src = chrome.runtime.getURL('sidebar.html');
  iframe.style.width = '100%';
  iframe.style.height = '100%';
  iframe.style.border = 'none';
  iframe.style.display = 'block';

  container.appendChild(iframe);
  return container;
}

// Toggle sidebar visibility
async function toggleSidebar() {
  if (!sidebarContainer) {
    console.error('Sidebar container not found');
    return;
  }

  sidebarOpen = !sidebarOpen;

  if (sidebarOpen) {
    // Show sidebar
    sidebarContainer.style.right = '0';
    if (toggleButton) {
      toggleButton.style.right = '570px'; // Move button with sidebar
    }
  } else {
    // Hide sidebar
    sidebarContainer.style.right = '-550px';
    if (toggleButton) {
      toggleButton.style.right = '20px'; // Reset button position
    }
  }

  // Save state
  await saveSidebarState(sidebarOpen);
}

// Hide sidebar (called from sidebar close button)
function hideSidebar() {
  if (sidebarOpen) {
    toggleSidebar();
  }
}

// Initialize the sidebar
async function initializeSidebar() {
  // Create and inject toggle button
  toggleButton = createToggleButton();
  document.body.appendChild(toggleButton);

  // Create and inject sidebar container
  sidebarContainer = createSidebarContainer();
  document.body.appendChild(sidebarContainer);

  // Load saved state
  sidebarOpen = await loadSidebarState();

  // Apply saved state
  if (sidebarOpen) {
    sidebarContainer.style.right = '0';
    if (toggleButton) {
      toggleButton.style.right = '570px';
    }
  }

  // Listen for close messages from sidebar
  window.addEventListener('message', (event) => {
    if (event.data.type === 'BHULEKHA_CLOSE_SIDEBAR') {
      hideSidebar();
    }
  });

  console.log('Bhulekha Extension: Sidebar initialized');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeSidebar);
} else {
  initializeSidebar();
}

// Listen for keyboard shortcut
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'TOGGLE_SIDEBAR') {
    toggleSidebar();
    sendResponse({ success: true });
  }
});
