/**
 * QuizGen AI - Dashboard Script
 */

let scoreChartInstance = null;

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();

  const user = getCurrentUser();
  if (user) {
    document.getElementById('welcomeGreeting').innerText = `Welcome back, ${escapeHTML(user.name || 'Student')}! 👋`;
  }

  await loadDashboardData();
});

async function loadDashboardData() {
  try {
    const data = await fetchAPI('/api/dashboard');
    const { metrics, recent_quizzes, weak_topics, chart_data } = data;

    // Update Stat Cards
    document.getElementById('statTotalQuizzes').innerText = metrics.total_quizzes;
    document.getElementById('statAvgScore').innerText = `${metrics.average_score}%`;
    document.getElementById('statQuestionsAnswered').innerText = metrics.total_questions_answered;
    document.getElementById('statBestScore').innerText = `${metrics.best_score}%`;

    // Render Weak Topics
    renderWeakTopics(weak_topics);

    // Render Recent Quizzes
    renderRecentQuizzes(recent_quizzes);

    // Render Chart
    renderChart(chart_data);

  } catch (error) {
    console.error('Failed to load dashboard:', error);
    showToast('Failed to load dashboard statistics.', 'error');
  }
}

function renderWeakTopics(weakTopics) {
  const container = document.getElementById('weakTopicsList');
  if (!weakTopics || weakTopics.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 1.5rem 0; color: var(--text-muted); font-size: 0.9rem;">
        🌟 Great job! No weak topics detected yet. Keep quizzing!
      </div>
    `;
    return;
  }

  let html = '';
  weakTopics.forEach(t => {
    const accuracy = Math.round(t.accuracy);
    let badgeClass = 'var(--danger-light)';
    let textColor = 'var(--danger-text)';

    if (accuracy >= 75) {
      badgeClass = 'var(--success-light)';
      textColor = 'var(--success-text)';
    } else if (accuracy >= 50) {
      badgeClass = 'var(--warning-light)';
      textColor = 'var(--warning-text)';
    }

    html += `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.8rem; background: var(--bg-alt); border-radius: var(--radius-md);">
        <div>
          <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-main);">${escapeHTML(t.topic)}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">${t.questions_answered} questions answered</div>
        </div>
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <span style="font-size: 0.85rem; font-weight: 700; background: ${badgeClass}; color: ${textColor}; padding: 0.25rem 0.6rem; border-radius: var(--radius-sm);">
            ${accuracy}%
          </span>
          <button onclick="practiceWeakTopic('${encodeURIComponent(t.topic)}')" class="btn btn-outline-primary btn-sm" title="Practice Weak Topic">
            Practice
          </button>
        </div>
      </div>
    `;
  });

  html += `
    <div style="margin-top: 0.5rem; text-align: center;">
      <a href="generate.html" class="btn btn-primary btn-sm btn-block">🎯 Generate Personalized Quiz</a>
    </div>
  `;

  container.innerHTML = html;
}

function practiceWeakTopic(encodedTopic) {
  const topic = decodeURIComponent(encodedTopic);
  window.location.href = `generate.html?topic=${encodeURIComponent(topic)}&mode=topic`;
}

function renderRecentQuizzes(quizzes) {
  const container = document.getElementById('recentQuizzesContainer');
  if (!quizzes || quizzes.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📚</div>
        <p style="font-size: 1.05rem; font-weight: 600; margin-bottom: 0.3rem;">No quizzes created yet</p>
        <p style="font-size: 0.9rem; margin-bottom: 1.2rem;">Upload your study notes to generate your first quiz.</p>
        <a href="generate.html" class="btn btn-primary btn-sm">Create First Quiz</a>
      </div>
    `;
    return;
  }

  let html = `
    <div style="display: flex; flex-direction: column; gap: 0.85rem;">
  `;

  quizzes.forEach(q => {
    const dateFormatted = q.created_at ? new Date(q.created_at).toLocaleDateString() : '';
    html += `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.25rem; background: var(--bg-alt); border: 1px solid var(--border-color); border-radius: var(--radius-md); flex-wrap: wrap; gap: 0.8rem;">
        <div>
          <div style="font-weight: 700; font-size: 1rem; color: var(--text-main);">${escapeHTML(q.title)}</div>
          <div style="display: flex; gap: 0.6rem; font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem; align-items: center;">
            <span>🏷️ ${escapeHTML(q.topic)}</span>
            <span>•</span>
            <span>❓ ${q.question_count} Questions</span>
            <span>•</span>
            <span>📊 ${q.difficulty.toUpperCase()}</span>
            <span>•</span>
            <span>📅 ${dateFormatted}</span>
          </div>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <a href="quiz.html?id=${q.id}" class="btn btn-primary btn-sm">Take Quiz</a>
        </div>
      </div>
    `;
  });

  html += '</div>';
  container.innerHTML = html;
}

function renderChart(chartData) {
  const ctx = document.getElementById('scoreChart');
  if (!ctx) return;

  let labels = [];
  let scores = [];

  if (chartData) {
    if (Array.isArray(chartData.labels) && chartData.labels.length > 0) {
      labels = chartData.labels;
      scores = chartData.scores || [];
    } else if (Array.isArray(chartData.progression) && chartData.progression.length > 0) {
      labels = chartData.progression.map((item, idx) => item.quiz_label || `Quiz ${item.attempt || idx + 1}`);
      scores = chartData.progression.map(item => Number(item.accuracy) || 0);
    } else if (Array.isArray(chartData) && chartData.length > 0) {
      labels = chartData.map((item, idx) => `Quiz ${item.attempt || idx + 1}`);
      scores = chartData.map(item => Number(item.accuracy) || 0);
    }
  }

  if (labels.length === 0) {
    labels = ['Quiz 1', 'Quiz 2', 'Quiz 3', 'Quiz 4', 'Quiz 5'];
    scores = [0, 0, 0, 0, 0];
  }

  if (scoreChartInstance) {
    scoreChartInstance.destroy();
  }

  scoreChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Accuracy (%)',
        data: scores,
        borderColor: '#4f46e5',
        backgroundColor: 'rgba(79, 70, 229, 0.1)',
        tension: 0.35,
        fill: true,
        pointBackgroundColor: '#4f46e5',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 7
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: {
            callback: value => `${value}%`
          },
          grid: {
            color: '#f1f5f9'
          }
        },
        x: {
          grid: {
            display: false
          }
        }
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label: context => ` Accuracy: ${context.parsed.y}%`
          }
        }
      }
    }
  });
}
