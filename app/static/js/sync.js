// static/js/sync.js

async function manualSync(event) {
    event.preventDefault();
    const button = event.target;
    button.disabled = true;
    button.textContent = "Syncing...";

    try {
        const response = await fetch("/api/sync-dropbox", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document
                    .querySelector('meta[name="csrf-token"]')
                    .content,
            },
        });

        const data = await response.json();
        
        if (response.ok) {
            // Update sync status indicator
            const indicator = document.querySelector('.sync-indicator');
            const statusText = document.querySelector('.sync-text');
            
            indicator.classList.remove('bg-gray-400', 'bg-red-500');
            indicator.classList.add('bg-green-500');
            statusText.textContent = 'Sync started successfully';
            
            setTimeout(() => {
                updateSyncStatus();
            }, 5000); // Check status again after 5 seconds
        } else {
            throw new Error(data.message || 'Sync failed');
        }
    } catch (error) {
        console.error("Sync error:", error);
        // Update sync status indicator to show error
        const indicator = document.querySelector('.sync-indicator');
        const statusText = document.querySelector('.sync-text');
        
        indicator.classList.remove('bg-gray-400', 'bg-green-500');
        indicator.classList.add('bg-red-500');
        statusText.textContent = 'Sync failed';
    } finally {
        button.disabled = false;
        button.textContent = "Sync Now";
    }
}

async function updateSyncStatus() {
    try {
        const response = await fetch('/api/sync-status');
        const data = await response.json();
        
        const indicator = document.querySelector('.sync-indicator');
        const statusText = document.querySelector('.sync-text');
        
        if (data.dropbox_connected) {
            indicator.classList.remove('bg-gray-400', 'bg-red-500');
            indicator.classList.add('bg-green-500');
            statusText.textContent = `Last sync: ${data.last_sync_time || 'Never'}`;
        } else {
            indicator.classList.remove('bg-gray-400', 'bg-green-500');
            indicator.classList.add('bg-red-500');
            statusText.textContent = 'Not connected';
        }
    } catch (error) {
        console.error('Error checking sync status:', error);
    }
}

// Check sync status periodically
updateSyncStatus();
setInterval(updateSyncStatus, 60000); // Check every minute