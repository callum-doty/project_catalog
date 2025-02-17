// static/js/search.js

document.getElementById('searchForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const query = new FormData(this).get('q');
    try {
        const response = await fetch(`/search?q=${encodeURIComponent(query)}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const results = await response.json();
        updateResults(results);
    } catch (error) {
        console.error('Search error:', error);
    }
});

function updateResults(results) {
    const grid = document.getElementById('resultsGrid');
    
    if (!results.length) {
        grid.innerHTML = `
            <div class="col-span-full text-center py-8">
                <p class="text-gray-500">No documents found</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = results.map(doc => `
        <div class="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow">
            <div class="w-full h-48 bg-gray-100 flex items-center justify-center">
                ${doc.preview 
                    ? `<img src="${doc.preview}" 
                           alt="Preview of ${doc.filename}" 
                           class="w-full h-full object-contain">`
                    : `<div class="flex flex-col items-center text-gray-400">
                           <svg class="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                               <path stroke-linecap="round" 
                                     stroke-linejoin="round" 
                                     stroke-width="2" 
                                     d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                           </svg>
                           <span>No preview available</span>
                       </div>`
                }
            </div>
            
            <div class="p-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">${doc.filename}</h3>
                <p class="text-sm text-gray-500 mb-4">Uploaded: ${doc.upload_date}</p>
                
                <div class="mb-4">
                    <h4 class="text-sm font-medium text-gray-700 mb-1">Summary</h4>
                    <p class="text-sm text-gray-600 line-clamp-3">${doc.summary}</p>
                </div>
                
                ${doc.keywords?.length ? `
                    <div>
                        <h4 class="text-sm font-medium text-gray-700 mb-1">Keywords</h4>
                        <div class="flex flex-wrap gap-2">
                            ${doc.keywords.map(keyword => `
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                    ${keyword.text}
                                    ${keyword.category 
                                        ? `<span class="ml-1 text-blue-600">(${keyword.category})</span>` 
                                        : ''
                                    }
                                </span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        </div>
    `).join('');
}

// Update document count
function updateDocumentCount(count) {
    const countElement = document.querySelector('.document-count');
    if (countElement) {
        countElement.textContent = `Found ${count} document${count !== 1 ? 's' : ''}`;
    }
}