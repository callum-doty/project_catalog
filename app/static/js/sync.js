// static/js/sync.js

document.addEventListener('DOMContentLoaded', function() {
    // Initialize sync status check
    checkSyncStatus();
    
    // Set up periodic sync status checks
    setInterval(checkSyncStatus, 60000); // Check every minute
});

// Function to check sync status
async function checkSyncStatus() {
    try {
        const response = await fetch('/api/sync-status');
        
        if (!response.ok) {
            updateSyncStatus('error', 'Error checking sync status');
            return;
        }
        
        const data = await response.json();
        console.log('Sync status:', data);
        
        // Update sync indicator
        const statusIndicator = document.querySelector('.sync-indicator');
        const statusText = document.querySelector('.sync-text');
        
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
        console.error('Error checking sync status:', error);
        updateSyncStatus('error', 'Error checking sync status');
    }
}

// Function to update sync status UI
function updateSyncStatus(status, message) {
    const statusIndicator = document.querySelector('.sync-indicator');
    const statusText = document.querySelector('.sync-text');
    
    if (!statusIndicator || !statusText) {
        console.error('Sync status elements not found');
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

// Format time ago
function formatTimeAgo(date) {
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
}

// Function to manually trigger sync
async function manualSync(event) {
    event.preventDefault();
    console.log("Manual sync triggered");

    const button = event.target;
    button.disabled = true;
    button.textContent = "Syncing...";

    try {
        const response = await fetch("/api/trigger-sync", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content,
            },
        });

        console.log("Response status:", response.status);
        const data = await response.json();
        console.log("Response data:", data);

        if (response.ok) {
            // Update status immediately
            updateSyncStatus('success', 'Sync in progress...');
            alert("Sync started successfully! Check logs for progress.");
            
            // Start polling for updated status
            let pollCount = 0;
            const maxPolls = 10;
            const pollInterval = setInterval(() => {
                pollCount++;
                if (pollCount > maxPolls) {
                    clearInterval(pollInterval);
                }
                checkSyncStatus();
            }, 5000);
        } else {
            updateSyncStatus('error', `Error: ${data.message}`);
            alert("Error: " + data.message);
        }
    } catch (error) {
        console.error("Sync error:", error);
        updateSyncStatus('error', 'Error triggering sync');
        alert("Error triggering sync");
    } finally {
        button.disabled = false;
        button.textContent = "Sync Now";
    }
}

// Expose the manualSync function globally
window.manualSync = manualSync;