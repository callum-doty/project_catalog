// app/static/js/sync.js

document.addEventListener('DOMContentLoaded', function() {
    // Initialize sync status check
    checkSyncStatus();
    
    // Set up periodic sync status checks with a slightly longer interval
    // to reduce server load
    setInterval(checkSyncStatus, 60000); // Check every minute
    
    // Initialize the sync button if it exists
    const syncButton = document.getElementById('triggerSyncBtn');
    if (syncButton) {
        syncButton.addEventListener('click', manualSync);
    }
});

// Function to check sync status with proper error handling and timeout
async function checkSyncStatus() {
    // Create an abort controller for timeout management
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
    
    try {
        const response = await fetch('/api/sync-status', {
            signal: controller.signal,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        // Clear the timeout since the request completed
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            updateSyncStatus('error', 'Error checking sync status');
            console.error(`Status check failed: ${response.status} ${response.statusText}`);
            return;
        }
        
        const data = await response.json();
        
        // Find status elements
        const statusIndicator = document.querySelector('.sync-indicator');
        const statusText = document.querySelector('.sync-text');
        
        // Only proceed if elements exist
        if (!statusIndicator || !statusText) {
            console.warn('Sync status elements not found - skipping update');
            return;
        }
        
        // Update sync indicator
        if (data.dropbox_connected) {
            // Connected to Dropbox
            if (data.last_sync_time) {
                const lastSyncDate = new Date(data.last_sync_time);
                const now = new Date();
                const hoursSinceSync = Math.round((now - lastSyncDate) / (1000 * 60 * 60));
                
                if (hoursSinceSync < 1) {
                    // Synced within the last hour
                    updateSyncStatus('success', `Last sync: ${formatTimeAgo(lastSyncDate)}`);
                } else if (hoursSinceSync < 24) {
                    // Synced within the last day
                    updateSyncStatus('warning', `Last sync: ${formatTimeAgo(lastSyncDate)}`);
                } else {
                    // Synced more than a day ago
                    updateSyncStatus('error', `Last sync: ${formatTimeAgo(lastSyncDate)}`);
                }
            } else {
                // No sync yet
                updateSyncStatus('warning', 'No sync performed yet');
            }
            
            // Add file count information if available
            if (data.files_to_process && data.files_to_process > 0) {
                statusText.textContent += ` (${data.files_to_process} files ready)`;
            }
        } else {
            // Not connected to Dropbox
            updateSyncStatus('error', 'Dropbox not connected');
        }
    } catch (error) {
        // Clear the timeout to avoid memory leaks
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
            console.error('Sync status check timed out');
            updateSyncStatus('error', 'Connection timeout');
        } else {
            console.error('Error checking sync status:', error);
            updateSyncStatus('error', 'Connection error');
        }
    }
}

// Function to update sync status UI with defensive checks
function updateSyncStatus(status, message) {
    const statusIndicator = document.querySelector('.sync-indicator');
    const statusText = document.querySelector('.sync-text');
    
    if (!statusIndicator || !statusText) {
        console.warn('Sync status elements not found');
        return;
    }
    
    // Remove all status classes
    statusIndicator.classList.remove('bg-green-500', 'bg-yellow-500', 'bg-red-500', 'bg-gray-400');
    
    // Set appropriate status class
    switch (status) {
        case 'success':
            statusIndicator.classList.add('bg-green-500');
            break;
        case 'warning':
            statusIndicator.classList.add('bg-yellow-500');
            break;
        case 'error':
            statusIndicator.classList.add('bg-red-500');
            break;
        default:
            statusIndicator.classList.add('bg-gray-400');
    }
    
    // Set status text
    statusText.textContent = message;
}

// Format time ago with defensive checks
function formatTimeAgo(date) {
    if (!date || !(date instanceof Date) || isNaN(date)) {
        return 'Unknown time';
    }
    
    try {
        const now = new Date();
        const diffMs = now - date;
        const diffSeconds = Math.floor(diffMs / 1000);
        const diffMinutes = Math.floor(diffSeconds / 60);
        const diffHours = Math.floor(diffMinutes / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffDays > 0) {
            return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
        } else if (diffHours > 0) {
            return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
        } else if (diffMinutes > 0) {
            return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
        } else {
            return 'Just now';
        }
    } catch (error) {
        console.error('Error formatting time:', error);
        return 'Unknown time';
    }
}

// Function to manually trigger sync - properly debounced and with timeout
async function manualSync(event) {
    if (event) {
        event.preventDefault();
    }
    
    // Get the button carefully
    const button = event.currentTarget || event.target;
    if (!button) {
        console.error("Button element not found in event");
        return;
    }
    
    console.log("Manual sync triggered");
    
    // Disable the button immediately to prevent double-clicks
    button.disabled = true;
    button.textContent = "Syncing...";
    
    // Get CSRF token with fallback
    let csrfToken = '';
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
        csrfToken = csrfMeta.content;
    } else {
        console.warn("CSRF token not found - request may fail");
    }
    
    // Create an abort controller for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout for sync
    
    try {
        const response = await fetch("/api/trigger-sync", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest"
            },
            signal: controller.signal
        });
        
        // Clear timeout since request completed
        clearTimeout(timeoutId);
        
        console.log("Response status:", response.status);
        
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log("Response data:", data);
        
        // Update status immediately
        updateSyncStatus('success', 'Sync in progress...');
        
        if (data.message) {
            alert(data.message || "Sync started successfully! Check logs for progress.");
        }
        
        // Start polling for updated status - limit to a reasonable number of attempts
        let pollCount = 0;
        const maxPolls = 10;
        const pollInterval = setInterval(() => {
            pollCount++;
            if (pollCount > maxPolls) {
                clearInterval(pollInterval);
                button.disabled = false;
                button.textContent = "Sync Now";
                updateSyncStatus('warning', 'Sync status unknown');
            }
            checkSyncStatus();
        }, 5000);

        // Set a timeout to re-enable button after 60 seconds regardless of polling
        setTimeout(() => {
            if (button.disabled) {
                button.disabled = false;
                button.textContent = "Sync Now";
            }
        }, 60000);
        
    } catch (error) {
        let errorMessage = "Unknown error";
        
        if (error.name === 'AbortError') {
            errorMessage = "Sync request timed out";
        } else {
            errorMessage = error.message || "Error triggering sync";
        }
        
        console.error("Sync error:", errorMessage);
        updateSyncStatus('error', 'Error triggering sync');
        alert(`Error: ${errorMessage}`);
        
        // Re-enable the button
        button.disabled = false;
        button.textContent = "Sync Now";
    }
}

// Expose the manualSync function globally
window.manualSync = manualSync;

// Global error handler for unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    // Prevent the default browser handling to avoid console errors
    event.preventDefault();
});