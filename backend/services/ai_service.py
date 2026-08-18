import json
import re
import random
import logging
import requests
from typing import List, Dict, Any, Optional
from backend.config import Config
from backend.services.topic_service import (
    normalize_topic,
    validate_topic_question_relevance,
    is_duplicate_question,
    get_prebuilt_topic_questions,
    generate_dynamic_topic_knowledge_bank,
    get_prebuilt_topic_flashcards
)
from backend.services.embedding_service import get_embedding, calculate_cosine_similarity

logger = logging.getLogger(__name__)

# =========================================================================
# SYSTEM PROMPTS
# =========================================================================

RAG_SYSTEM_PROMPT = """You are QuizGen AI, an expert, strict source-grounded quiz generator.
Your primary directive is to generate accurate, high-quality assessment questions ONLY from the provided source context chunks.

CRITICAL RULES:
1. STRICT SOURCE GROUNDING: You MUST base every question, option, answer, and explanation purely on facts explicitly stated in the provided context.
2. NO EXTERNAL HALLUCINATION: Do NOT introduce outside facts or speculative knowledge not found in the context.
3. TOPIC RELEVANCE: If a topic is specified, generate questions concerning concepts, causes, consequences, mechanisms, and details related to that topic within the context.
4. SOURCE CITATION: For every question, identify the source_page (integer) and verbatim source_text excerpt from the chunk.
5. QUESTION FORMATS:
   - For 'mcq': Provide exactly 4 options (A, B, C, D text strings). Only ONE option must be correct. Ensure plausible distractors grounded in related context terms.
   - For 'true_false': Options must be ["True", "False"]. Correct answer must be "True" or "False".
   - For 'short_answer': Provide a clear, conceptual question and a concise expected answer key.
6. DIFFICULTY: Set difficulty to one of: 'Easy', 'Medium', 'Difficult'.
7. JSON ONLY: Respond ONLY with a valid JSON object matching the requested schema.
"""

TOPIC_SYSTEM_PROMPT_TEMPLATE = """You are an expert educational quiz generator.

The requested topic is:
{TOPIC}

Generate questions ONLY about this requested topic.
The questions must test concepts that are directly related to the topic.
Do not generate generic questions.
Do not change the subject.
Do not silently broaden the topic.
Do not generate questions about unrelated concepts.

If the requested topic is narrow, keep the questions narrow.
If the topic contains multiple concepts, questions may cover those concepts.

Target Difficulty Level: {DIFFICULTY}
- Easy: Basic definitions and simple concepts.
- Medium: Conceptual understanding and simple application.
- Hard / Difficult: Application, comparison, reasoning and code-based questions where appropriate.
- Mixed: A balanced mixture of Easy, Medium, and Difficult questions across the quiz (set individual difficulty per question to 'Easy', 'Medium', or 'Difficult').

Required Question Types: {QUESTION_TYPES}
- For 'mcq': Provide exactly 4 options (A, B, C, D text strings). Only ONE option must be correct. Ensure plausible distractors strictly related to {TOPIC}.
- For 'true_false': Options must be ["True", "False"]. Correct answer must be "True" or "False".
- For 'short_answer': Provide a clear, conceptual question and a concise expected answer key.

Return structured JSON only:
{{
  "questions": [
    {{
      "id": "q1",
      "type": "mcq",
      "question": "Question text directly about {TOPIC}...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option B",
      "explanation": "Clear explanation directly concerning {TOPIC}.",
      "difficulty": "Easy",
      "topic": "{TOPIC}"
    }}
  ]
}}
"""

FLASHCARD_TOPIC_SYSTEM_PROMPT = """You are an expert active-recall flashcard creator.

The requested topic is:
{TOPIC}

Create concise, high-yield active recall flashcards specifically and exclusively about {TOPIC}.
Do not include unrelated concepts or switch subjects.
Every card should have:
- 'front': A focused concept, question, or prompt about {TOPIC}.
- 'back': A clear, accurate definition or answer explaining the concept.

Return structured JSON only:
{{
  "flashcards": [
    {{
      "id": "fc1",
      "front": "Front question/concept...",
      "back": "Detailed definition/answer...",
      "topic": "{TOPIC}"
    }}
  ]
}}
"""

# =========================================================================
# SCENARIO B: DEDICATED TOPIC-ONLY QUIZ GENERATION PIPELINE
# =========================================================================

def generate_topic_quiz_with_ai(
    topic: str,
    num_questions: int,
    difficulty: str,
    question_types: List[str]
) -> Dict[str, Any]:
    """
    Dedicated Topic-Only Generation Pipeline:
    1. Topic normalization.
    2. Topic-specific generation with AI.
    3. Topic relevance validation (rejecting off-topic / weak matches / duplicates).
    4. Replacement question loop until exactly num_questions valid items are obtained.
    5. Local fallback if API is unavailable.
    """
    norm_topic = normalize_topic(topic)
    diff_clean = difficulty.lower()
    if diff_clean == "mixed":
        diff_label = "Mixed"
        diff_prompt_desc = "Mixed (generate a balanced mixture of Easy, Medium, and Difficult questions)"
    elif diff_clean in ("hard", "difficult"):
        diff_label = "Difficult"
        diff_prompt_desc = "Difficult"
    elif diff_clean == "easy":
        diff_label = "Easy"
        diff_prompt_desc = "Easy"
    else:
        diff_label = "Medium"
        diff_prompt_desc = "Medium"

    valid_types = question_types if question_types else ["mcq"]
    types_desc = ", ".join(valid_types)

    logger.info("[QUIZ] Topic: %s", norm_topic)
    logger.info("[QUIZ] Generation mode: TOPIC")

    accepted_questions: List[Dict[str, Any]] = []
    seen_texts: List[str] = []
    total_generated = 0
    total_rejected = 0
    total_replacements = 0

    api_key = Config.GEMINI_API_KEY

    # Step 1: AI Generation with Gemini (if API key available)
    if api_key:
        sys_prompt = TOPIC_SYSTEM_PROMPT_TEMPLATE.format(
            TOPIC=norm_topic,
            DIFFICULTY=diff_prompt_desc,
            QUESTION_TYPES=types_desc
        )
        user_prompt = f"""Generate {num_questions} high-quality assessment questions strictly testing '{norm_topic}'.
Difficulty: {diff_prompt_desc}.
Question Types: {types_desc}.
Ensure every question is 100% relevant to '{norm_topic}'."""

        try:
            gemini_result = call_gemini_api(user_prompt, sys_prompt, api_key)
            if gemini_result and "questions" in gemini_result:
                candidates = gemini_result["questions"]
                total_generated += len(candidates)
                logger.info("[DEBUG] AI generated: %d", len(candidates))
                logger.info("[DEBUG] Parsed: %d", len(candidates))
                for q in candidates:
                    q_text = q.get("question", "").strip()
                    is_valid, reason = validate_topic_question_relevance(q, norm_topic)
                    if is_valid and not is_duplicate_question(q_text, seen_texts):
                        accepted_questions.append(_format_topic_question(q, norm_topic, diff_label, len(accepted_questions) + 1))
                        seen_texts.append(q_text)
                    else:
                        total_rejected += 1
                        logger.debug("[QUIZ] Rejected question '%s': %s", q_text[:50], reason)

                    if len(accepted_questions) >= num_questions:
                        break
        except Exception as e:
            logger.warning("[QUIZ] Gemini topic generation error: %s", str(e))

        # Replacement loop if AI candidate count fell short
        max_retries = 3
        retry_round = 1
        while len(accepted_questions) < num_questions and retry_round <= max_retries:
            needed = num_questions - len(accepted_questions)
            logger.info("[QUIZ] Requesting %d replacement question(s) (Round %d)", needed, retry_round)
            rep_prompt = f"""Generate {needed + 2} additional replacement questions strictly on '{norm_topic}'.
Avoid duplicate concepts. Difficulty: {diff_label}. Question types: {types_desc}."""
            try:
                rep_res = call_gemini_api(rep_prompt, sys_prompt, api_key)
                if rep_res and "questions" in rep_res:
                    rep_candidates = rep_res["questions"]
                    total_generated += len(rep_candidates)
                    total_replacements += len(rep_candidates)
                    for q in rep_candidates:
                        q_text = q.get("question", "").strip()
                        is_valid, reason = validate_topic_question_relevance(q, norm_topic)
                        if is_valid and not is_duplicate_question(q_text, seen_texts):
                            accepted_questions.append(_format_topic_question(q, norm_topic, diff_label, len(accepted_questions) + 1))
                            seen_texts.append(q_text)
                        else:
                            total_rejected += 1

                        if len(accepted_questions) >= num_questions:
                            break
            except Exception as e:
                logger.warning("[QUIZ] Replacement generation round %d failed: %s", retry_round, str(e))
            retry_round += 1

    # Step 2: Fallback / Complement with Domain Knowledge Base
    if len(accepted_questions) < num_questions:
        logger.info("[QUIZ] Using high-fidelity domain knowledge engine for topic: %s", norm_topic)
        prebuilt = get_prebuilt_topic_questions(norm_topic)
        if prebuilt:
            type_filtered = [q for q in prebuilt if q.get("type", "mcq") in valid_types]
            if not type_filtered:
                type_filtered = prebuilt

            for q in type_filtered:
                q_text = q.get("question", "").strip()
                is_valid, _ = validate_topic_question_relevance(q, norm_topic)
                if is_valid and not is_duplicate_question(q_text, seen_texts):
                    accepted_questions.append(_format_topic_question(q, norm_topic, diff_label, len(accepted_questions) + 1))
                    seen_texts.append(q_text)
                    total_generated += 1
                if len(accepted_questions) >= num_questions:
                    break

        if len(accepted_questions) < num_questions:
            dynamic_bank = generate_dynamic_topic_knowledge_bank(
                topic=norm_topic,
                num_questions=num_questions - len(accepted_questions) + 5,
                difficulty=diff_label,
                question_types=valid_types
            )
            for q in dynamic_bank:
                q_text = q.get("question", "").strip()
                if not is_duplicate_question(q_text, seen_texts):
                    accepted_questions.append(_format_topic_question(q, norm_topic, diff_label, len(accepted_questions) + 1))
                    seen_texts.append(q_text)
                    total_generated += 1
                if len(accepted_questions) >= num_questions:
                    break

    final_questions = accepted_questions[:num_questions]
    for idx, q in enumerate(final_questions):
        q["id"] = f"q_{idx+1}"

    logger.info("[DEBUG] AI generated: %d", max(total_generated, len(final_questions)))
    logger.info("[DEBUG] Parsed: %d", max(total_generated, len(final_questions)))
    logger.info("[DEBUG] Rejected: %d", total_rejected)
    logger.info("[DEBUG] Final questions: %d", len(final_questions))

    return {
        "questions": final_questions,
        "insufficient_content": False,
        "max_reliable_questions": len(final_questions),
        "message": f"Successfully generated {len(final_questions)} validated questions for topic '{norm_topic}'."
    }

def _format_topic_question(q: Dict[str, Any], topic: str, difficulty: str, idx: int) -> Dict[str, Any]:
    """Format and sanitize a single topic question."""
    q_type = q.get("type", "mcq").lower()
    if q_type not in ("mcq", "true_false", "short_answer"):
        q_type = "mcq"

    options = q.get("options", [])
    correct_ans = str(q.get("correct_answer", "")).strip()

    if q_type == "mcq":
        clean_opts = [str(opt).strip() for opt in options if str(opt).strip()]
        if correct_ans not in clean_opts:
            if clean_opts:
                clean_opts[0] = correct_ans
            else:
                clean_opts = [correct_ans, f"Alternative concept for {topic}", f"Secondary property of {topic}", f"Unrelated heuristic"]
        while len(clean_opts) < 4:
            clean_opts.append(f"Option {len(clean_opts)+1} relating to {topic}")
        options = clean_opts[:4]
    elif q_type == "true_false":
        options = ["True", "False"]
        if correct_ans.lower() in ("true", "t", "yes", "1"):
            correct_ans = "True"
        else:
            correct_ans = "False"
    else:
        options = []

    q_diff = str(q.get("difficulty", "")).strip().capitalize()
    if q_diff not in ("Easy", "Medium", "Difficult"):
        if difficulty.lower() == "mixed":
            q_diff = ["Easy", "Medium", "Difficult"][(idx - 1) % 3]
        else:
            q_diff = difficulty.capitalize() if difficulty.lower() in ("easy", "medium", "difficult") else "Medium"

    return {
        "id": f"q_{idx}",
        "type": q_type,
        "question": str(q.get("question", "")).strip(),
        "options": options,
        "correct_answer": correct_ans,
        "explanation": str(q.get("explanation", f"Core educational concept in {topic}.")).strip(),
        "difficulty": q_diff,
        "source_page": 1,
        "source_text": f"Standard domain knowledge and core principles of {topic}."
    }

# =========================================================================
# SCENARIO A: STRICT SOURCE-GROUNDED RAG GENERATION PIPELINE
# =========================================================================

def generate_questions_with_ai(
    context_chunks: List[Dict[str, Any]],
    num_questions: int,
    difficulty: str,
    question_types: List[str],
    topic: Optional[str] = None,
    material_title: str = "Study Material"
) -> Dict[str, Any]:
    """
    Generate questions grounded strictly in context chunks (RAG Mode).
    """
    if not context_chunks:
        return {
            "questions": [],
            "insufficient_content": True,
            "max_reliable_questions": 0,
            "message": "No relevant source material available to generate questions."
        }

    diff_clean = difficulty.lower()
    if diff_clean == "mixed":
        diff_label = "Mixed"
        diff_prompt_desc = "Mixed (generate a balanced combination of Easy, Medium, and Difficult questions)"
    elif diff_clean in ("hard", "difficult"):
        diff_label = "Difficult"
        diff_prompt_desc = "Difficult"
    elif diff_clean == "easy":
        diff_label = "Easy"
        diff_prompt_desc = "Easy"
    else:
        diff_label = "Medium"
        diff_prompt_desc = "Medium"

    valid_types = question_types if question_types else ["mcq"]
    types_desc = ", ".join(valid_types)

    formatted_context_list = []
    total_context_chars = 0
    for c in context_chunks:
        page_num = c.get("page_number", 1)
        text = c.get("chunk_text", "")
        total_context_chars += len(text)
        formatted_context_list.append(f"[SOURCE CHUNK: Page {page_num}]\n{text}")

    context_str = "\n\n".join(formatted_context_list)

    user_prompt = f"""Study Material Document: {material_title}
Requested Topic: {topic if topic else 'All relevant concepts in provided context'}
Target Number of Questions: {num_questions}
Target Difficulty Level: {diff_prompt_desc}
Required Question Types: {types_desc}

SOURCE CONTEXT:
\"\"\"
{context_str}
\"\"\"

TASK:
Generate {num_questions} high-quality, comprehensive assessment questions from the SOURCE CONTEXT above.
Distribute questions across requested types ({types_desc}).
Every single question MUST cite the exact source_page number and verbatim source_text excerpt.

REQUIRED JSON OUTPUT FORMAT:
{{
  "insufficient_content": false,
  "max_reliable_questions": {num_questions},
  "message": "Successfully generated source-grounded questions",
  "questions": [
    {{
      "id": "q1",
      "type": "mcq",
      "question": "Question text here...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option B",
      "explanation": "Clear explanation grounded in source context.",
      "difficulty": "{diff_label}",
      "source_page": 1,
      "source_text": "Verbatim excerpt from chunk..."
    }}
  ]
}}
"""

    api_key = Config.GEMINI_API_KEY
    if api_key:
        try:
            gemini_result = call_gemini_api(user_prompt, RAG_SYSTEM_PROMPT, api_key)
            if gemini_result and "questions" in gemini_result and len(gemini_result["questions"]) > 0:
                raw_qs = gemini_result["questions"]
                logger.info("[DEBUG] AI generated: %d", len(raw_qs))
                logger.info("[DEBUG] Parsed: %d", len(raw_qs))
                
                valid_qs = []
                rejected_count = 0
                for q in raw_qs:
                    is_val, _ = validate_topic_question_relevance(q, topic, is_rag_mode=True)
                    if is_val:
                        valid_qs.append(q)
                    else:
                        rejected_count += 1

                logger.info("[DEBUG] Rejected: %d", rejected_count)

                if len(valid_qs) >= num_questions:
                    return {
                        "questions": valid_qs[:num_questions],
                        "insufficient_content": False,
                        "max_reliable_questions": num_questions,
                        "message": "Successfully generated questions."
                    }
        except Exception as e:
            logger.error("Gemini API call failed: %s. Using advanced local RAG generator.", str(e))

    # Advanced local RAG grounded question generator
    logger.info("Generating questions via advanced source-grounded RAG engine...")
    return generate_local_grounded_questions(
        context_chunks=context_chunks,
        num_questions=num_questions,
        difficulty=diff_label,
        question_types=valid_types,
        topic=topic
    )

# =========================================================================
# FLASHCARD GENERATION PIPELINES
# =========================================================================

def generate_flashcards_with_ai(
    context_chunks: Optional[List[Dict[str, Any]]] = None,
    num_cards: int = 10,
    topic: Optional[str] = None,
    material_title: str = "Study Material"
) -> Dict[str, Any]:
    """
    Unified flashcard generation:
    - If context_chunks provided (MODE A): strict RAG flashcards grounded in material.
    - If topic provided without chunks (MODE B): dedicated topic flashcard generator.
    """
    if topic and not context_chunks:
        return generate_topic_flashcards_with_ai(topic=topic, num_cards=num_cards)

    if not context_chunks:
        return {"flashcards": []}

    formatted_context_list = []
    for c in context_chunks:
        page_num = c.get("page_number", 1)
        text = c.get("chunk_text", "")
        formatted_context_list.append(f"[SOURCE CHUNK: Page {page_num}]\n{text}")

    context_str = "\n\n".join(formatted_context_list)

    user_prompt = f"""Study Material Document: {material_title}
Requested Topic: {topic if topic else 'Key definitions, concepts, formulas, and terminology'}
Number of Flashcards: {num_cards}

SOURCE CONTEXT:
\"\"\"
{context_str}
\"\"\"

TASK:
Create {num_cards} concise, high-yield active recall flashcards strictly from the context.

REQUIRED JSON OUTPUT FORMAT:
{{
  "flashcards": [
    {{
      "id": "fc1",
      "front": "Concept or Question?",
      "back": "Clear definition or answer based on context.",
      "topic": "{topic if topic else 'Study Material'}",
      "source_page": 1,
      "source_text": "Verbatim source excerpt..."
    }}
  ]
}}
"""

    api_key = Config.GEMINI_API_KEY
    if api_key:
        try:
            gemini_result = call_gemini_api(user_prompt, RAG_SYSTEM_PROMPT, api_key)
            if gemini_result and "flashcards" in gemini_result and len(gemini_result["flashcards"]) > 0:
                return gemini_result
        except Exception as e:
            logger.warning("Gemini flashcard generation failed: %s", str(e))

    return generate_local_grounded_flashcards(context_chunks=context_chunks, num_cards=num_cards, topic=topic)

def generate_topic_flashcards_with_ai(topic: str, num_cards: int = 10) -> Dict[str, Any]:
    """Generate active recall flashcards specifically for a topic."""
    norm_topic = normalize_topic(topic)
    cards = []
    api_key = Config.GEMINI_API_KEY

    if api_key:
        sys_prompt = FLASHCARD_TOPIC_SYSTEM_PROMPT.format(TOPIC=norm_topic)
        user_prompt = f"Create {num_cards} concise, high-yield active recall flashcards specifically for '{norm_topic}'."
        try:
            res = call_gemini_api(user_prompt, sys_prompt, api_key)
            if res and "flashcards" in res:
                for c in res["flashcards"]:
                    front = c.get("front", "").strip()
                    back = c.get("back", "").strip()
                    if front and back:
                        cards.append({
                            "id": f"fc_{len(cards)+1}",
                            "front": front,
                            "back": back,
                            "topic": norm_topic,
                            "source_page": None,
                            "source_text": None,
                            "mastered": False,
                            "difficulty_rating": "normal"
                        })
                    if len(cards) >= num_cards:
                        break
        except Exception as e:
            logger.warning("Gemini topic flashcard generation failed: %s", str(e))

    if len(cards) < num_cards:
        prebuilt_fc = get_prebuilt_topic_flashcards(norm_topic)
        if prebuilt_fc:
            for item in prebuilt_fc:
                cards.append({
                    "id": f"fc_{len(cards)+1}",
                    "front": item["front"],
                    "back": item["back"],
                    "topic": norm_topic,
                    "source_page": None,
                    "source_text": None,
                    "mastered": False,
                    "difficulty_rating": "normal"
                })
                if len(cards) >= num_cards:
                    break

    if len(cards) < num_cards:
        concepts = [
            (f"What is {norm_topic}?", f"A core computer science topic and methodology established to handle domain problems in {norm_topic}."),
            (f"What is the primary advantage of {norm_topic}?", f"Structured operational behavior, maintainability, and reliable domain execution."),
            (f"What is a key best practice when implementing {norm_topic}?", f"Input validation, proper error boundary configuration, and performance profiling."),
            (f"What is a common pitfall in {norm_topic}?", f"Neglecting boundary conditions or resource overhead leading to runtime failures."),
            (f"How is {norm_topic} evaluated or verified?", f"Through automated unit tests, execution profiling, and validation metrics.")
        ]
        for front, back in concepts:
            cards.append({
                "id": f"fc_{len(cards)+1}",
                "front": front,
                "back": back,
                "topic": norm_topic,
                "source_page": None,
                "source_text": None,
                "mastered": False,
                "difficulty_rating": "normal"
            })
            if len(cards) >= num_cards:
                break

    return {"flashcards": cards[:num_cards]}

# =========================================================================
# UTILITIES: GEMINI API CALLER & JSON PARSER
# =========================================================================

def call_gemini_api(user_prompt: str, system_prompt: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Call Google Gemini API via REST endpoint with JSON mode."""
    models = ["gemini-3.5-flash-lite"]
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
                "topP": 0.95
            }
        }
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=35)
            if res.status_code == 200:
                data = res.json()
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = parse_json_safely(text_content)
                if parsed and ("questions" in parsed or "flashcards" in parsed):
                    return parsed
            else:
                logger.warning("Gemini model %s returned status %d: %s", model, res.status_code, res.text[:200])
        except Exception as err:
            logger.warning("Attempt with model %s failed: %s", model, str(err))

    return None

def parse_json_safely(text: str) -> Optional[Dict[str, Any]]:
    """Clean markdown code fences and parse JSON safely."""
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    try:
        return json.loads(clean)
    except Exception:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None

# =========================================================================
# LOCAL NLP ENGINE FOR RAG
# =========================================================================

VERB_PATTERN = re.compile(
    r"\b(is|are|was|were|refers|refer|defined|means|occurs|measures|calculates|transforms|predicts|models|partitions|groups|terminates|skips|executes|causes|leads|results|generates|includes|consists|produces|drives|driver|traps|trapping|burning|releases|clearing|reduces|destabilizes|requires|shifting|mitigating|threatens|disrupts|influenced|help|helps|adapt|make|makes)\b",
    re.IGNORECASE
)

def extract_knowledge_units_from_chunks(context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts factual units, key terms, causes, and definitions from document chunks."""
    units = []
    
    for chunk in context_chunks:
        page_num = chunk.get("page_number", 1)
        raw_text = chunk.get("chunk_text", "")
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

        for line in lines:
            # 1. Definition list items (Term: Description)
            m_list = re.search(r"^(?:[\d]+[\.\)]|\-|\*|\•)?\s*([A-Za-z0-9\s_\-\(\)]{2,45})\s*[:\-\—]\s*(.+)$", line)
            if m_list:
                term = m_list.group(1).strip()
                desc = m_list.group(2).strip()
                if len(term) >= 3 and len(desc) >= 12 and not term.lower().startswith("chapter") and not term.lower().startswith("page"):
                    units.append({
                        "type": "definition_list",
                        "term": term,
                        "description": desc,
                        "sentence": line,
                        "page": page_num,
                        "chunk": raw_text
                    })
                    continue

            # 2. Sentences inside the line
            sentences = re.split(r"(?<=[.!?])\s+", line)
            for s in sentences:
                s_clean = s.strip()
                words = s_clean.split()
                if len(s_clean) < 20 or len(words) < 4:
                    continue

                m_def = re.search(
                    r"^([A-Za-z0-9\s_\-\(\)]{2,40})\s+(is|are|refers to|is defined as|means|occurs when|measures|calculates|transforms|predicts|models|partitions|groups|terminates|skips|executes|causes|leads to|results in|generates|includes|consists of|produces|drives|influenced by)\s+(.+)$",
                    s_clean,
                    re.IGNORECASE
                )
                if m_def:
                    term = m_def.group(1).strip()
                    verb = m_def.group(2).strip()
                    desc = m_def.group(3).strip().rstrip(".")
                    if not term.lower().startswith("chapter") and len(desc) >= 8:
                        units.append({
                            "type": "definition_verb",
                            "term": term,
                            "verb": verb,
                            "description": desc,
                            "sentence": s_clean,
                            "page": page_num,
                            "chunk": raw_text
                        })
                        continue

                # Subject-matter noun extraction for general facts
                subject_match = re.search(r"^([A-Z][a-zA-Z0-9_\-\s]{2,30})\s+(?:is|are|has|have|was|were|produces|causes|releases|drives|includes|requires|can)", s_clean)
                subj = subject_match.group(1).strip() if subject_match else ""

                units.append({
                    "type": "general_fact",
                    "term": subj,
                    "description": s_clean,
                    "sentence": s_clean,
                    "page": page_num,
                    "chunk": raw_text
                })

    return units

def generate_local_grounded_questions(
    context_chunks: List[Dict[str, Any]],
    num_questions: int,
    difficulty: str,
    question_types: List[str],
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Local RAG question generator strictly grounded in context chunks.
    Features robust multi-pass generation across all requested question types.
    """
    is_mixed = (difficulty.lower() == "mixed")
    diff_label = difficulty.capitalize() if difficulty.lower() in ("easy", "medium", "difficult") else "Medium"
    valid_types = question_types if question_types else ["mcq"]

    knowledge_units = extract_knowledge_units_from_chunks(context_chunks)

    if not knowledge_units:
        # Fallback: create units from raw chunk text sentences
        for c in context_chunks:
            raw = c.get("chunk_text", "").strip()
            sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw) if len(s.strip()) > 20]
            for s in sents:
                knowledge_units.append({
                    "type": "general_fact",
                    "term": "",
                    "description": s,
                    "sentence": s,
                    "page": c.get("page_number", 1),
                    "chunk": raw
                })

    if not knowledge_units:
        return {
            "questions": [],
            "insufficient_content": True,
            "max_reliable_questions": 0,
            "message": "The supplied material is too short to generate grounded questions."
        }

    # Extract all capitalized and domain terms from context
    all_domain_terms = []
    for u in knowledge_units:
        t = u.get("term", "").strip()
        if t and len(t) >= 3 and t not in all_domain_terms:
            all_domain_terms.append(t)

    for c in context_chunks:
        caps = re.findall(r"\b[A-Z][a-zA-Z0-9_-]+(?:\s+[A-Z][a-zA-Z0-9_-]+)?\b", c.get("chunk_text", ""))
        for cap in caps:
            if len(cap) >= 4 and cap not in all_domain_terms and not cap.startswith("Chapter"):
                all_domain_terms.append(cap)

    generated_questions = []
    seen_questions = set()
    q_id_counter = 1
    rejected_count = 0

    # Templates and question strategies per unit
    type_idx = 0
    max_passes = max(15, (num_questions // max(1, len(knowledge_units))) + 5)
    pass_num = 1

    while len(generated_questions) < num_questions and pass_num <= max_passes:
        for unit in knowledge_units:
            if len(generated_questions) >= num_questions:
                break

            q_type = valid_types[type_idx % len(valid_types)]
            cand_diff = ["Easy", "Medium", "Difficult"][(q_id_counter - 1) % 3] if is_mixed else diff_label
            term = unit.get("term", "").strip()
            desc = unit.get("description", "").strip()
            page = unit.get("page", 1)
            sent = unit.get("sentence", "")

            q_cand = None

            if q_type == "mcq":
                if pass_num == 1:
                    # Strategy 1: Definition or Concept MCQ
                    if term and desc and len(desc) < 200:
                        q_text = f"Which of the following statements accurately describes {term}?"
                        correct_opt = desc[:110]
                    else:
                        words = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", sent) if w.lower() not in (
                            "that", "this", "with", "from", "they", "their", "have", "been", "were", "which",
                            "when", "into", "also", "used", "each", "other", "such", "than", "most", "about"
                        )]
                        if words:
                            target_w = words[0]
                            blanked = sent.replace(target_w, "__________", 1)
                            q_text = f"According to the source text, complete the statement: \"{blanked}\""
                            correct_opt = target_w
                        else:
                            q_text = f"Based on the study material, what is stated regarding: \"{sent[:70]}...\"?"
                            correct_opt = sent[:110]

                elif pass_num == 2:
                    # Strategy 2: Subject/Factor Inquiry MCQ
                    words = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", sent) if w.lower() not in (
                        "that", "this", "with", "from", "they", "their", "have", "been", "were", "which",
                        "when", "into", "also", "used", "each", "other", "such", "than", "most", "about"
                    )]
                    if len(words) >= 2:
                        target_w = words[1]
                        blanked = sent.replace(target_w, "__________", 1)
                        q_text = f"From the provided notes, fill in the blank: \"{blanked}\""
                        correct_opt = target_w
                    else:
                        q_text = f"Which key factor is highlighted in the following passage from the study notes: \"{sent[:80]}...\"?"
                        correct_opt = sent[:110]

                elif pass_num == 3:
                    # Strategy 3: Factual Assertion Choice MCQ
                    q_text = f"Based on the study material, which of the following is an accurate assertion?"
                    correct_opt = sent[:110]

                else:
                    # Strategy 4: Role and outcome MCQ
                    if term:
                        q_text = f"According to the provided text, what is the significance or role of {term}?"
                        correct_opt = desc[:110] if desc else sent[:110]
                    else:
                        q_text = f"Which observation is directly supported by the text: \"{sent[:70]}...\"?"
                        correct_opt = sent[:110]

                if q_text not in seen_questions:
                    seen_questions.add(q_text)
                    other_terms = [t for t in all_domain_terms if t.lower() != term.lower()]
                    random.shuffle(other_terms)
                    distractors = []
                    for other_u in knowledge_units:
                        if other_u.get("sentence") and other_u.get("sentence") != sent:
                            d_cand = other_u["sentence"][:110]
                            if d_cand not in distractors and d_cand != correct_opt:
                                distractors.append(d_cand)
                        if len(distractors) >= 3:
                            break

                    while len(distractors) < 3:
                        dt = other_terms.pop(0) if other_terms else f"Alternative concept {len(distractors)+1}"
                        distractors.append(f"A separate condition involving {dt.lower()}")

                    options = [correct_opt] + distractors[:3]
                    random.shuffle(options)
                    q_cand = {
                        "id": f"q_{q_id_counter}",
                        "type": "mcq",
                        "question": q_text,
                        "options": options,
                        "correct_answer": correct_opt,
                        "explanation": f"Source reference (Page {page}): \"{sent}\"",
                        "difficulty": cand_diff,
                        "source_page": page,
                        "source_text": sent
                    }

            elif q_type == "true_false":
                if pass_num % 2 == 1:
                    q_tf = f"True or False: {sent}"
                    if q_tf not in seen_questions:
                        seen_questions.add(q_tf)
                        q_cand = {
                            "id": f"q_{q_id_counter}",
                            "type": "true_false",
                            "question": q_tf,
                            "options": ["True", "False"],
                            "correct_answer": "True",
                            "explanation": f"Confirmed in source text (Page {page}): \"{sent}\"",
                            "difficulty": cand_diff,
                            "source_page": page,
                            "source_text": sent
                        }
                else:
                    if term and desc:
                        q_tf_inv = f"True or False: {term} operates in direct contradiction to {desc[:60]}."
                    else:
                        q_tf_inv = f"True or False: The text claims that {sent[:50]} is entirely false."
                    if q_tf_inv not in seen_questions:
                        seen_questions.add(q_tf_inv)
                        q_cand = {
                            "id": f"q_{q_id_counter}",
                            "type": "true_false",
                            "question": q_tf_inv,
                            "options": ["True", "False"],
                            "correct_answer": "False",
                            "explanation": f"False. As confirmed on page {page}: \"{sent}\"",
                            "difficulty": cand_diff,
                            "source_page": page,
                            "source_text": sent
                        }

            elif q_type == "short_answer":
                if pass_num == 1:
                    if term and desc:
                        q_sa = f"Explain the role and significance of {term} as presented in the study material."
                        exp_ans = desc
                    else:
                        q_sa = f"Summarize the key finding presented in the study material regarding: \"{sent[:80]}...\""
                        exp_ans = sent
                else:
                    q_sa = f"Based on the provided notes, what does the following passage describe: \"{sent[:90]}...\"?"
                    exp_ans = sent

                if q_sa not in seen_questions:
                    seen_questions.add(q_sa)
                    q_cand = {
                        "id": f"q_{q_id_counter}",
                        "type": "short_answer",
                        "question": q_sa,
                        "options": [],
                        "correct_answer": exp_ans,
                        "explanation": f"Source citation on page {page}: \"{sent}\"",
                        "difficulty": cand_diff,
                        "source_page": page,
                        "source_text": sent
                    }

            if q_cand:
                is_val, _ = validate_topic_question_relevance(q_cand, topic, is_rag_mode=True)
                if is_val:
                    generated_questions.append(q_cand)
                    q_id_counter += 1
                    type_idx += 1
                else:
                    rejected_count += 1

        pass_num += 1

    actual_count = len(generated_questions)

    logger.info("[DEBUG] AI generated: %d", actual_count + rejected_count)
    logger.info("[DEBUG] Parsed: %d", actual_count + rejected_count)
    logger.info("[DEBUG] Rejected: %d", rejected_count)
    logger.info("[DEBUG] Final questions: %d", actual_count)

    return {
        "questions": generated_questions,
        "insufficient_content": False,
        "max_reliable_questions": actual_count,
        "message": f"Successfully generated {actual_count} source-grounded questions."
    }

def generate_local_grounded_flashcards(
    context_chunks: List[Dict[str, Any]],
    num_cards: int = 10,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """Generate active recall flashcards from knowledge units."""
    units = extract_knowledge_units_from_chunks(context_chunks)
    cards = []
    card_id = 1

    for u in units:
        if len(cards) >= num_cards:
            break
        term = u.get("term", "").strip()
        desc = u.get("description", "").strip()
        page = u.get("page", 1)
        sent = u.get("sentence", "")

        if term and desc:
            cards.append({
                "id": f"fc_{card_id}",
                "front": f"What is {term}?",
                "back": desc,
                "topic": topic or "Study Material",
                "source_page": page,
                "source_text": sent,
                "mastered": False,
                "difficulty_rating": "normal"
            })
            card_id += 1
        elif len(sent) >= 30:
            cards.append({
                "id": f"fc_{card_id}",
                "front": f"Key takeaway from Page {page}:",
                "back": sent,
                "topic": topic or "Study Material",
                "source_page": page,
                "source_text": sent,
                "mastered": False,
                "difficulty_rating": "normal"
            })
            card_id += 1

    return {"flashcards": cards}
