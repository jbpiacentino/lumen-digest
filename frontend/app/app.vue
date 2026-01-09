<template>
  <div class="min-h-screen bg-gray-100 flex flex-col">
    <!-- Top Navigation -->
    <header class="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
      <div class="flex items-center gap-4">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight">Lumen Digest</h1>
        <div v-if="articles.length > 0" class="flex gap-2">
          <span class="px-2 py-1 bg-gray-100 text-gray-600 text-xs font-medium rounded">
            {{ articles.length }} Total Articles
          </span>
          <span :class="['px-2 py-1 text-xs font-medium rounded', uncategorizedCount > 0 ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600']">
            {{ uncategorizedCount }} Uncategorized
          </span>
        </div>
      </div>
      
      <button 
        @click="syncDigest" 
        :disabled="loading"
        class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-all"
      >
        <span v-if="loading" class="animate-spin mr-2">🔄</span>
        {{ loading ? 'Processing...' : 'Sync & Classify' }}
      </button>
    </header>

    <div class="flex-1 flex overflow-hidden">
      <!-- Sidebar Navigation -->
      <aside class="w-64 bg-white border-r border-gray-200 overflow-y-auto hidden md:block">
        <nav class="p-4 space-y-1">
          <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest px-3 mb-2">Categories</p>
          
          <button 
            @click="activeCategory = 'all'"
            :class="['w-full flex justify-between items-center px-3 py-2 text-sm font-medium rounded-md transition-colors', activeCategory === 'all' ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50']"
          >
            <span>All Articles</span>
            <span class="text-xs bg-gray-200 text-gray-800 px-2 rounded-full">{{ articles.length }}</span>
          </button>

          <button 
            v-for="(count, catId) in categoryStats" 
            :key="catId"
            @click="activeCategory = catId"
            :class="[
              'w-full flex justify-between items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
              activeCategory === catId ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50',
              cat === 'Uncategorized' && count > 0 ? 'text-red-600 font-bold' : ''
            ]"
          >
            <span class="truncate pr-2">{{ categoryLabel(catId) }}</span>
            <span :class="['text-xs px-2 rounded-full', cat === 'Uncategorized' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700']">
              {{ count }}
            </span>
          </button>
        </nav>
      </aside>

      <!-- Main Content -->
      <main class="flex-1 overflow-y-auto bg-gray-50 p-6">
        
        <!-- Loading -->
        <div v-if="loading" class="flex flex-col items-center justify-center h-64 text-gray-500">
          <div class="animate-bounce text-4xl mb-4">🤖</div>
          <p class="italic text-lg">Lumen AI is reading and sorting your news...</p>
        </div>

        <!-- Feed -->
        <div v-else-if="filteredArticles.length > 0" class="max-w-3xl mx-auto space-y-6">
          <div v-for="article in filteredArticles" :key="article.id" class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden hover:border-indigo-300 transition-colors">
            <div class="p-6">
              <div class="flex justify-between items-start gap-4">
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-2">
                    <span :class="['text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full border', (article.category_id || 'uncategorized') === 'uncategorized' ? 'bg-red-50 text-red-600 border-red-100' : 'bg-indigo-50 text-indigo-600 border-indigo-100']">
                      {{ categoryLabel(article.category_id || 'uncategorized') }}
                    </span>
                    <span class="text-gray-400 text-[10px]">{{ new Date(article.published_at * 1000).toLocaleDateString() }}</span>
                  </div>
                  <a :href="article.url" target="_blank" class="text-lg font-bold text-gray-900 hover:text-indigo-600 leading-snug">
                    {{ article.title }}
                  </a>
                </div>
              </div>

              <!-- OpenAI Summary -->
              <div class="mt-4 text-gray-700 text-sm leading-relaxed">
                <div v-html="formatSummary(article.summary)" class="prose prose-sm prose-indigo custom-summary"></div>
              </div>

              <div class="mt-4 pt-4 border-t border-gray-50 flex justify-end">
                <a :href="article.url" target="_blank" class="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center">
                  Full Article 
                  <svg class="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                </a>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="text-center py-20 bg-white rounded-xl border-2 border-dashed border-gray-200 max-w-3xl mx-auto">
          <p class="text-gray-400">No articles found in this category.</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
const config = useRuntimeConfig();
const articles = ref([]);
const loading = ref(false);
const activeCategory = ref('all');
const lang = ref('en');
const categoryLabels = ref({});

// Infer UI language (simple heuristic). You can later replace this with a proper i18n switch.
onMounted(async () => {
  try {
    const navLang = (navigator.language || 'en').toLowerCase();
    if (navLang.startsWith('fr')) lang.value = 'fr';
    else lang.value = 'en';
  } catch (_) {
    lang.value = 'en';
  }
  await loadCategories();
});

// Simple stats for the sidebar
const categoryStats = computed(() => {
  const stats = {};
  articles.value.forEach(a => {
    const id = a.category_id || 'uncategorized';
    stats[id] = (stats[id] || 0) + 1;
  });
  return stats;
});

const uncategorizedCount = computed(() => categoryStats.value['uncategorized'] || 0);

// Filtering logic
const filteredArticles = computed(() => {
  if (activeCategory.value === 'all') return articles.value;
  return articles.value.filter(a => (a.category_id || 'uncategorized') === activeCategory.value);
});

function categoryLabel(categoryId) {
  return categoryLabels.value[categoryId] || categoryId;
}

async function loadCategories() {
  try {
    categoryLabels.value = await $fetch(`${config.public.apiBase}/digest/categories?lang=${lang.value}`);
  } catch (err) {
    // Non-fatal: the UI can fall back to category_id
    categoryLabels.value = {};
    console.warn('Failed to load category labels:', err);
  }
}

async function syncDigest() {
  loading.value = true;
  try {
    await loadCategories();
    // Increased limit to 50 for a better birds-eye view
    const data = await $fetch(`${config.public.apiBase}/digest/sync?limit=50`);
    articles.value = data.articles;
    // Switch to Uncategorized view if there are many, to help you fix them
    if (uncategorizedCount.value > 0) {
      activeCategory.value = 'uncategorized';
    }
  } catch (err) {
    alert("Error: " + err.message);
  } finally {
    loading.value = false;
  }
}

function formatSummary(text) {
  if (!text) return "";
  // More robust bullet point formatting
  let formatted = text.trim();
  if (formatted.includes('- ') || formatted.includes('* ')) {
    formatted = formatted.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>');
    return `<ul class="list-disc pl-5 space-y-1">${formatted}</ul>`;
  }
  return formatted;
}
</script>

<style>
.custom-summary ul {
  list-style-type: disc;
}
.custom-summary li::marker {
  color: #6366f1; /* indigo-500 */
}
</style>