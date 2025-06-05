// static/js/document-preview-loader.js

document.addEventListener('DOMContentLoaded', function() {
    // Function to load document preview
    function loadDocumentPreview(container, documentId, filename, card, observerInstance) {
      // dataset.loading is true, set by IntersectionObserver callback

      container.innerHTML = `
        <div class="flex items-center justify-center h-full">
          <div class="animate-pulse flex flex-col items-center">
            <div class="h-10 w-10 border-4 border-t-blue-500 border-blue-200 rounded-full animate-spin mb-2"></div>
            <p class="text-sm text-gray-500">Loading preview...</p>
          </div>
        </div>
      `;
      
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
            container.dataset.loading = 'false';
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
            container.dataset.loading = 'false';
            observerInstance.unobserve(card);
          } else {
            console.warn(`No preview or fallback from initial API for docId: ${documentId}, filename: ${filename}. Data:`, data);
            throw new Error('No preview or fallback URL from initial API.'); // Trigger .catch
          }
        })
        .catch(error => { // Catches errors from primary fetch chain
          console.error('Initial error or no preview from API:', error);
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
                console.warn(`Fallback URL not provided for docId: ${documentId}, filename: ${filename}.`);
                container.innerHTML = `<div class="p-4 text-center text-sm text-gray-500">Preview unavailable.</div>`;
              }
            })
            .catch(fallbackError => {
              console.error('Error loading direct URL fallback:', fallbackError);
              container.innerHTML = `<div class="p-4 text-center text-sm text-red-600">Preview unavailable. Error during fallback.</div>`;
            })
            .finally(() => {
              // This finally is for the fallback fetch chain.
              // Regardless of fallback success or failure, the loading attempt for this card is over.
              container.dataset.loading = 'false';
            });
        });
    }

    // Initialize Intersection Observer
    const previewObserver = new IntersectionObserver(
      (entries, observerInstance) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const card = entry.target;
            const previewContainer = card.querySelector('.preview-container');
            
            if (previewContainer && 
                previewContainer.dataset.loaded !== 'true' && 
                previewContainer.dataset.loading !== 'true') {
                  
              const documentId = previewContainer.dataset.documentId;
              const filename = previewContainer.dataset.filename;

              if (documentId && filename) {
                previewContainer.dataset.loading = 'true'; 
                loadDocumentPreview(previewContainer, documentId, filename, card, observerInstance);
              } else {
                console.warn('Missing documentId or filename for preview. Unobserving.', previewContainer.dataset);
                observerInstance.unobserve(card); // Unobserve if data is bad to prevent loops
                if(previewContainer) previewContainer.dataset.loading = 'false'; // Clear loading if we unobserve due to bad data
              }
            } else if (previewContainer && previewContainer.dataset.loaded === 'true') {
              observerInstance.unobserve(card); // Already loaded, ensure it's unobserved
            }
          }
        });
      },
      {
        rootMargin: '200px', // Load when card is 200px away from viewport
        threshold: 0.01     // Trigger if even 1% of the card is visible
      }
    );

    const observeCard = (cardElement) => {
        if (cardElement.nodeType === 1 && cardElement.matches && cardElement.matches('.document-card')) {
            const previewContainer = cardElement.querySelector('.preview-container');
            // Only observe if it has a preview container and hasn't been passed to observer yet
            if (previewContainer && previewContainer.dataset.observedByLoader !== 'true') {
                 previewObserver.observe(cardElement);
                 previewContainer.dataset.observedByLoader = 'true'; 
            }
        }
    };

    // Function to initialize observation for existing cards
    const initObservationForExistingCards = () => {
        document.querySelectorAll('.document-card').forEach(observeCard);
    };

    // Observe cards after the entire page (including styles and images) has loaded
    if (document.readyState === 'complete') {
        initObservationForExistingCards();
    } else {
        window.addEventListener('load', initObservationForExistingCards);
    }

    // Setup MutationObserver to watch for dynamically added cards
    // Target a specific container if known, otherwise fall back to document.body
    const targetNodeForMutations = document.getElementById('search-results-container') || 
                                   document.getElementById('document-list-container') || // Common alternative ID
                                   document.body; 
    
    const domMutationObserver = new MutationObserver((mutationsList) => {
        for (const mutation of mutationsList) {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) { // Check if it's an element node
                        observeCard(node); // Check if the added node itself is a card
                        // Also check for document-card descendants if a wrapper element was added
                        node.querySelectorAll('.document-card').forEach(observeCard);
                    }
                });
            }
        }
    });
    domMutationObserver.observe(targetNodeForMutations, { childList: true, subtree: true });

    // General fallback for images with class 'preview-image' that might exist outside this loader's scope
    // Note: loadDocumentPreview sets its own onerror handler for the images it creates.
    document.querySelectorAll('img.preview-image').forEach(img => {
      if (!img.onerror) { // Avoid overriding specific onerror handlers
        img.onerror = function() {
          this.onerror = null; // Prevent infinite loop if placeholder also fails
          this.src = '/api/placeholder-image'; 
        };
      }
    });
});
