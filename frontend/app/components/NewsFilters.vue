<template>
  <div class="space-y-3">
    <div class="relative w-full">
      <MagnifyingGlassIcon class="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
      <input
        id="news-search"
        v-model="searchModel"
        type="text"
        class="input input-sm input-bordered w-full pl-9 pr-8"
        placeholder="Search"
      />
      <button
        class="btn btn-circle btn-xs absolute right-2 top-1/2 -translate-y-1/2 transition-opacity"
        type="button"
        @click="searchModel = ''"
        aria-label="Clear search"
        :class="searchModel ? 'opacity-100' : 'opacity-0 pointer-events-none'"
      >
        <XMarkIcon class="w-3.5 h-3.5" />
      </button>
    </div>
    <div class="flex items-center gap-2 flex-wrap">
      <label for="lang-filter" class="text-xs font-medium text-gray-500">Lang</label>
      <select
        id="lang-filter"
        v-model="languageModel"
        class="text-xs rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      >
        <option value="">All</option>
        <option v-for="langOption in languageOptions" :key="langOption" :value="langOption">
          {{ langOption.toUpperCase() }}
        </option>
      </select>
      <label for="source-filter" class="text-xs font-medium text-gray-500">Source</label>
      <select
        id="source-filter"
        v-model="sourceModel"
        class="text-xs rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      >
        <option value="">All</option>
        <option v-for="sourceOption in sourceOptions" :key="sourceOption" :value="sourceOption">
          {{ sourceOption }}
        </option>
      </select>
      <select
        id="time-window"
        v-model="timeWindowModel"
        class="text-xs rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      >
        <option :value="0">All time</option>
        <option :value="1">Last 24 hours</option>
        <option :value="3">Last 3 days</option>
        <option :value="7">Last 7 days</option>
        <option :value="30">Last 30 days</option>
      </select>
      <div class="ml-auto flex items-center gap-2">
        <!-- <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">View</div> -->
        <div class="join">
          <button
            class="btn btn-xs join-item"
            type="button"
            :class="viewModeModel === 'cards' ? 'btn-primary' : 'btn-outline'"
            @click="viewModeModel = 'cards'"
          >
            <Square3Stack3DIcon class="inline-block w-4 h-4" />
          </button>
          <button
            class="btn btn-xs join-item"
            type="button"
            :class="viewModeModel === 'list' ? 'btn-primary' : 'btn-outline'"
            @click="viewModeModel = 'list'"
          >
            <TableCellsIcon class="inline-block w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { MagnifyingGlassIcon, XMarkIcon, Square3Stack3DIcon, TableCellsIcon } from '@heroicons/vue/24/solid';

const props = defineProps({
  searchQuery: { type: String, default: '' },
  languageFilter: { type: String, default: '' },
  sourceFilter: { type: String, default: '' },
  timeWindowDays: { type: Number, default: 0 },
  viewMode: { type: String, default: 'cards' },
  languageOptions: { type: Array, default: () => [] },
  sourceOptions: { type: Array, default: () => [] }
});

const emit = defineEmits([
  'update:searchQuery',
  'update:languageFilter',
  'update:sourceFilter',
  'update:timeWindowDays',
  'update:viewMode'
]);

const searchModel = computed({
  get: () => props.searchQuery,
  set: (value) => emit('update:searchQuery', value)
});

const languageModel = computed({
  get: () => props.languageFilter,
  set: (value) => emit('update:languageFilter', value)
});

const sourceModel = computed({
  get: () => props.sourceFilter,
  set: (value) => emit('update:sourceFilter', value)
});

const timeWindowModel = computed({
  get: () => props.timeWindowDays,
  set: (value) => emit('update:timeWindowDays', value)
});

const viewModeModel = computed({
  get: () => props.viewMode,
  set: (value) => emit('update:viewMode', value)
});
</script>
