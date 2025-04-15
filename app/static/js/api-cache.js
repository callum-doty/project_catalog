// api-cache.js

class APICache {
    constructor(maxAge = 60000) { // Default cache lifetime: 1 minute
      this.cache = {};
      this.maxAge = maxAge;
    }
    
    async fetch(url, options = {}) {
      const cacheKey = url;
      const now = Date.now();
      
      // Check if we have a valid cached response
      if (this.cache[cacheKey] && now - this.cache[cacheKey].timestamp < this.maxAge) {
        return Promise.resolve(this.cache[cacheKey].data);
      }
      
      // Fetch fresh data
      try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        // Store in cache
        this.cache[cacheKey] = {
          timestamp: now,
          data: data
        };
        
        return data;
      } catch (error) {
        console.error('API fetch error:', error);
        throw error;
      }
    }
    
    clear() {
      this.cache = {};
    }
  }
  
  // Create global instance
  window.apiCache = new APICache();