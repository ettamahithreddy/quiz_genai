/**
 * QuizGen AI - Study Materials Manager
 */

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();
  await loadMaterials();

  document.getElementById('closeMatModalBtn').onclick = () => {
    document.getElementById('materialModal').classList.remove('active');
  };
});

async function loadMaterials() {
  const container = document.getElementById('materialsContainer');

  try {
    const data = await fetchAPI('/api/materials');
    const materials = data.materials || [];

    if (materials.length === 0) {
      container.innerHTML = `
        <div class="card" style="text-align: center; padding: 3.5rem 1.5rem;">
          <div style="font-size: 3rem; margin-bottom: 0.6rem;">📄</div>
          <h2 style="font-size: 1.4rem; margin-bottom: 0.4rem;">No Study Materials Uploaded Yet</h2>
          <p style="color: var(--text-muted); font-size: 0.95rem; max-width: 480px; margin: 0 auto 1.5rem;">
            Upload your lecture notes, textbook chapters, or reference PDFs to index them for AI quiz generation.
          </p>
          <a href="generate.html" class="btn btn-primary">Upload First Material</a>
        </div>
      `;
      return;
    }

    let html = '<div class="grid-3">';

    materials.forEach(mat => {
      const isPdf = mat.file_type === 'pdf';
      const icon = isPdf ? '📄' : '📝';
      const sizeMb = (mat.file_size / (1024 * 1024)).toFixed(2);
      const dateStr = mat.created_at ? new Date(mat.created_at).toLocaleDateString() : '';

      html += `
        <div class="card card-hover" style="display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.8rem;">
              <span style="font-size: 2rem;">${icon}</span>
              <span style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; background: var(--bg-alt); color: var(--text-muted); padding: 0.2rem 0.5rem; border-radius: var(--radius-sm);">
                ${mat.file_type.toUpperCase()}
              </span>
            </div>

            <h3 style="font-size: 1.15rem; font-weight: 700; margin-bottom: 0.6rem; word-break: break-word;">
              ${escapeHTML(mat.file_name)}
            </h3>

            <div style="font-size: 0.85rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 0.3rem; margin-bottom: 1.5rem;">
              <div>📑 <strong>${mat.page_count}</strong> pages (${mat.chunk_count} RAG chunks)</div>
              <div>📊 <strong>${mat.total_words.toLocaleString()}</strong> words • ${sizeMb} MB</div>
              <div>⚡ <strong>${mat.quizzes_generated}</strong> quizzes generated</div>
              <div>📅 Added on ${dateStr}</div>
            </div>
          </div>

          <div style="display: flex; gap: 0.5rem; padding-top: 1rem; border-top: 1px solid var(--border-color); flex-wrap: wrap;">
            <a href="generate.html?material_id=${mat.id}" class="btn btn-primary btn-sm" style="flex: 1;">
              ⚡ Create Quiz
            </a>
            <button onclick="viewMaterialDetail('${mat.id}')" class="btn btn-secondary btn-sm" title="View Chunks">
              👁️ View
            </button>
            <button onclick="deleteMaterial('${mat.id}')" class="btn btn-secondary btn-sm" style="color: var(--danger);" title="Delete">
              🗑️
            </button>
          </div>
        </div>
      `;
    });

    html += '</div>';
    container.innerHTML = html;

  } catch (error) {
    container.innerHTML = `<div class="card" style="color: var(--danger); text-align: center; padding: 2rem;">${escapeHTML(error.message)}</div>`;
  }
}

async function viewMaterialDetail(matId) {
  try {
    const data = await fetchAPI(`/api/materials/${matId}`);
    const mat = data.material;

    document.getElementById('modalMatTitle').innerText = mat.file_name;
    document.getElementById('modalMatStats').innerHTML = `
      <span>📑 ${mat.page_count} Pages</span>
      <span>•</span>
      <span>🧩 ${mat.chunk_count} Chunks</span>
      <span>•</span>
      <span>📊 ${mat.total_words.toLocaleString()} Words</span>
    `;

    const chunksList = document.getElementById('modalChunksList');
    chunksList.innerHTML = '';

    (mat.chunks_preview || []).forEach((c, idx) => {
      const chunkCard = document.createElement('div');
      chunkCard.style.cssText = 'background: var(--bg-alt); padding: 0.85rem; border-radius: var(--radius-md); border: 1px solid var(--border-color); font-size: 0.85rem;';
      chunkCard.innerHTML = `
        <div style="font-weight: 700; color: var(--primary); margin-bottom: 0.3rem;">
          Chunk #${idx + 1} — Page ${c.page_number} (${c.char_count} chars)
        </div>
        <div style="color: var(--text-secondary); line-height: 1.4;">
          ${escapeHTML(c.chunk_text)}
        </div>
      `;
      chunksList.appendChild(chunkCard);
    });

    document.getElementById('materialModal').classList.add('active');

  } catch (error) {
    showToast(error.message || 'Failed to fetch material details.', 'error');
  }
}

async function deleteMaterial(matId) {
  if (!confirm('Are you sure you want to delete this study material?')) {
    return;
  }

  try {
    await fetchAPI(`/api/materials/${matId}`, { method: 'DELETE' });
    showToast('Material deleted successfully.', 'success');
    await loadMaterials();
  } catch (error) {
    showToast(error.message || 'Failed to delete material.', 'error');
  }
}
