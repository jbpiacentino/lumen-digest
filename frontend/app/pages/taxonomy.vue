<template>
  <div class="flex-1 flex overflow-hidden">
    <aside class="w-80 border-r border-gray-200 bg-white overflow-y-auto">
      <div class="p-4 border-b border-gray-200 space-y-3">
        <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Taxonomy</div>
        <div class="flex items-center gap-2">
          <button class="btn btn-xs btn-outline" type="button" @click="loadTaxonomy" :disabled="loading">
            {{ loading ? 'Loading…' : 'Reload' }}
          </button>
          <button class="btn btn-xs btn-outline" type="button" @click="saveTaxonomy" :disabled="saving || !taxonomyData">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
          <button class="btn btn-xs btn-outline" type="button" @click="recalcCentroids" :disabled="recalcPending">
            {{ recalcPending ? 'Recalc…' : 'Recalc centroids' }}
          </button>
        </div>
      </div>
      <div class="p-4 space-y-2">
        <button
          v-for="node in flatNodes"
          :key="node.id"
          class="w-full text-left rounded-lg border border-gray-200 p-3 hover:border-indigo-300 transition-colors"
          :class="selectedId === node.id ? 'bg-indigo-50 border-indigo-300' : 'bg-white'"
          type="button"
          @click="selectNode(node.id)"
        >
          <div class="text-xs font-semibold text-gray-800">
            {{ node.label || node.id }}
          </div>
          <div class="mt-1 text-[11px] text-gray-500">
            {{ node.id }}
          </div>
        </button>
      </div>
    </aside>

    <main class="flex-1 overflow-y-auto bg-gray-50 p-6">
      <ClientOnly>
        <div v-if="!isAuthenticated" class="max-w-3xl mx-auto">
          <div class="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
            <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Access</div>
            <h2 class="mt-2 text-2xl font-bold text-gray-900">Sign in required</h2>
            <p class="mt-3 text-sm text-gray-600 leading-relaxed">
              Please log in to edit taxonomy.
            </p>
          </div>
        </div>

        <div v-else class="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div class="xl:col-span-2 space-y-6">
            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
              <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Category</div>
              <div v-if="selectedNode" class="mt-4 space-y-4">
                <div>
                  <div class="text-[11px] font-semibold text-gray-600">ID</div>
                  <div class="text-sm text-gray-800">{{ selectedNode.id }}</div>
                </div>
                <div>
                  <div class="text-[11px] font-semibold text-gray-600">Label (EN)</div>
                  <input v-model="selectedNode.labels.en" type="text" class="input input-sm input-bordered w-full" />
                </div>
                <div>
                  <div class="text-[11px] font-semibold text-gray-600">Label (FR)</div>
                  <input v-model="selectedNode.labels.fr" type="text" class="input input-sm input-bordered w-full" />
                </div>
              </div>
              <div v-else class="mt-4 text-sm text-gray-500">
                Select a category to edit anchors.
              </div>
            </div>

          <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-4">
            <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Anchors</div>
            <div v-if="selectedNode" class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div class="text-[11px] font-semibold text-gray-600">EN</div>
                <div class="space-y-2 mt-2">
                  <div v-for="(anchor, idx) in selectedNode.anchors.en" :key="`en-${idx}`" class="flex items-center gap-2">
                    <input v-model="selectedNode.anchors.en[idx]" type="text" class="input input-xs input-bordered w-full" />
                    <button class="btn btn-xs btn-ghost" type="button" @click="removeAnchor('en', idx)">Remove</button>
                  </div>
                  <div class="flex items-center gap-2">
                    <input v-model="newAnchor.en" type="text" class="input input-xs input-bordered w-full" placeholder="Add EN anchor" />
                    <button class="btn btn-xs btn-outline" type="button" :disabled="!newAnchor.en.trim()" @click="addAnchor('en')">Add</button>
                  </div>
                </div>
              </div>
              <div>
                <div class="text-[11px] font-semibold text-gray-600">FR</div>
                <div class="space-y-2 mt-2">
                  <div v-for="(anchor, idx) in selectedNode.anchors.fr" :key="`fr-${idx}`" class="flex items-center gap-2">
                    <input v-model="selectedNode.anchors.fr[idx]" type="text" class="input input-xs input-bordered w-full" />
                    <button class="btn btn-xs btn-ghost" type="button" @click="removeAnchor('fr', idx)">Remove</button>
                  </div>
                  <div class="flex items-center gap-2">
                    <input v-model="newAnchor.fr" type="text" class="input input-xs input-bordered w-full" placeholder="Add FR anchor" />
                    <button class="btn btn-xs btn-outline" type="button" :disabled="!newAnchor.fr.trim()" @click="addAnchor('fr')">Add</button>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-gray-500">
              Select a category to edit anchors.
            </div>
          </div>

          <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
            <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Extract anchors</div>
            <div class="flex items-center gap-2">
              <label class="text-[11px] text-gray-500">Lang</label>
              <select v-model="extractLang" class="text-[11px] rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500">
                <option value="en">EN</option>
                <option value="fr">FR</option>
              </select>
              <button class="btn btn-xs btn-outline" type="button" :disabled="extracting || !extractText.trim()" @click="extractAnchors">
                {{ extracting ? 'Extracting…' : 'Extract' }}
              </button>
            </div>
            <textarea
              v-model="extractText"
              class="textarea textarea-bordered w-full text-xs h-32"
              placeholder="Paste article full text here"
            ></textarea>
            <div v-if="extractedAnchors.length" class="flex flex-wrap gap-2">
              <button
                v-for="anchor in extractedAnchors"
                :key="anchor.phrase"
                class="btn btn-xs btn-ghost border border-gray-200"
                type="button"
                :disabled="!selectedNode"
                @click="addExtractedAnchor(anchor.phrase)"
              >
                + {{ anchor.phrase }}
              </button>
            </div>
          </div>
        </div>

        <div class="space-y-6">
          <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Versions</div>
            <div class="mt-3 space-y-2 text-[11px] text-gray-600">
              <div v-for="version in versions" :key="version.name" class="flex items-center justify-between gap-2">
                <div class="truncate">{{ version.name }}</div>
                <div>{{ formatDate(version.modified_at) }}</div>
              </div>
              <div v-if="!versions.length" class="text-gray-400">No versions yet.</div>
            </div>
          </div>
          </div>
        </div>
      </ClientOnly>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';

const config = useRuntimeConfig();
const { authHeaders, isAuthenticated } = useAuth();

const taxonomyData = ref(null);
const loading = ref(false);
const saving = ref(false);
const recalcPending = ref(false);
const versions = ref([]);
const selectedId = ref(null);
const newAnchor = ref({ en: '', fr: '' });
const extractText = ref('');
const extractLang = ref('en');
const extracting = ref(false);
const extractedAnchors = ref([]);

const flatNodes = computed(() => {
  if (!taxonomyData.value) return [];
  const list = [];
  const addNode = (node) => {
    const labels = node.labels || {};
    list.push({
      id: node.id,
      label: labels.en || labels.fr || node.id
    });
  };
  if (taxonomyData.value.taxonomy) {
    taxonomyData.value.taxonomy.forEach(addNode);
  } else if (taxonomyData.value.categories) {
    taxonomyData.value.categories.forEach((node) => {
      addNode(node);
      (node.subcategories || []).forEach(addNode);
    });
  }
  return list;
});

const selectedNode = computed(() => {
  if (!taxonomyData.value || !selectedId.value) return null;
  const findNode = (node) => node.id === selectedId.value;
  if (taxonomyData.value.taxonomy) {
    return taxonomyData.value.taxonomy.find(findNode) || null;
  }
  if (taxonomyData.value.categories) {
    for (const node of taxonomyData.value.categories) {
      if (findNode(node)) return node;
      const sub = (node.subcategories || []).find(findNode);
      if (sub) return sub;
    }
  }
  return null;
});

function normalizeAnchors(node) {
  if (!node.anchors) {
    node.anchors = { en: [], fr: [] };
  }
  if (Array.isArray(node.anchors)) {
    node.anchors = { en: node.anchors, fr: [] };
  }
  node.anchors.en = node.anchors.en || [];
  node.anchors.fr = node.anchors.fr || [];
  node.labels = node.labels || { en: '', fr: '' };
}

function selectNode(id) {
  selectedId.value = id;
  if (selectedNode.value) {
    normalizeAnchors(selectedNode.value);
  }
}

function addAnchor(lang) {
  if (!selectedNode.value) return;
  const value = newAnchor.value[lang].trim();
  if (!value) return;
  normalizeAnchors(selectedNode.value);
  selectedNode.value.anchors[lang].push(value);
  newAnchor.value[lang] = '';
}

function removeAnchor(lang, idx) {
  if (!selectedNode.value) return;
  selectedNode.value.anchors[lang].splice(idx, 1);
}

async function loadTaxonomy() {
  try {
    loading.value = true;
    const data = await $fetch(`${config.public.apiBase}/taxonomy/raw`, { headers: authHeaders.value });
    taxonomyData.value = data?.taxonomy || null;
    if (taxonomyData.value?.taxonomy) {
      taxonomyData.value.taxonomy.forEach(normalizeAnchors);
    }
    if (taxonomyData.value?.categories) {
      taxonomyData.value.categories.forEach((node) => {
        normalizeAnchors(node);
        (node.subcategories || []).forEach(normalizeAnchors);
      });
    }
    selectedId.value = null;
  } finally {
    loading.value = false;
  }
  await loadVersions();
}

async function loadVersions() {
  try {
    const data = await $fetch(`${config.public.apiBase}/taxonomy/versions`, { headers: authHeaders.value });
    versions.value = data?.items || [];
  } catch (_) {
    versions.value = [];
  }
}

async function saveTaxonomy() {
  if (!taxonomyData.value) return;
  try {
    saving.value = true;
    await $fetch(`${config.public.apiBase}/taxonomy/save`, {
      method: 'POST',
      body: { taxonomy: taxonomyData.value },
      headers: authHeaders.value
    });
    await loadVersions();
  } finally {
    saving.value = false;
  }
}

async function recalcCentroids() {
  try {
    recalcPending.value = true;
    await $fetch(`${config.public.apiBase}/taxonomy/reload`, { headers: authHeaders.value });
  } finally {
    recalcPending.value = false;
  }
}

async function extractAnchors() {
  if (!extractText.value.trim()) return;
  try {
    extracting.value = true;
    const data = await $fetch(`${config.public.apiBase}/taxonomy/extract-anchors`, {
      method: 'POST',
      body: { text: extractText.value, language: extractLang.value, top_k: 20 },
      headers: authHeaders.value
    });
    extractedAnchors.value = data?.anchors || [];
  } finally {
    extracting.value = false;
  }
}

function addExtractedAnchor(phrase) {
  if (!selectedNode.value) return;
  normalizeAnchors(selectedNode.value);
  const lang = extractLang.value === 'fr' ? 'fr' : 'en';
  if (!selectedNode.value.anchors[lang].includes(phrase)) {
    selectedNode.value.anchors[lang].push(phrase);
  }
}

function formatDate(value) {
  try {
    return new Date(value).toLocaleString();
  } catch (_) {
    return value;
  }
}

onMounted(async () => {
  if (!isAuthenticated.value) return;
  await loadTaxonomy();
});
</script>
