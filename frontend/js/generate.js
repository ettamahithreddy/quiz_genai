/**
 * QuizGen AI - Quiz Generator Logic
 */

let selectedFile = null;
let currentTab = 'tab-pdf';
let insufficientState = null;

document.addEventListener('DOMContentLoaded', () => {
  requireAuth();

  // Check URL parameters for prefilled topic or material
  const params = new URLSearchParams(window.location.search);
  const prefillTopic = params.get('topic');
  const prefillMaterial = params.get('material_id');
  const prefillMode = params.get('mode');

  // Setup tab buttons
  const tabButtons = document.querySelectorAll('.input-tab-btn');
  tabButtons.forEach(btn => {
    btn.onclick = () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const targetTabId = btn.getAttribute('data-tab');
      currentTab = targetTabId;

      document.querySelectorAll('.tab-content-panel').forEach(panel => {
        panel.style.display = 'none';
      });
      document.getElementById(targetTabId).style.display = 'block';
    };
  });

  // Switch to topic mode if URL parameter passed
  if (prefillMode === 'topic' || (prefillTopic && !prefillMaterial)) {
    const topicBtn = document.querySelector('[data-tab="tab-topic"]');
    if (topicBtn) topicBtn.click();
    if (prefillTopic) {
      document.getElementById('topicInput').value = prefillTopic;
    }
  }

  // Setup Dropzone
  setupDropzone();

  // Setup sample topic buttons
  document.querySelectorAll('.sample-topic-btn').forEach(btn => {
    btn.onclick = () => {
      document.getElementById('topicInput').value = btn.innerText.trim();
    };
  });

  // Setup Character Counter
  const notesTextarea = document.getElementById('notesTextInput');
  const charCounter = document.getElementById('charCounter');
  notesTextarea.addEventListener('input', () => {
    charCounter.innerText = notesTextarea.value.length;
  });

  // Setup Form Submit
  const form = document.getElementById('quizGeneratorForm');
  form.onsubmit = async (e) => {
    e.preventDefault();
    await handleGenerateQuiz(false);
  };

  // Setup Insufficient Content Modal Buttons
  document.getElementById('cancelPartialBtn').onclick = () => {
    document.getElementById('insufficientModal').classList.remove('active');
  };

  document.getElementById('confirmPartialBtn').onclick = async () => {
    document.getElementById('insufficientModal').classList.remove('active');
    if (insufficientState) {
      document.getElementById('numQuestionsSelect').value = insufficientState.max_reliable_questions;
      await handleGenerateQuiz(true);
    }
  };
});

function setupDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('pdfFileInput');
  const browseBtn = document.getElementById('browseBtn');
  const filePreview = document.getElementById('filePreview');
  const previewFileName = document.getElementById('previewFileName');
  const previewFileSize = document.getElementById('previewFileSize');
  const removeFileBtn = document.getElementById('removeFileBtn');

  browseBtn.onclick = () => fileInput.click();
  dropzone.onclick = (e) => {
    if (e.target !== browseBtn) fileInput.click();
  };

  dropzone.ondragover = (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  };

  dropzone.ondragleave = () => {
    dropzone.classList.remove('dragover');
  };

  dropzone.ondrop = (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  fileInput.onchange = () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  };

  removeFileBtn.onclick = () => {
    selectedFile = null;
    fileInput.value = '';
    filePreview.style.display = 'none';
    dropzone.style.display = 'block';
  };

  function handleFileSelected(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'txt', 'md'].includes(ext)) {
      showToast('Please upload a PDF or text document.', 'error');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      showToast('File size exceeds the 20 MB limit.', 'error');
      return;
    }

    selectedFile = file;
    previewFileName.innerText = file.name;
    previewFileSize.innerText = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
    dropzone.style.display = 'none';
    filePreview.style.display = 'flex';
  }
}

async function handleGenerateQuiz(forceCount = false) {
  // Validate question types
  const qTypeCheckboxes = document.querySelectorAll('input[name="qType"]:checked');
  const questionTypes = Array.from(qTypeCheckboxes).map(cb => cb.value);

  if (questionTypes.length === 0) {
    showToast('Please select at least one question type (MCQ, True/False, or Short Answer).', 'error');
    return;
  }

  const numQuestionsInput = document.getElementById('numQuestionsInput');
  const numQuestionsRaw = numQuestionsInput ? numQuestionsInput.value.trim() : '';
  const numQuestions = Number(numQuestionsRaw);

  if (!numQuestionsRaw || isNaN(numQuestions) || !Number.isInteger(numQuestions) || numQuestions < 1 || numQuestions > 100) {
    showToast('Please enter a valid positive number of questions.', 'error');
    if (numQuestionsInput) numQuestionsInput.focus();
    return;
  }

  const difficulty = document.getElementById('difficultySelect').value;

  let requestBody;
  let isFormData = false;

  if (currentTab === 'tab-pdf') {
    if (!selectedFile) {
      showToast('Please select a PDF file to upload.', 'error');
      return;
    }
    const specificTopic = document.getElementById('pdfSpecificTopic').value.trim();
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('topic', specificTopic);
    formData.append('num_questions', numQuestions);
    formData.append('number_of_questions', numQuestions);
    formData.append('difficulty', difficulty);
    formData.append('question_types', JSON.stringify(questionTypes));
    if (forceCount) formData.append('force_count', 'true');

    requestBody = formData;
    isFormData = true;

  } else if (currentTab === 'tab-topic') {
    const topic = document.getElementById('topicInput').value.trim();
    if (!topic) {
      showToast('Please enter a topic name.', 'error');
      return;
    }

    requestBody = JSON.stringify({
      topic,
      num_questions: numQuestions,
      number_of_questions: numQuestions,
      difficulty,
      question_types: questionTypes,
      force_count: forceCount
    });

  } else if (currentTab === 'tab-notes') {
    const text = document.getElementById('notesTextInput').value.trim();
    const title = document.getElementById('notesTitleInput').value.trim() || 'Pasted Notes';
    if (!text) {
      showToast('Please paste your study material or article.', 'error');
      return;
    }

    requestBody = JSON.stringify({
      text,
      topic: title,
      num_questions: numQuestions,
      number_of_questions: numQuestions,
      difficulty,
      question_types: questionTypes,
      force_count: forceCount
    });
  }

  // Start Stepper Animation
  startLoaderAnimation();

  try {
    const options = {
      method: 'POST',
      body: requestBody
    };
    if (isFormData) {
      options.headers = {}; // browser sets multipart boundary automatically
    }

    const data = await fetchAPI('/api/quizzes/generate', options);

    // Handle Insufficient Content Case
    if (data.insufficient_content && !forceCount) {
      stopLoaderAnimation();
      insufficientState = data;
      document.getElementById('insufficientTitle').innerText = `Only ${data.max_reliable_questions} Reliable Questions Available`;
      document.getElementById('insufficientMessage').innerText = data.message;
      document.getElementById('confirmPartialBtn').innerText = `Generate ${data.max_reliable_questions} Grounded Questions`;
      document.getElementById('insufficientModal').classList.add('active');
      return;
    }

    // Complete all steps
    completeAllLoaderSteps();

    showToast('Quiz generated successfully! Loading questions...', 'success');
    setTimeout(() => {
      window.location.href = `quiz.html?id=${data.quiz.id}`;
    }, 1000);

  } catch (error) {
    stopLoaderAnimation();
    showToast(error.message || 'Quiz generation failed. Please try again.', 'error');
  }
}

// Clean Loading Modal Controllers
function startLoaderAnimation() {
  const modal = document.getElementById('aiLoaderModal');
  if (modal) modal.classList.add('active');
}

function completeAllLoaderSteps() {
  // No-op for clean minimal loader
}

function stopLoaderAnimation() {
  const modal = document.getElementById('aiLoaderModal');
  if (modal) modal.classList.remove('active');
}
