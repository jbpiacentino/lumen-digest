<template>
  <div class="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-4xl mx-auto">
      
      <!-- Header -->
      <header class="flex justify-between items-center mb-10">
        <div>
          <h1 class="text-3xl font-bold text-gray-900">Lumen Digest</h1>
          <p class="text-gray-600">AI-Powered FreshRSS Intelligence</p>
        </div>
        <button 
          @click="syncDigest" 
          :disabled="loading"
          class="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none disabled:opacity-50 transition-all"
        >
          <span v-if="loading" class="animate-spin mr-2">🔄</span>
          {{ loading ? 'Analyzing Articles...' : 'Sync & Generate' }}
        </button>
      </header>

      <!-- Loading State -->
      <div v-if="loading" class="text-center py-20">
        <div class="text-lg text-gray-500 italic">OpenAI is summarizing and your local ML is classifying entries...</div>
      </div>

      <!-- Article Feed -->
      <div v-else-if="articles.length > 0" class="space-y-8">
        <div v-for="(group, category) in groupedArticles" :key="category">
          <h2 class="text-xs font-semibold uppercase tracking-wider text-indigo-500 mb-4 border-b border-indigo-100 pb-1">
            {{ category }}
          </h2>
          
          <div class="grid gap-6">
            <div v-for="article in group" :key="article.id" class="bg-white overflow-hidden shadow rounded-lg border border-gray-100 hover:shadow-md transition-shadow">
              <div class="px-6 py-5">
                <div class="flex justify-between items-start mb-2">
                  <a :href="article.url" target="_blank" class="text-xl font-semibold text-gray-900 hover:text-indigo-600 leading-tight">
                    {{ article.title }}
                  </a>
                </div>
                
                <!-- OpenAI Summary (Bullet points) -->
                <div class="mt-3 text-gray-700 text-sm prose prose-indigo">
                  <div v-html="formatSummary(article.summary)"></div>
                </div>

                <div class="mt-4 flex items-center text-xs text-gray-400">
                  <span>{{ new Date(article.published_at * 1000).toLocaleDateString() }}</span>
                  <span class="mx-2">•</span>
                  <a :href="article.url" target="_blank" class="underline">View Source</a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-20 bg-white rounded-xl border-2 border-dashed border-gray-200">
        <p class="text-gray-400">No articles fetched yet. Click "Sync" to start.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
const config = useRuntimeConfig();
const articles = ref([]);
const loading = ref(false);

// Group articles by their ML-assigned category
const groupedArticles = computed(() => {
  return articles.value.reduce((acc, obj) => {
    const key = obj.category;
    if (!acc[key]) acc[key] = [];
    acc[key].push(obj);
    return acc;
  }, {});
});

async function syncDigest() {
  loading.value = true;
  try {
    const data = await $fetch(`${config.public.apiBase}/digest/sync?limit=10`);
    articles.value = data.articles;
  } catch (err) {
    alert("Error syncing digest: " + err.message);
  } finally {
    loading.value = false;
  }
}

// Convert OpenAI bullet points into basic HTML
function formatSummary(text) {
  if (!text) return "";
  // Replaces markdown bullets (-) or (*) with HTML bullet points
  return text.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>')
             .replace(/(<li>.*<\/li>)/s, '<ul class="list-disc pl-5">$1</ul>');
}
</script>

<style>
/* Basic styling to make the summaries look clean */
.prose ul { margin-top: 0.5rem; }
.prose li { margin-bottom: 0.25rem; }
</style>
