/**
 * QuizGen AI - Results and Grounded Review
 */

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();

  const params = new URLSearchParams(window.location.search);
  const attemptId = params.get('attempt_id');

  if (!attemptId) {
    showToast('Missing attempt ID.', 'error');
    setTimeout(() => { window.location.href = 'dashboard.html'; }, 1000);
    return;
  }

  await loadAttemptResults(attemptId);
});

async function loadAttemptResults(attemptId) {
  try {
    const data = await fetchAPI(`/api/quizzes/attempts/${attemptId}`);
    const attempt = data.attempt;

    renderScoreHero(attempt);
    renderDetailedReview(attempt.detailed_review);

    // Setup Practice Weak Topics button
    document.getElementById('practiceWeakBtn').onclick = () => {
      window.location.href = `generate.html?topic=${encodeURIComponent(attempt.topic || 'Review')}&mode=topic`;
    };

  } catch (error) {
    showToast(error.message || 'Failed to load attempt results.', 'error');
  }
}

function renderScoreHero(attempt) {
  const accuracy = Math.round(attempt.accuracy || 0);
  document.getElementById('scorePercentage').innerText = accuracy;

  const emoji = document.getElementById('resultEmoji');
  const title = document.getElementById('resultTitle');
  const subtitle = document.getElementById('resultSubtitle');

  if (accuracy >= 80) {
    emoji.innerText = '🏆';
    title.innerText = 'Outstanding Performance!';
    subtitle.innerText = `You've demonstrated exceptional mastery of ${escapeHTML(attempt.topic || 'this subject')}.`;
  } else if (accuracy >= 50) {
    emoji.innerText = '🌟';
    title.innerText = 'Great Effort!';
    subtitle.innerText = `You're on the right track with ${escapeHTML(attempt.topic || 'this material')}. Review the source citations below.`;
  } else {
    emoji.innerText = '🚀';
    title.innerText = 'Quiz Completed!';
    subtitle.innerText = 'Review the source material citations below to strengthen key concepts.';
  }

  document.getElementById('statCorrect').innerText = attempt.correct || 0;
  document.getElementById('statIncorrect').innerText = attempt.incorrect || 0;
  document.getElementById('statTotal').innerText = attempt.total_questions || 0;

  // Format time
  const timeSeconds = attempt.time_taken || 0;
  const m = Math.floor(timeSeconds / 60);
  const s = timeSeconds % 60;
  document.getElementById('statTime').innerText = m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function renderDetailedReview(reviewList) {
  const container = document.getElementById('questionsReviewContainer');
  if (!reviewList || reviewList.length === 0) {
    container.innerHTML = '<p style="color: var(--text-muted);">No question details available.</p>';
    return;
  }

  let html = '';

  reviewList.forEach((item, idx) => {
    const isCorrect = item.is_correct;
    const borderClass = isCorrect ? 'var(--success)' : 'var(--danger)';
    const statusBadge = isCorrect 
      ? '<span style="background: var(--success-light); color: var(--success-text); font-weight: 700; font-size: 0.8rem; padding: 0.25rem 0.6rem; border-radius: var(--radius-sm);">✓ Correct</span>'
      : '<span style="background: var(--danger-light); color: var(--danger-text); font-weight: 700; font-size: 0.8rem; padding: 0.25rem 0.6rem; border-radius: var(--radius-sm);">✕ Incorrect</span>';

    html += `
      <div class="card" style="border-left: 5px solid ${borderClass}; padding: 1.8rem;">
        <!-- Card Header -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; flex-wrap: wrap; gap: 0.5rem;">
          <div style="display: flex; align-items: center; gap: 0.6rem;">
            <span style="font-weight: 800; font-size: 1.1rem; color: var(--text-main);">Question ${idx + 1}</span>
            <span style="font-size: 0.75rem; text-transform: uppercase; background: var(--bg-alt); color: var(--text-muted); padding: 0.2rem 0.5rem; border-radius: var(--radius-sm); font-weight: 600;">
              ${item.type.replace('_', ' ')}
            </span>
          </div>
          <div>${statusBadge}</div>
        </div>

        <!-- Question Text -->
        <p style="font-size: 1.05rem; font-weight: 600; color: var(--text-main); margin-bottom: 1.2rem;">
          ${escapeHTML(item.question)}
        </p>

        <!-- User Answer vs Correct Answer -->
        <div style="background: var(--bg-alt); border-radius: var(--radius-md); padding: 1rem; margin-bottom: 1.2rem; font-size: 0.95rem;">
          <div style="margin-bottom: 0.4rem;">
            <span style="font-weight: 700; color: var(--text-muted);">Your Answer: </span>
            <span style="font-weight: 600; color: ${isCorrect ? 'var(--success-text)' : 'var(--danger-text)'};">
              ${escapeHTML(item.user_answer || '(No answer provided)')}
            </span>
          </div>

          <div>
            <span style="font-weight: 700; color: var(--text-muted);">Correct Answer: </span>
            <span style="font-weight: 700; color: var(--text-main);">
              ${escapeHTML(item.correct_answer)}
            </span>
          </div>
        </div>

        <!-- Explanation -->
        <div style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem; line-height: 1.5;">
          <strong>Explanation: </strong>${escapeHTML(item.explanation)}
        </div>

        <!-- Grounded Source Citation Box -->
        <div class="source-citation">
          <div class="source-citation-header">
            <span>📄 Grounded Source Citation</span>
            <span class="source-page-badge">Page ${item.source_page || 1}</span>
          </div>
          <div class="source-citation-text">
            "${escapeHTML(item.source_text || 'Grounding fact retrieved from study material.')}"
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}
