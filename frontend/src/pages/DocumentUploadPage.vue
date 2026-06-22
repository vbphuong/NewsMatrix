<script setup>
import { onMounted, ref } from 'vue';

import { fetchDocuments, uploadDocument, deleteDocument } from '../lib/backend-documents';
import '../assets/document-upload-page.css';

const documents = ref([]);
const selectedFile = ref(null);
const loading = ref(false);
const error = ref('');
const success = ref('');

function onFileChange(event) {
  const [file] = event.target.files ?? [];
  selectedFile.value = file ?? null;
  error.value = '';
  success.value = '';
}

async function loadDocuments() {
  loading.value = true;
  error.value = '';

  try {
    documents.value = await fetchDocuments();
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Failed to load documents';
  } finally {
    loading.value = false;
  }
}

async function handleUpload() {
  if (!selectedFile.value) {
    error.value = 'Choose a PDF file first.';
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    const uploadedDocument = await uploadDocument(selectedFile.value);
    success.value = `${uploadedDocument.file_name} uploaded successfully and produced ${uploadedDocument.total_chunk} chunks.`;
    selectedFile.value = null;
    await loadDocuments();
  } catch (uploadError) {
    error.value = uploadError instanceof Error ? uploadError.message : 'Failed to upload document';
  } finally {
    loading.value = false;
  }
}

async function handleDelete(documentId, fileName) {
  if (!window.confirm(`Are you sure you want to delete "${fileName}" and all of its chunks? This action cannot be undone.`)) {
    return;
  }

  loading.value = true;
  error.value = '';
  success.value = '';

  try {
    const res = await deleteDocument(documentId);
    success.value = res.message || 'Document deleted successfully.';
    await loadDocuments();
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : 'Failed to delete document';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadDocuments();
});
</script>

<template>
  <section class="page document-upload-page">
    <div class="page__hero document-upload-hero">
      <span class="page__kicker">Admin tools</span>
      <h1 class="page__title">Document ingestion.</h1>
      <p class="page__copy">
        Upload a PDF and the backend will push it to Supabase Storage bucket <strong>raw_data</strong>, then run the chunking pipeline and persist <strong>documents</strong> and <strong>chunks</strong>.
      </p>
    </div>

    <div class="document-upload-grid">
      <article class="panel panel--soft document-upload-panel">
        <div class="document-upload-panel__head">
          <div>
            <h2 class="panel__title">Upload PDF</h2>
            <p class="panel__meta">Files are stored under a document-specific path inside the bucket.</p>
          </div>
        </div>

        <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
        <p v-if="success" class="panel__notice notice--success">{{ success }}</p>

        <div class="document-dropzone" :class="{ 'document-dropzone--filled': selectedFile }">
          <label class="document-dropzone__label">
            <input class="document-dropzone__input" type="file" accept="application/pdf,.pdf" @change="onFileChange" />
            <span class="document-dropzone__title">{{ selectedFile ? selectedFile.name : 'Choose a PDF' }}</span>
            <span class="document-dropzone__copy">{{ selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB` : 'PDF only, processed automatically after upload.' }}</span>
          </label>
        </div>

        <div class="document-upload-actions">
          <button class="btn btn--primary" type="button" :disabled="loading" @click="handleUpload">
            {{ loading ? 'Processing...' : 'Upload and process' }}
          </button>
          <button class="btn" type="button" :disabled="loading" @click="loadDocuments">Refresh list</button>
        </div>
      </article>

      <article class="panel panel--soft document-history-panel">
        <div class="document-upload-panel__head">
          <div>
            <h2 class="panel__title">Uploaded documents</h2>
            <p class="panel__meta">{{ documents.length }} records</p>
          </div>
        </div>

        <div class="document-list">
          <article v-for="document in documents" :key="document.document_id" class="document-item">
            <div class="document-item__details">
              <h3 class="document-item__title" :title="document.file_name">{{ document.file_name }}</h3>
              <p class="document-item__meta">
                {{ document.total_page }} pages | {{ document.total_chunk }} chunks | {{ document.file_type }}
              </p>
              <p class="document-item__path">{{ document.file_path }}</p>
              <time v-if="document.created_at" class="document-item__date">{{ new Date(document.created_at).toLocaleString() }}</time>
            </div>
            <div class="document-item__actions">
              <button
                class="btn btn--danger btn--small"
                type="button"
                :disabled="loading"
                @click="handleDelete(document.document_id, document.file_name)"
              >
                Delete
              </button>
            </div>
          </article>
        </div>
      </article>
    </div>
  </section>
</template>