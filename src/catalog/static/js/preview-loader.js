// static/js/document-preview-loader.js

document.addEventListener('DOMContentLoaded', function() {
    // Find all document cards
    const documentCards = document.querySelectorAll('.document-card');
    
    // Initialize Intersection Observer for lazy loading previews
    const previewObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const card = entry.target;
            
            // Find preview container within this card
            const previewImg = card.querySelector('.preview-image');
            const previewContainer = card.querySelector('.preview-container');
            
            // Load preview if needed
            if (previewContainer && previewContainer.dataset.loaded === 'false') {
              const filename = previewContainer.dataset.filename;
              if (filename) {
                loadDocumentPreview(previewContainer, filename);
                previewContainer.dataset.loaded = 'true';
              }
            }
            
            // Stop observing this card once its preview is loaded
            previewObserver.unobserve(card);
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
    function loadDocumentPreview(container, filename) {
      // Store the original content for fallback
      const originalContent = container.innerHTML;
      
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
      fetch(`/api/preview/${encodeURIComponent(filename)}`)
        .then(response => {
          if (!response.ok) {
            throw new Error(`Preview fetch failed: ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          if (data.status === 'fallback_redirect' && data.url) {
            console.log(`Using PDF fallback for ${filename}: ${data.url}`);
            // Embed PDF using <object> tag or provide download link
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
          } else if (data.preview) {
            // Show the image preview with fade-in effect
            container.innerHTML = `
              <img 
                src="${data.preview}" 
                alt="Preview of ${filename}" 
                class="w-full h-full object-contain fade-in"
                onerror="this.onerror=null; this.src='/api/placeholder-image';"
              >
            `;
          } else {
            // No preview available, restore original or show a generic placeholder
            console.warn(`No preview or fallback for ${filename}. Data:`, data);
            container.innerHTML = originalContent; // Or a more specific placeholder
          }
        })
        .catch(error => {
          console.error('Initial error loading preview:', error);
          // Log the filename being used for the fallback
          console.log('[Fallback] Filename value:', filename);
          console.log('[Fallback] Encoded filename value:', encodeURIComponent(filename));
          // Attempt to load direct URL as a fallback
          fetch(`/search/fallback_to_direct_url?filename=${encodeURIComponent(filename)}`)
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
                    <p class="mb-2 text-sm text-red-600">Preview generation failed.</p>
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
              } else {
                throw new Error('Fallback URL not provided in response.');
              }
            })
            .catch(fallbackError => {
              console.error('Error loading direct URL fallback:', fallbackError);
              // Restore original content or show a generic error message if fallback also fails
              container.innerHTML = `
                <div class="flex flex-col items-center justify-center h-full p-4 text-center">
                  <p class="mb-2 text-sm text-red-600">Preview unavailable.</p>
                  <p class="text-xs text-gray-500">Could not load preview or direct link.</p>
                </div>
              `;
            });
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
