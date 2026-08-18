# QuizGen AI — Smart Generative AI Quiz Generator (RAG-Powered)

QuizGen AI is a full-stack educational AI web application that generates personalized, strictly source-grounded quizzes and flashcards from study materials (PDF textbooks, lecture notes, pasted articles, or topics) using a **Retrieval-Augmented Generation (RAG)** pipeline.

---

## 🌟 Core Purpose & Philosophy

> **"QuizGen AI generates quizzes strictly from the user's selected study material and keeps questions grounded in the supplied context."**

Unlike naive AI tools that generate random trivia with hallucinations, QuizGen AI:
1. **Extracts page-level text** from uploaded PDFs using PyMuPDF.
2. **Splits text into overlapping semantic chunks** while preserving exact page number metadata.
3. **Generates dense vector embeddings** using `sentence-transformers` (`all-MiniLM-L6-v2`).
4. **Performs semantic cosine retrieval and keyword filtering** tailored specifically to the requested topic (e.g. "Supervised Learning" vs "Python Loops").
5. **Enforces strict source grounding** so every generated question is accompanied by an exact **page reference** and verbatim **source citation snippet**.
6. **Detects insufficient content** to avoid hallucinating questions when the source text is too brief.

---

## 🚀 Key Features

* **3 Flexible Input Modes**:
  * 📄 **Upload PDF**: Supports any PDF document up to 20 MB with drag-and-drop.
  * 🔍 **Enter Topic**: Topic-directed study mode.
  * 📝 **Paste Article / Notes**: Direct textarea input with live character counter.
* **Topic-Specific PDF Filtering**: Filter specific chapters or topics within large multi-chapter PDFs (e.g. asking for "Python Loops" from a multi-chapter textbook only extracts Page 4 questions).
* **Multi-Format Assessment**:
  * Multiple Choice Questions (MCQs with 4 options & plausible distractors)
  * True / False Questions
  * Short-Answer Questions with semantic keyword scoring
* **Difficulty & Count Customization**: 5, 10, 20, 30, 50 questions with Easy, Medium, Hard, or Mixed difficulty.
* **Animated AI Generation Stepper**: Visual real-time step progression (*Reading material → Processing content → Creating embeddings → Retrieving context → Generating questions → Validating citations*).
* **Interactive Quiz Player**: Clean, responsive UI with question counter, progress bar, timer, option selection, and smooth navigation.
* **Detailed Results & Grounded Review**: Displays score percentage, time elapsed, accuracy breakdown, and green/red cards featuring exact **Source Page & Verbatim Excerpt** citations.
* **Student Analytics Dashboard**:
  * Metric cards (Total Quizzes, Average Score, Questions Answered, Best Score)
  * Interactive Score History line chart (Chart.js)
  * Weak Topic Mastery tracker with an instant **"Practice Weak Topics"** button
* **3D Flip Study Flashcards**: Active recall study decks with 3D flip card animations, Easy / Difficult ratings, and mastery progress bars.
* **Quiz Sharing & Code Lookup**: One-click share codes (e.g. `ML2026`) for peer quizzes and teacher-student sharing.
* **Strict User Isolation**: All private PDFs, quizzes, attempts, and progress records are scoped strictly to the authenticated `user_id` extracted from JWTs.

---

## 🛠️ Technology Stack

| Layer | Technologies Used |
|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (ES6+), Chart.js |
| **Backend** | Python 3.11+, Flask, Flask-CORS, Flask-JWT-Extended, bcrypt |
| **Document Processing & RAG** | PyMuPDF (`pymupdf`), `sentence-transformers` (`all-MiniLM-L6-v2`), NumPy, Scikit-Learn |
| **Database** | MongoDB Atlas / Local MongoDB with PyMongo (resilient in-memory fallback) |
| **Generative AI** | Google Gemini API (`gemini-1.5-flash` / `gemini-1.5-pro` / `gemini-2.0-flash`) + Local Heuristic RAG engine |

---

## 🏗️ Architecture & RAG Pipeline

```text
       ┌───────────────────────────────────────────────┐
       │     PDF / Notes / Article / Topic Input      │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────┐
       │     PyMuPDF Text Extraction (Page-by-Page)    │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────┐
       │     Text Normalization & Overlapping Chunks   │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────┐
       │    Sentence-Transformers (all-MiniLM-L6-v2)   │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────┐
       │  Topic Semantic Retrieval & Keyword Overlap   │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────┐
       │     Strict Source-Grounded Generative AI      │
       │    (System Prompt: No External Knowledge)     │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────┐
       │  Post-Generation Validation & Citation Check  │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────┐
       │       Interactive Quiz & MongoDB Storage      │
       └───────────────────────────────────────────────┘
```

---

## 📂 MongoDB Collections

The database `quiz_generator` contains the following collections:

1. **`users`**: User credentials, bcrypt `password_hash`, `email` (unique index), `role` ("student" | "teacher").
2. **`materials`**: Metadata (`file_name`, `page_count`, `total_words`, `file_size`), and indexed RAG `chunks` with embeddings and page numbers.
3. **`quizzes`**: Generated quizzes with question sets, difficulty, `share_code`, and timestamps.
4. **`attempts`**: Student quiz attempts, recorded answers, total score, accuracy, and elapsed time.
5. **`progress`**: Topic mastery tracking per user (`topic`, `questions_answered`, `correct_answers`, `accuracy`, `last_practiced`).
6. **`flashcards`**: 3D study card decks with difficulty ratings and mastery tracking.
7. **`quiz_shares`**: Shared quiz access tokens and access counters.

---

## ⚙️ Environment Variables

Create a `.env` file in the root directory (copied from `.env.example`):

```env
# Server
PORT=5000
FLASK_ENV=development
DEBUG=True

# MongoDB Configuration
# For MongoDB Atlas:
# MONGO_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/quiz_generator?retryWrites=true&w=majority
MONGO_URI=mongodb://localhost:27017/quiz_generator
DB_NAME=quiz_generator

# JWT Secret
JWT_SECRET_KEY=quizgen_jwt_secret_dev_2026_x89a_secure

# AI / LLM Configuration (Google Gemini)
GEMINI_API_KEY=your_gemini_api_key_here
AI_API_KEY=your_gemini_api_key_here

# Upload Limits
MAX_CONTENT_LENGTH=20971520 # 20 MB
UPLOAD_FOLDER=uploads
```

---

## 💻 Installation & Setup Instructions

### 1. Prerequisites
- Python 3.10+
- (Optional) MongoDB Community Server or MongoDB Atlas Account

### 2. Setup Virtual Environment
```bash
# Clone or navigate to the repository
cd hackathon_project

# Create virtual environment
python -m venv .venv

# Activate on Windows:
.venv\Scripts\activate

# Activate on macOS / Linux:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Run the Flask Backend & Frontend Server
```bash
python backend/app.py
```

The Flask server serves both the REST API endpoints and the full static frontend at:
👉 **`http://localhost:5000`**

Open your web browser and navigate to `http://localhost:5000` to start using QuizGen AI!

---

## 🧪 Testing Scenarios

Run the automated end-to-end test suite:

```bash
python -m unittest tests/test_e2e_scenarios.py
```

### Validated Test Cases:
1. **PDF Upload + Topic Grounding**: Uploads `Machine_Learning_Notes.pdf` with topic `Supervised Learning`, verifying that generated questions focus strictly on regression, classification, decision trees, and classification metrics on Page 2.
2. **Topic Isolation**: Filters `Python Loops` from multi-chapter notes and verifies question citations resolve directly to Page 4.
3. **Insufficient Content Guard**: Requests 50 questions on a single brief note, verifying the system halts hallucination and prompts the user with the true maximum capacity.
4. **User Data Isolation**: Validates that User B cannot read or access User A's uploaded materials or private quizzes.

---

## 📡 REST API Documentation

### Authentication
* `POST /api/auth/register` — Register a new account (`name`, `email`, `password`, `confirm_password`, `role`).
* `POST /api/auth/login` — Sign in and receive JWT token (`email`, `password`).
* `GET /api/auth/me` — Fetch currently authenticated user profile.
* `POST /api/auth/logout` — Logout.

### Materials
* `POST /api/materials/upload` — Upload PDF file or pasted text notes for RAG chunking.
* `GET /api/materials` — List all study materials uploaded by the authenticated user.
* `GET /api/materials/<id>` — View material metadata and chunk previews.
* `DELETE /api/materials/<id>` — Delete material and associated chunks.

### Quizzes
* `POST /api/quizzes/generate` — RAG-based quiz generator (`material_id`, `topic`, `num_questions`, `difficulty`, `question_types`).
* `GET /api/quizzes` — List user's generated quizzes with latest scores.
* `GET /api/quizzes/<id>` — Get quiz details for taking the quiz.
* `POST /api/quizzes/<id>/submit` — Submit quiz answers for scoring, update topic progress.
* `GET /api/quizzes/attempts/<attempt_id>` — Retrieve score breakdown with source citations.
* `GET /api/quizzes/share/<share_code>` — Retrieve shared quiz by code (e.g. `ML2026`).
* `DELETE /api/quizzes/<id>` — Delete a quiz.

### Dashboard & Analytics
* `GET /api/dashboard` — Aggregated metrics, recent quizzes, weak topics, and chart data.
* `GET /api/progress` — Topic mastery statistics.
* `GET /api/analytics` — Question type performance breakdown.

### Flashcards
* `POST /api/flashcards/generate` — Generate active recall flashcard deck from material or topic.
* `GET /api/flashcards` — List flashcard decks with mastery stats.
* `GET /api/flashcards/<id>` — Get deck cards.
* `PUT /api/flashcards/<deck_id>/cards/<card_id>` — Update mastery rating (`mastered`, `difficulty_rating`).
* `DELETE /api/flashcards/<deck_id>` — Delete deck.

---

## 👥 Contributors & Hackathon Submission

* **Project**: QuizGen AI
* **Category**: Generative AI
* **Core Purpose**: Grounded Quiz Generation using Retrieval-Augmented Generation (RAG)
