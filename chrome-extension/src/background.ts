// Background service worker for keyboard shortcuts
console.log('Bhulekha Extension: Background service worker loaded');

// Listen for keyboard command
chrome.commands.onCommand.addListener((command) => {
  if (command === 'toggle-sidebar') {
    // Send message to active tab's content script
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'TOGGLE_SIDEBAR' })
          .then(() => console.log('Toggle sidebar command sent'))
          .catch((error) => console.error('Error sending toggle command:', error));
      }
    });
  }
});
