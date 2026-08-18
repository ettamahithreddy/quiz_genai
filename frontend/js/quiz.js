/**
 * QuizGen AI - Interactive Quiz Player
 */

let quizData = null;
let currentQuestionIndex = 0;
let userAnswers = {};
let startTime = Date.now();
let timerInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();

  const params = new URLSearchParams(window.location.search);
  const quizId = params.get('id');

  if (!quizId) {
    showToast('Missing Quiz ID.', 'error');
    setTimeout(() => { window.location.href = 'dashboard.html'; }, 1000);
    return;
  }

  await loadQuiz(quizId);
  setupQuizControls(quizId);
  startTimer();
});

async function loadQuiz(quizId) {
  try {
    const data = await fetchAPI(`/api/quizzes/${quizId}`);
    quizData = data.quiz;

    document.getElementById('quizTitle').innerText = quizData.title;
    document.getElementById('quizTopicBadge').innerText = quizData.topic || 'General';

    renderCurrentQuestion();
  } catch (error) {
    showToast(error.message || 'Failed to load quiz questions.', 'error');
    setTimeout(() => { window.location.href = 'dashboard.html'; }, 1500);
  }
}

function startTimer() {
  const timerDisplay = document.getElementById('timerDisplay');
  timerInterval = setInterval(() => {
    const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    timerDisplay.innerText = `⏱️ ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }, 1000);
}

function renderCurrentQuestion() {
  if (!quizData || !quizData.questions || quizData.questions.length === 0) return;

  const total = quizData.questions.length;
  const q = quizData.questions[currentQuestionIndex];

  // Update Header Counters & Progress Fill
  document.getElementById('questionCounter').innerText = `Question ${currentQuestionIndex + 1} of ${total}`;
  const percent = ((currentQuestionIndex + 1) / total) * 100;
  document.getElementById('progressBarFill').style.width = `${percent}%`;

  // Update Question Meta Tags
  const typeLabels = {
    mcq: 'Multiple Choice (MCQ)',
    true_false: 'True / False',
    short_answer: 'Short Answer'
  };
  document.getElementById('questionTypeTag').innerText = typeLabels[q.type] || q.type.toUpperCase();
  document.getElementById('questionDiffTag').innerText = q.difficulty || 'Medium';
  document.getElementById('questionText').innerText = q.question;

  // Render Option Cards
  const optionsContainer = document.getElementById('optionsContainer');
  optionsContainer.innerHTML = '';

  const selectedAnswer = userAnswers[q.id] || '';

  if (q.type === 'mcq' || q.type === 'true_false') {
    const options = q.type === 'true_false' ? ['True', 'False'] : (q.options || []);
    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];

    options.forEach((opt, idx) => {
      const card = document.createElement('div');
      card.className = `option-card ${selectedAnswer === opt ? 'selected' : ''}`;
      
      const letter = q.type === 'true_false' ? (idx === 0 ? 'T' : 'F') : (letters[idx] || '•');

      card.innerHTML = `
        <div class="option-circle">${letter}</div>
        <div style="font-size: 1.05rem; font-weight: 500; color: var(--text-main);">${escapeHTML(opt)}</div>
      `;

      card.onclick = () => {
        userAnswers[q.id] = opt;
        renderCurrentQuestion();
      };

      optionsContainer.appendChild(card);
    });

  } else if (q.type === 'short_answer') {
    const textarea = document.createElement('textarea');
    textarea.className = 'form-control';
    textarea.style.minHeight = '140px';
    textarea.placeholder = 'Type your concise explanation or answer here...';
    textarea.value = selectedAnswer;

    textarea.oninput = () => {
      userAnswers[q.id] = textarea.value;
    };

    optionsContainer.appendChild(textarea);
  }

  // Manage Nav Button visibility
  const prevBtn = document.getElementById('prevQuestionBtn');
  const nextBtn = document.getElementById('nextQuestionBtn');
  const submitBtn = document.getElementById('submitQuizBtn');

  prevBtn.disabled = currentQuestionIndex === 0;

  if (currentQuestionIndex === total - 1) {
    nextBtn.style.display = 'none';
    submitBtn.style.display = 'inline-flex';
  } else {
    nextBtn.style.display = 'inline-flex';
    submitBtn.style.display = 'none';
  }
}

function setupQuizControls(quizId) {
  document.getElementById('prevQuestionBtn').onclick = () => {
    if (currentQuestionIndex > 0) {
      currentQuestionIndex--;
      renderCurrentQuestion();
    }
  };

  document.getElementById('nextQuestionBtn').onclick = () => {
    if (currentQuestionIndex < quizData.questions.length - 1) {
      currentQuestionIndex++;
      renderCurrentQuestion();
    }
  };

  document.getElementById('submitQuizBtn').onclick = async () => {
    await submitQuizAttempt(quizId);
  };

  document.getElementById('quitQuizBtn').onclick = () => {
    if (confirm('Are you sure you want to quit this quiz? Your progress will not be saved.')) {
      window.location.href = 'dashboard.html';
    }
  };
}

async function submitQuizAttempt(quizId) {
  const submitBtn = document.getElementById('submitQuizBtn');
  submitBtn.disabled = true;
  submitBtn.innerText = 'Evaluating...';

  if (timerInterval) clearInterval(timerInterval);
  const timeTakenSeconds = Math.floor((Date.now() - startTime) / 1000);

  // Format answers payload
  const formattedAnswers = quizData.questions.map(q => ({
    question_id: q.id,
    user_answer: userAnswers[q.id] || ''
  }));

  try {
    const data = await fetchAPI(`/api/quizzes/${quizId}/submit`, {
      method: 'POST',
      body: JSON.stringify({
        answers: formattedAnswers,
        time_taken: timeTakenSeconds
      })
    });

    // Explosive celebration blast upon clicking Submit Quiz
    if (typeof confetti === 'function') {
      const festiveColors = ['#4f46e5', '#0ea5e9', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#ef4444'];
      
      // Dual side cannons
      confetti({
        particleCount: 80,
        angle: 60,
        spread: 70,
        origin: { x: 0, y: 0.75 },
        colors: festiveColors,
        zIndex: 9999
      });

      confetti({
        particleCount: 80,
        angle: 120,
        spread: 70,
        origin: { x: 1, y: 0.75 },
        colors: festiveColors,
        zIndex: 9999
      });

      // Center explosion
      confetti({
        particleCount: 120,
        spread: 100,
        origin: { x: 0.5, y: 0.6 },
        colors: festiveColors,
        zIndex: 9999
      });
    }

    showToast('🎉 Quiz Submitted! Evaluating answers...', 'success');
    setTimeout(() => {
      window.location.href = `result.html?attempt_id=${data.attempt_id}`;
    }, 1100);

  } catch (error) {
    submitBtn.disabled = false;
    submitBtn.innerText = '✓ Submit Quiz';
    showToast(error.message || 'Failed to submit quiz.', 'error');
  }
}
