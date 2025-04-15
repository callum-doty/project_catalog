// preview-loader.js

document.addEventListener('DOMContentLoaded', function() {
    // Find all preview placeholders
    const previewContainers = document.querySelectorAll('.document-preview-container');
    
    previewContainers.forEach(container => {
        const filename = container.dataset.filename;
        if (container.querySelector('.preview-placeholder')) {
            // This preview is not yet available, poll for it
            checkPreviewStatus(container, filename);
        }
    });
    
    function checkPreviewStatus(container, filename) {
        // Poll every 3 seconds
        const intervalId = setInterval(() => {
            fetch(`/api/preview-status/${encodeURIComponent(filename)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'available') {
                        // Preview is now available, update the container
                        container.innerHTML = `<img src="${data.preview_url}" alt="Preview of ${filename}" class="document-preview">`;
                        clearInterval(intervalId); // Stop polling
                    }
                })
                .catch(error => console.error('Error checking preview status:', error));
        }, 3000);
        
        // Stop polling after 30 seconds (10 attempts) to avoid infinite polling
        setTimeout(() => {
            clearInterval(intervalId);
        }, 30000);
    }
});