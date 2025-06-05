// static/js/document-preview-loader.js

document.addEventListener('DOMContentLoaded', function() {
    // Find all document cards
    const documentCards = document.querySelectorAll('.document-card');
    
    // Initialize Intersection Observer for lazy loading previews
    const previewObserver = new IntersectionObserver(
      (entries, observerInstance) => { // observerInstance is the observer itself
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const card = entry.target;
            const previewContainer = card.querySelector('.preview-container');
            
            // Check if not already loaded and not currently attempting to load
            if (previewContainer && 
                previewContainer.dataset.loaded !== 'true' && 
                previewContainer.dataset.loading !== 'true') {
                  
              const documentId = previewContainer.dataset.documentId;
              const filename = previewContainer.dataset.filename;

              if (documentId && filename) {
                // Pass card and observerInstance to handle unobserving on success
                loadDocumentPreview(previewContainer, documentId, filename, card, observerInstance);
              } else {
                console.warn('Missing documentId or filename for preview. Unobserving to prevent loops.', previewContainer.dataset);
                observerInstance.unobserve(card); // Unobserve if data is bad
              }
            } else if (previewContainer && previewContainer.dataset.loaded === 'true') {
              // If it's already successfully loaded, ensure it's unobserved
              observerInstance.unobserve(card);
            }
          }
        });
      },
      {
        rootMargin: '100px', // Start loading when document card is within 100px of viewport
        threshold: 0.1
      }
    );
    
    // Start observing all document cards
    documentCards.forEach(card => {
      previewObserver.observe(card);
    });
    
    // Function to load document preview
    function loadDocumentPreview(container, documentId, filename, card, observerInstance) {
      // Store the original content for fallback if all attempts fail
      const originalContent = container.innerHTML; 
      container.dataset.loading = 'true'; // Mark as attempting to load
      
      // Show loading indicator
      container.innerHTML = `
        <div class="flex items-center justify-center h-full">
          <div class="animate-pulse flex flex-col items-center">
            <div class="h-10 w-10 border-4 border-t-blue-500 border-blue-200 rounded-full animate-spin mb-2"></div>
            <p class="text-sm text-gray-500">Loading preview...</p>
          </div>
        </div>
      `;
      
      // Fetch preview from API
      fetch(`/api/preview/${documentId}/${encodeURIComponent(filename)}`)
        .then(response => {
          if (!response.ok) {
            throw new Error(`Preview fetch failed: ${response.status} for docId: ${documentId}, filename: ${filename}`);
          }
          return response.json();
        })
        .then(data => {
          if (data.status === 'fallback_redirect' && data.url) {
            console.log(`Using PDF fallback for docId: ${documentId}, filename: ${filename}: ${data.url}`);
            container.innerHTML = `
              <object data="${data.url}" type="application/pdf" class="w-full h-full">
                <div class="flex flex-col items-center justify-center h-full p-4 text-center">
                  <p class="mb-2 text-sm text-gray-600">Cannot display PDF preview directly in this browser.</p>
                  <a 
                    href="${data.url}" 
                    download="${data.filename || 'document.pdf'}" 
                    class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors text-sm"
                  >
                    Download PDF: ${data.filename || 'document.pdf'}
                  </a>
                </div>
              </object>
            `;
            container.dataset.loaded = 'true';
            observerInstance.unobserve(card);
          } else if (data.status === 'success' && data.url) {
            container.innerHTML = `
              <img 
                src="${data.url}"
                alt="Preview of ${filename}" 
                class="w-full h-full object-contain fade-in"
                onerror="this.onerror=null; this.src='/api/placeholder-image';"
              >
            `;
            container.dataset.loaded = 'true';
            observerInstance.unobserve(card);
          } else {
            // No preview available from initial API call, do not unobserve yet.
            // Error will be caught by .catch block to try direct URL fallback.
            console.warn(`No preview or fallback from initial API for docId: ${documentId}, filename: ${filename}. Data:`, data);
            throw new Error('No preview or fallback URL from initial API.'); // Trigger .catch
          }
        })
        .catch(error => { // Catches errors from fetch() or the .then() block above
          console.error('Initial error or no preview from API:', error);
          console.log(`[Fallback Attempt] Document ID: ${documentId}, Filename: ${filename}`);
          
          fetch(`/search/fallback_to_direct_url?document_id=${documentId}&filename=${encodeURIComponent(filename)}`)
            .then(fallbackResponse => {
              if (!fallbackResponse.ok) {
                throw new Error(`Fallback fetch failed: ${fallbackResponse.status}`);
              }
              return fallbackResponse.json();
            })
            .then(fallbackData => {
              if (fallbackData.direct_url) {
                console.log(`Using direct URL fallback for ${filename}: ${fallbackData.direct_url}`);
                container.innerHTML = `
                  <div class="flex flex-col items-center justify-center h-full p-4 text-center">
                    <p class="mb-2 text-sm text-red-600">Preview generation may have failed.</p>
                    <a 
                      href="${fallbackData.direct_url}" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors text-sm"
                    >
                      Open Original File: ${filename}
                    </a>
                  </div>
                `;
                container.dataset.loaded = 'true'; // Considered "loaded" as we provided a link
                observerInstance.unobserve(card);
              } else {
                // Fallback URL not provided, restore original content or show generic error
                console.warn(`Fallback URL not provided for docId: ${documentId}, filename: ${filename}.`);
                container.innerHTML = `
                  <div class="flex flex-col items-center justify-center h-full p-4 text-center">
                    <p class="mb-2 text-sm text-red-600">Preview unavailable.</p>
                    <p class="text-xs text-gray-500">Could not load preview or direct link.</p>
                  </div>
                `;
                // Do NOT set loaded=true, do NOT unobserve. Allow re-attempts.
              }
            })
            .catch(fallbackError => {
              console.error('Error loading direct URL fallback:', fallbackError);
              container.innerHTML = `
                <div class="flex flex-col items-center justify-center h-full p-4 text-center">
                  <p class="mb-2 text-sm text-red-600">Preview unavailable.</p>
                  <p class="text-xs text-gray-500">Could not load preview or direct link.</p>
                </div>
              `;
              // Do NOT set loaded=true, do NOT unobserve. Allow re-attempts.
            })
            .finally(() => {
              container.dataset.loading = 'false'; // Clear loading flag after fallback attempt
            });
        })
        .finally(() => {
          // This finally block is for the primary fetch. 
          // If an error occurred and we went to the fallback, 
          // the loading flag is handled by the fallback's finally.
          // If primary fetch succeeded, we need to clear loading here.
          if (container.dataset.loaded === 'true') { // Only clear if successfully loaded by primary
             container.dataset.loading = 'false';
          }
          // If primary fetch failed and went to .catch, the .catch's .finally will handle it.
        });
    }
    
    // Handle placeholder fallbacks
    document.querySelectorAll('.preview-image').forEach(img => {
      img.onerror = function() {
        this.onerror = null;
        this.src = '/api/placeholder-image'; // Updated to API endpoint
      };
    });
  });
