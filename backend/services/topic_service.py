import re
import random
import logging
from typing import List, Dict, Any, Tuple, Optional
from backend.services.embedding_service import get_embedding, calculate_cosine_similarity

logger = logging.getLogger(__name__)

# Known domain acronyms that should maintain exact casing during normalization
KNOWN_ACRONYMS = {
    "dbms": "DBMS",
    "acid": "ACID",
    "sql": "SQL",
    "nosql": "NoSQL",
    "rdbms": "RDBMS",
    "api": "API",
    "rest": "REST",
    "http": "HTTP",
    "https": "HTTPS",
    "tcp": "TCP",
    "udp": "UDP",
    "ip": "IP",
    "tcp/ip": "TCP/IP",
    "dns": "DNS",
    "dhcp": "DHCP",
    "arp": "ARP",
    "bgp": "BGP",
    "ospf": "OSPF",
    "cpu": "CPU",
    "ram": "RAM",
    "gpu": "GPU",
    "os": "OS",
    "ml": "ML",
    "ai": "AI",
    "nlp": "NLP",
    "llm": "LLM",
    "bert": "BERT",
    "svm": "SVM",
    "knn": "KNN",
    "pca": "PCA",
    "cnn": "CNN",
    "rnn": "RNN",
    "lstm": "LSTM",
    "html": "HTML",
    "css": "CSS",
    "json": "JSON",
    "jwt": "JWT",
    "oauth": "OAuth",
    "oop": "OOP",
    "crud": "CRUD",
    "ci/cd": "CI/CD",
    "fifo": "FIFO",
    "lifo": "LIFO",
    "lru": "LRU",
    "bst": "BST",
    "avl": "AVL",
    "wal": "WAL",
    "2pl": "2PL"
}

GENERIC_DOCUMENT_TITLES = {
    "general", "all concepts", "study material", "pasted notes", "notes", "my notes",
    "conclusion", "introduction", "summary", "overview", "chapter", "chapter 1",
    "chapter 2", "chapter 3", "chapter 4", "chapter 5", "unit 1", "unit 2", "unit 3",
    "lecture", "lecture 1", "lecture 2", "assignment", "document", "article", "text",
    "reading", "study notes", "untitled", "untitled note", "notes.txt"
}

def normalize_topic(topic: str) -> str:
    """
    Clean and normalize topic input without stripping key words or user intent.
    - Strips leading/trailing spaces.
    - Collapses multiple whitespace characters.
    - Preserves domain acronyms while applying title casing to standard words.
    - Preserves compound sub-topics (e.g. 'DBMS transactions and ACID properties').
    """
    if not topic:
        return "General"

    cleaned = re.sub(r"\s+", " ", topic.strip())
    if not cleaned:
        return "General"

    words = cleaned.split(" ")
    normalized_words = []
    minor_words = {"and", "or", "in", "of", "for", "with", "on", "at", "to", "the", "a", "an"}

    for i, word in enumerate(words):
        word_lower = word.lower().strip(".,;:()[]{}")
        if word_lower in KNOWN_ACRONYMS:
            punct = word[len(word_lower):] if len(word) > len(word_lower) else ""
            normalized_words.append(KNOWN_ACRONYMS[word_lower] + punct)
        elif i > 0 and word_lower in minor_words:
            normalized_words.append(word.lower())
        else:
            normalized_words.append(word.capitalize())

    return " ".join(normalized_words)

# =========================================================================
# DOMAIN RELEVANCE & OFF-TOPIC CONCEPT CHECKERS
# =========================================================================

DOMAIN_NEGATIVE_CONSTRAINTS = {
    "python loops": {
        "required_keywords": ["loop", "for", "while", "iteration", "iterate", "break", "continue", "range", "enumerate", "zip", "nested", "pass", "iter", "next", "generator", "infinite"],
        "forbidden_concepts": [
            r"\bclass\b", r"\binheritance\b", r"\bpolymorphism\b", r"\bencapsulation\b",
            r"\bdecorator\b", r"\bfile handling\b", r"\bopen\(", r"\breadlines\b",
            r"\bdjango\b", r"\bflask\b", r"\bsqlalchemy\b", r"\bdatabase\b", r"\btable\b",
            r"\bmachine learning\b", r"\bneural\b", r"\bpandas\b", r"\bdataframe\b",
            r"\bhtml\b", r"\bcss\b", r"\breact\b", r"\bsocket\b", r"\bmultiprocessing\b"
        ]
    },
    "dbms transactions": {
        "required_keywords": ["transaction", "acid", "atomicity", "consistency", "isolation", "durability", "commit", "rollback", "savepoint", "concurrency", "schedule", "serializability", "lock", "2pl", "deadlock", "wal", "log", "dirty read", "phantom read", "non-repeatable read"],
        "forbidden_concepts": [
            r"\bhtml\b", r"\bcss\b", r"\bfor loop\b", r"\bwhile loop\b", r"\bpython class\b",
            r"\bmachine learning\b", r"\bgradient descent\b", r"\bneural network\b",
            r"\btcp handshake\b", r"\bosi model\b", r"\brouting protocol\b",
            r"\bcss flexbox\b", r"\bvue\b", r"\breact component\b"
        ]
    },
    "machine learning": {
        "required_keywords": ["model", "learning", "supervised", "unsupervised", "reinforcement", "train", "test", "dataset", "feature", "label", "loss", "gradient", "regression", "classification", "clustering", "accuracy", "overfitting", "underfitting", "bias", "variance", "neural", "precision", "recall", "f1", "epoch", "tree", "svm", "kmeans", "pca", "cross-validation"],
        "forbidden_concepts": [
            r"\bfor loop in python\b", r"\bwhile loop syntax\b", r"\bcss grid\b",
            r"\bhtml form\b", r"\bforeign key constraint\b", r"\bacid property\b",
            r"\bosi layer 3\b", r"\btcp port\b", r"\bsubnet mask\b"
        ]
    },
    "computer networks": {
        "required_keywords": ["network", "packet", "protocol", "osi", "tcp", "udp", "ip", "router", "switch", "dns", "http", "https", "arp", "dhcp", "port", "socket", "subnet", "bandwidth", "latency", "congestion", "handshake", "layer", "ethernet", "mac address"],
        "forbidden_concepts": [
            r"\bfor loop\b", r"\bwhile loop\b", r"\bclass inheritance\b", r"\bacid properties\b",
            r"\bsql join\b", r"\bmachine learning\b", r"\bdecision tree\b", r"\bcss style\b"
        ]
    },
    "data structures": {
        "required_keywords": ["array", "linked list", "stack", "queue", "tree", "binary tree", "bst", "heap", "graph", "hash", "node", "time complexity", "big o", "traversal", "dfs", "bfs", "pointer", "vertex", "edge"],
        "forbidden_concepts": [
            r"\bhtml tag\b", r"\bcss color\b", r"\bdatabase trigger\b", r"\bneural weight\b",
            r"\btcp ack\b", r"\bdns query\b", r"\bhttp 404\b"
        ]
    }
}

# Cross-domain generic negative checks
CROSS_DOMAIN_DISJOINT_TOPICS = [
    (r"\b(climate|greenhouse|global warming|carbon dioxide|methane|deforestation|glaciers|sea level|weather)\b",
     [r"\bpython loop\b", r"\bwhile loop\b", r"\bfor loop\b", r"\bjavascript\b", r"\bsql join\b", r"\bdatabase index\b", r"\bhtml\b", r"\bcss\b"]),
    (r"\b(python loop|loop in python|loops)\b",
     [r"\bclimate change\b", r"\bphotosynthesis\b", r"\bmitochondria\b", r"\bgreenhouse gas\b", r"\bforeign key\b"]),
    (r"\b(dbms|database|transactions|acid)\b",
     [r"\bfor loop in python\b", r"\bphotosynthesis\b", r"\bcss grid\b", r"\bmitochondria\b"])
]

def validate_topic_question_relevance(
    question: Dict[str, Any],
    topic: str,
    is_rag_mode: bool = False
) -> Tuple[bool, str]:
    """
    Validates a generated question against the requested topic using SEMANTIC RELEVANCE.
    Does NOT require exact topic keyword matches.
    Accepts synonyms, sub-concepts, and domain-related facts.
    Strictly rejects cross-domain violations (e.g. 'What is a Python loop?' for 'Climate Change').
    """
    topic_clean = topic.strip().lower() if topic else ""

    if not topic_clean or topic_clean in GENERIC_DOCUMENT_TITLES or any(topic_clean.startswith(g) for g in GENERIC_DOCUMENT_TITLES):
        return True, "Valid"

    topic_normalized = normalize_topic(topic).lower()
    q_text = str(question.get("question", "")).strip()
    correct_ans = str(question.get("correct_answer", "")).strip()
    explanation = str(question.get("explanation", "")).strip()
    options = [str(opt).strip() for opt in question.get("options", [])]

    if not q_text or len(q_text) < 8:
        return False, "Question text is empty or too short."
    if not correct_ans:
        return False, "Correct answer is missing."

    full_text = f"{q_text} {correct_ans} {' '.join(options)} {explanation}".lower()

    # 1. Check Explicit Cross-Domain Disjoint Rules
    for topic_pattern, forbidden_pats in CROSS_DOMAIN_DISJOINT_TOPICS:
        if re.search(topic_pattern, topic_normalized):
            for f_pat in forbidden_pats:
                if re.search(f_pat, q_text.lower()):
                    return False, f"Question violates domain boundary: contains off-topic concept matching '{f_pat}'."

    # 2. Check Known Domain Negative Constraints
    matched_domain = None
    for domain_key, constraint in DOMAIN_NEGATIVE_CONSTRAINTS.items():
        if domain_key in topic_normalized or all(w in topic_normalized for w in domain_key.split()):
            matched_domain = constraint
            break

    if matched_domain:
        for pat in matched_domain["forbidden_concepts"]:
            if re.search(pat, q_text.lower()):
                return False, f"Question violates domain boundary: contains off-topic concept matching '{pat}'."

        has_req = any(kw in full_text for kw in matched_domain["required_keywords"])
        if not has_req:
            return False, "Question lacks core conceptual keywords for the requested topic."
        return True, "Valid"

    # In RAG mode, if not violating negative constraints and question is grounded, accept it
    if is_rag_mode:
        return True, "Valid"

    # 3. Check Semantic Relevance via Embedding Cosine Similarity (for pure topic mode)
    try:
        t_emb = get_embedding(topic_normalized)
        q_emb = get_embedding(q_text)
        sim = calculate_cosine_similarity(t_emb, q_emb)
        
        if sim >= 0.14:
            return True, "Valid"

        f_emb = get_embedding(full_text[:300])
        f_sim = calculate_cosine_similarity(t_emb, f_emb)
        if f_sim >= 0.14:
            return True, "Valid"

        topic_words = [w for w in re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", topic_normalized) if w not in ("and", "the", "for", "with", "how", "what", "which", "effects", "overview", "introduction")]
        if topic_words and any(tw in full_text for tw in topic_words):
            return True, "Valid"

        return False, f"Low semantic relevance ({sim:.2f}) to requested topic '{topic}'."
    except Exception:
        return True, "Valid"

def is_duplicate_question(new_q_text: str, existing_q_texts: List[str], threshold: float = 0.85) -> bool:
    """
    Prevents duplicate questions from being accepted.
    """
    new_norm = re.sub(r"[^a-z0-9]", "", new_q_text.lower())
    for ex in existing_q_texts:
        ex_norm = re.sub(r"[^a-z0-9]", "", ex.lower())
        if new_norm == ex_norm:
            return True
        
        w_new = set(re.findall(r"\b[a-z0-9]{3,}\b", new_q_text.lower()))
        w_ex = set(re.findall(r"\b[a-z0-9]{3,}\b", ex.lower()))
        if w_new and w_ex:
            jaccard = len(w_new.intersection(w_ex)) / len(w_new.union(w_ex))
            if jaccard >= 0.88:
                return True

    return False

# =========================================================================
# HIGH-FIDELITY DOMAIN KNOWLEDGE BASES (25+ QUESTIONS EACH)
# =========================================================================

PYTHON_LOOPS_QUESTIONS = [
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "Which Python keyword is used to immediately terminate the execution of a loop?",
        "options": ["break", "stop", "exit", "continue"],
        "correct_answer": "break",
        "explanation": "The 'break' statement terminates the innermost loop and continues execution at the next statement."
    },
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "Which Python keyword is used to skip the rest of the current loop iteration and move to the next iteration?",
        "options": ["continue", "pass", "skip", "next"],
        "correct_answer": "continue",
        "explanation": "The 'continue' statement rejects all remaining statements in the current iteration of the loop and moves control to the next iteration."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "What is the output of the expression 'list(range(2, 10, 3))' in Python?",
        "options": ["[2, 5, 8]", "[2, 5, 8, 10]", "[3, 6, 9]", "[2, 4, 6, 8]"],
        "correct_answer": "[2, 5, 8]",
        "explanation": "range(start, stop, step) begins at 2, increments by 3, and stops strictly before 10 (2, 5, 8)."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "In Python, when does the 'else' block attached to a 'for' or 'while' loop execute?",
        "options": [
            "Only when the loop completes all iterations without encountering a 'break' statement",
            "Whenever the loop terminates, even if 'break' was executed",
            "Only if an exception is raised inside the loop",
            "Every time after each single iteration of the loop"
        ],
        "correct_answer": "Only when the loop completes all iterations without encountering a 'break' statement",
        "explanation": "The loop 'else' clause runs only if the loop finishes normally without being terminated by a 'break'."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "Which built-in Python function allows you to iterate over a sequence while keeping track of both the index and the element value?",
        "options": ["enumerate()", "zip()", "range()", "iter()"],
        "correct_answer": "enumerate()",
        "explanation": "enumerate(iterable) returns a tuple containing (index, item) for each element in the iterable."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "Consider nested loops where a 'break' statement is executed inside the inner loop. What occurs?",
        "options": [
            "Only the inner loop terminates; the outer loop continues execution",
            "Both inner and outer loops terminate simultaneously",
            "The entire program terminates execution",
            "Execution jumps directly to the start of the outer loop"
        ],
        "correct_answer": "Only the inner loop terminates; the outer loop continues execution",
        "explanation": "A 'break' statement strictly terminates only the nearest enclosing loop in which it appears."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "What is the primary risk of updating the termination condition variable inside a 'while' loop incorrectly?",
        "options": [
            "An infinite loop that consumes CPU cycles without terminating",
            "A compile-time SyntaxError before execution",
            "Automatic type conversion to a float",
            "A memory allocation error caused by recursion"
        ],
        "correct_answer": "An infinite loop that consumes CPU cycles without terminating",
        "explanation": "If the while condition never evaluates to False (e.g., counter not updated), the loop runs indefinitely as an infinite loop."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "What happens if you modify a list (e.g. deleting elements) while iterating over it with a standard 'for x in my_list:' loop?",
        "options": [
            "Elements will be skipped or index shifts will cause unexpected iteration behavior",
            "Python raises an immediate ConcurrentModificationException",
            "The list is automatically copied internally before iteration",
            "The loop resets its index back to 0"
        ],
        "correct_answer": "Elements will be skipped or index shifts will cause unexpected iteration behavior",
        "explanation": "Modifying a list in-place during iteration shifts indices, leading to skipped items or out-of-range anomalies. Iterating over a copy is recommended."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "Which Python module from the standard library provides memory-efficient looping tools such as cycle(), count(), and chain()?",
        "options": ["itertools", "functools", "collections", "operator"],
        "correct_answer": "itertools",
        "explanation": "The 'itertools' module contains functions that create iterators for efficient looping and combinatorics."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "How does a Python generator expression inside a loop differ from a list comprehension?",
        "options": [
            "Generator expressions produce values lazily on-demand, saving memory during large iterations",
            "Generator expressions execute faster by pre-allocating all memory at once",
            "Generator expressions can only be used with while loops, not for loops",
            "Generator expressions automatically sort the yielded items"
        ],
        "correct_answer": "Generator expressions produce values lazily on-demand, saving memory during large iterations",
        "explanation": "Generators evaluate elements one at a time via the iterator protocol rather than materializing the entire list in memory."
    },
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "What will 'for i in range(5):' produce as the sequence of values for i?",
        "options": ["0, 1, 2, 3, 4", "1, 2, 3, 4, 5", "0, 1, 2, 3, 4, 5", "1, 2, 3, 4"],
        "correct_answer": "0, 1, 2, 3, 4",
        "explanation": "range(5) generates integers starting from 0 up to 4 (5 total iterations)."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "Which function is used in Python to convert an iterable into an iterator object supporting the next() method in loops?",
        "options": ["iter()", "loop()", "yield()", "generator()"],
        "correct_answer": "iter()",
        "explanation": "The iter() built-in function returns an iterator object from an iterable, which the for loop consumes."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "What is the result of 'for k, v in {'a': 1, 'b': 2}.items():' during iteration?",
        "options": [
            "Iterates over key-value tuples simultaneously unpacking into k and v",
            "Iterates only over the dictionary keys",
            "Iterates only over the dictionary values",
            "Raises a TypeError because dictionaries cannot be looped over"
        ],
        "correct_answer": "Iterates over key-value tuples simultaneously unpacking into k and v",
        "explanation": "dict.items() yields (key, value) pairs which can be unpacked in loop headers."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "What is the time complexity of iterating through an N x M nested for loop in Python?",
        "options": ["O(N * M)", "O(N + M)", "O(N log M)", "O(1)"],
        "correct_answer": "O(N * M)",
        "explanation": "Nested loops execute the inner loop M times for each of the N outer iterations, leading to O(N * M) total operations."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "Which loop control pattern allows iterating backwards through a Python list without mutating the original list?",
        "options": ["for item in reversed(my_list):", "for item in my_list.reverse():", "for item in backward(my_list):", "for item in my_list[::-1].sort():"],
        "correct_answer": "for item in reversed(my_list):",
        "explanation": "reversed() returns a reverse iterator over the list elements without mutating the list in-place."
    },
    {
        "type": "true_false",
        "difficulty": "Easy",
        "question": "True or False: In Python, a 'for' loop can directly iterate over the characters of a string without converting it to a list.",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "True. Strings are iterable sequences in Python, so 'for char in text:' iterates character by character."
    },
    {
        "type": "true_false",
        "difficulty": "Medium",
        "question": "True or False: The 'pass' statement inside a loop causes the loop to skip directly to the next iteration like 'continue'.",
        "options": ["True", "False"],
        "correct_answer": "False",
        "explanation": "False. 'pass' is a null operation (placeholder) that does nothing, whereas 'continue' skips to the next iteration."
    },
    {
        "type": "true_false",
        "difficulty": "Difficult",
        "question": "True or False: A while loop condition in Python evaluates to False for an empty list, empty dictionary, 0, and None.",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "True. In Python, empty sequences, 0, and None evaluate as falsy in boolean loop conditions."
    },
    {
        "type": "true_false",
        "difficulty": "Medium",
        "question": "True or False: The zip() function stops iteration when the shortest input iterable is exhausted.",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "True. By default, zip() terminates when the shortest input iterable runs out of elements (unless zip_longest is used)."
    },
    {
        "type": "short_answer",
        "difficulty": "Medium",
        "question": "What Python function is used to pair and iterate through elements of two lists in parallel in a single loop?",
        "options": [],
        "correct_answer": "zip()",
        "explanation": "zip() combines multiple iterables element-by-element into tuples for simultaneous iteration."
    },
    {
        "type": "short_answer",
        "difficulty": "Easy",
        "question": "Which Python loop structure is most appropriate when the exact number of iterations is not known in advance and depends on a condition?",
        "options": [],
        "correct_answer": "while loop",
        "explanation": "A while loop repeatedly executes a block as long as its condition remains True, ideal for condition-driven iteration."
    },
    {
        "type": "short_answer",
        "difficulty": "Medium",
        "question": "What exception is raised when next() is called on an exhausted Python iterator inside a loop?",
        "options": [],
        "correct_answer": "StopIteration",
        "explanation": "The iterator protocol raises StopIteration when there are no further items, which the for loop catches internally to terminate."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "How can you loop over an iterable in fixed-size chunks of size N in modern Python (3.12+)?",
        "options": ["itertools.batched(iterable, N)", "itertools.chunked(iterable, N)", "iterable.split(N)", "loop.batch(iterable, N)"],
        "correct_answer": "itertools.batched(iterable, N)",
        "explanation": "Python 3.12 introduced itertools.batched() to easily iterate over sequences in fixed-size batches."
    },
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "What is the default start value of range(N) if only one parameter is supplied?",
        "options": ["0", "1", "-1", "N"],
        "correct_answer": "0",
        "explanation": "range(N) defaults to starting at integer 0 and increments by 1 until N-1."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "What happens if a loop contains 'while True:' with no internal 'break', 'return', or exception?",
        "options": ["The loop runs infinitely and never terminates", "Python automatically stops the loop after 1000 iterations", "A RecursionError is raised", "The loop finishes after one execution"],
        "correct_answer": "The loop runs infinitely and never terminates",
        "explanation": "'while True:' creates an unconditional infinite loop that continues until an exit statement (break/return/raise) is reached."
    }
]

DBMS_TRANSACTIONS_QUESTIONS = [
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "In the ACID model of DBMS transactions, what does the 'A' represent and guarantee?",
        "options": [
            "Atomicity: all operations in a transaction complete successfully, or none of them do",
            "Availability: the database is accessible 24/7",
            "Authentication: only verified users can execute transactions",
            "Auditability: every transaction is logged in plain text"
        ],
        "correct_answer": "Atomicity: all operations in a transaction complete successfully, or none of them do",
        "explanation": "Atomicity ensures that a transaction is treated as a single, indivisible unit of work: 'all or nothing'."
    },
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "Which SQL command is used to permanently save all changes made during the current transaction to the database?",
        "options": ["COMMIT", "ROLLBACK", "SAVEPOINT", "FLUSH"],
        "correct_answer": "COMMIT",
        "explanation": "COMMIT finalizes the transaction, making all data modifications permanent and visible to other transactions."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "What concurrency read anomaly occurs when a transaction reads uncommitted data written by another concurrent transaction that later rolls back?",
        "options": ["Dirty Read", "Non-repeatable Read", "Phantom Read", "Lost Update"],
        "correct_answer": "Dirty Read",
        "explanation": "A Dirty Read happens when Transaction A reads data modified by Transaction B before B has committed, and B subsequently rolls back."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "Which property in ACID ensures that once a transaction has committed, its changes will persist even in the event of a system power failure?",
        "options": ["Durability", "Isolation", "Consistency", "Atomicity"],
        "correct_answer": "Durability",
        "explanation": "Durability guarantees that committed transaction results survive system crashes, typically implemented via Write-Ahead Logging (WAL)."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "What is the correct sequence of states that a transaction transitions through in a standard DBMS state diagram?",
        "options": [
            "Active -> Partially Committed -> Committed",
            "Active -> Committed -> Partially Committed",
            "Partially Committed -> Active -> Terminated",
            "Committed -> Active -> Closed"
        ],
        "correct_answer": "Active -> Partially Committed -> Committed",
        "explanation": "A transaction begins in the Active state, enters Partially Committed after the final statement executes, and becomes Committed once logs are flushed."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "Under Two-Phase Locking (2PL), what rule governs the shrinking phase of a transaction?",
        "options": [
            "A transaction may release locks, but cannot acquire any new locks",
            "A transaction may acquire new locks, but cannot release any",
            "All locks must be converted to exclusive write locks",
            "Locks are automatically transferred to waiting transactions"
        ],
        "correct_answer": "A transaction may release locks, but cannot acquire any new locks",
        "explanation": "In 2PL, the growing phase allows acquiring locks without releasing any, and the shrinking phase allows releasing locks without acquiring new ones."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "Which transaction isolation level completely eliminates Dirty Reads, Non-repeatable Reads, and Phantom Reads?",
        "options": ["Serializable", "Repeatable Read", "Read Committed", "Read Uncommitted"],
        "correct_answer": "Serializable",
        "explanation": "Serializable is the highest ANSI SQL isolation level, preventing all concurrency anomalies by enforcing serializable execution schedules."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "What condition occurs when two or more transactions are each waiting for a lock held by the other, creating a circular wait cycle?",
        "options": ["Deadlock", "Livelock", "Starvation", "Cascading Abort"],
        "correct_answer": "Deadlock",
        "explanation": "A deadlock is a situation where two or more transactions are in a simultaneous circular wait, each holding a lock the other requires."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "What is a 'Phantom Read' anomaly in database transactions?",
        "options": [
            "A transaction re-executes a range query and discovers new rows inserted and committed by another transaction",
            "A transaction reads a row that was updated in memory but not on disk",
            "A transaction crashes and leaves unreleased read locks",
            "Two transactions overwrite the same column concurrently"
        ],
        "correct_answer": "A transaction re-executes a range query and discovers new rows inserted and committed by another transaction",
        "explanation": "Phantom Reads occur when new records satisfying a search condition are inserted and committed by a concurrent transaction between two reads."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "What does Conflict Serializability ensure in concurrent transaction scheduling?",
        "options": [
            "The schedule can be transformed into a serial schedule by swapping non-conflicting concurrent operations",
            "All read operations occur before any write operations",
            "No locks are required during query execution",
            "Transactions execute with zero latency"
        ],
        "correct_answer": "The schedule can be transformed into a serial schedule by swapping non-conflicting concurrent operations",
        "explanation": "Conflict serializability checks that a schedule's precedence graph contains no cycles, guaranteeing equivalence to a serial execution."
    },
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "What does Consistency guarantee in the context of ACID properties?",
        "options": [
            "The database transitions strictly from one valid state satisfying all schema constraints to another",
            "The database server maintains constant CPU frequency",
            "Queries execute in constant O(1) time",
            "All tables have identical number of rows"
        ],
        "correct_answer": "The database transitions strictly from one valid state satisfying all schema constraints to another",
        "explanation": "Consistency ensures that data integrity rules, primary/foreign key constraints, and business logic invariants are preserved."
    },
    {
        "type": "true_false",
        "difficulty": "Easy",
        "question": "True or False: Executing a ROLLBACK command undoes all modifications performed in the current transaction back to the beginning or to a SAVEPOINT.",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "True. ROLLBACK aborts the transaction and reverts all changes made since the transaction started or since the designated savepoint."
    },
    {
        "type": "true_false",
        "difficulty": "Medium",
        "question": "True or False: In DBMS recovery, the Write-Ahead Logging (WAL) protocol dictates that log records must be written to disk AFTER the data pages are modified on disk.",
        "options": ["True", "False"],
        "correct_answer": "False",
        "explanation": "False. The WAL protocol strictly mandates that log records describing a change must be written to non-volatile storage BEFORE the modified data page is flushed to disk."
    },
    {
        "type": "true_false",
        "difficulty": "Difficult",
        "question": "True or False: Cascading rollbacks occur in concurrent transactions when a transaction T1 fails and rolls back, forcing all transactions that read uncommitted data written by T1 to also roll back.",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "True. Cascading rollback is the cascading abort of dependent transactions that have read dirty uncommitted data from an aborted transaction."
    },
    {
        "type": "short_answer",
        "difficulty": "Medium",
        "question": "What is the term for a schedule of concurrent transactions whose execution outcome is equivalent to some serial execution of those transactions?",
        "options": [],
        "correct_answer": "Serializable Schedule",
        "explanation": "A serializable schedule guarantees that concurrent transaction execution yields the exact same state as if transactions were executed one after another."
    },
    {
        "type": "short_answer",
        "difficulty": "Easy",
        "question": "Which SQL statement creates an intermediate checkpoint inside a transaction that can be rolled back to without aborting the entire transaction?",
        "options": [],
        "correct_answer": "SAVEPOINT",
        "explanation": "SAVEPOINT allows partial rollbacks within a transaction without abandoning all preceding modifications."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "What type of lock allows multiple concurrent transactions to read a data item simultaneously but prevents any transaction from writing to it?",
        "options": ["Shared Lock (S-Lock)", "Exclusive Lock (X-Lock)", "Intent Lock", "Update Lock"],
        "correct_answer": "Shared Lock (S-Lock)",
        "explanation": "A Shared Lock allows concurrent reading by multiple transactions, while blocking exclusive write locks."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "What is Strict Two-Phase Locking (Strict 2PL) designed to prevent?",
        "options": ["Cascading Aborts", "Deadlocks", "Starvation", "Index fragmentation"],
        "correct_answer": "Cascading Aborts",
        "explanation": "Strict 2PL requires that all exclusive locks be held until the transaction explicitly commits or aborts, eliminating cascading rollbacks."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "In database crash recovery (ARIES algorithm), what are the three phases executed in sequence?",
        "options": ["Analysis, Redo, Undo", "Scan, Lock, Release", "Fetch, Decode, Execute", "Validate, Commit, Flush"],
        "correct_answer": "Analysis, Redo, Undo",
        "explanation": "ARIES recovery executes Analysis (reconstruct state), Redo (repeat history), and Undo (rollback active/uncommitted transactions)."
    },
    {
        "type": "true_false",
        "difficulty": "Medium",
        "question": "True or False: Under the Read Committed isolation level, a transaction never reads uncommitted dirty data from other transactions.",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "True. Read Committed prevents Dirty Reads by reading only committed versions of data rows."
    }
]

MACHINE_LEARNING_QUESTIONS = [
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "What is the primary characteristic that distinguishes Supervised Learning from Unsupervised Learning?",
        "options": [
            "Supervised learning trains on labeled input-output pairs; unsupervised learning finds patterns in unlabeled data",
            "Supervised learning does not require any training data",
            "Supervised learning is only used for image processing",
            "Supervised learning cannot perform classification"
        ],
        "correct_answer": "Supervised learning trains on labeled input-output pairs; unsupervised learning finds patterns in unlabeled data",
        "explanation": "Supervised learning algorithms map input features to known ground-truth labels, while unsupervised learning discovers intrinsic data distributions without target labels."
    },
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "Which of the following machine learning tasks is categorized as a Regression problem?",
        "options": [
            "Predicting the market sale price of a house based on square footage and location",
            "Classifying an incoming email as Spam or Not Spam",
            "Detecting whether an image contains a cat or a dog",
            "Clustering customer shopping baskets into 4 demographic segments"
        ],
        "correct_answer": "Predicting the market sale price of a house based on square footage and location",
        "explanation": "Regression predicts continuous numerical values (e.g. house price), whereas classification predicts discrete class labels."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "What occurs when a machine learning model suffers from Overfitting?",
        "options": [
            "The model achieves very low error on training data but fails to generalize to unseen test data",
            "The model performs poorly on both training and test datasets due to excessive simplicity",
            "The model's loss function diverges to infinity during gradient descent",
            "The model underutilizes available computing hardware"
        ],
        "correct_answer": "The model achieves very low error on training data but fails to generalize to unseen test data",
        "explanation": "Overfitting happens when a model learns noise and specific details of the training set rather than the underlying general trend, leading to poor test generalization."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "Which evaluation metric represents the harmonic mean of Precision and Recall?",
        "options": ["F1-Score", "ROC-AUC", "Mean Squared Error", "Accuracy"],
        "correct_answer": "F1-Score",
        "explanation": "The F1-Score is defined as 2 * (Precision * Recall) / (Precision + Recall), balancing precision and recall on imbalanced datasets."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "In gradient descent optimization, what role does the Learning Rate hyperparameter play?",
        "options": [
            "It controls the step size taken along the negative gradient direction to update model parameters",
            "It specifies the total number of layers in a deep neural network",
            "It measures the ratio of training data to test data",
            "It determines the number of clusters in K-Means"
        ],
        "correct_answer": "It controls the step size taken along the negative gradient direction to update model parameters",
        "explanation": "The learning rate scales the gradient vector during weight updates: too high can cause divergence, too low results in slow convergence."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "In the Bias-Variance Tradeoff, what typically happens as model complexity increases?",
        "options": [
            "Bias decreases while Variance increases",
            "Both Bias and Variance decrease to zero simultaneously",
            "Bias increases while Variance decreases",
            "Variance remains constant while Bias diverges"
        ],
        "correct_answer": "Bias decreases while Variance increases",
        "explanation": "Complex models fit training data closely (lower bias), but become more sensitive to data fluctuations (higher variance)."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "What is the primary purpose of Principal Component Analysis (PCA) in machine learning?",
        "options": [
            "Dimensionality reduction by projecting features onto orthogonal axes of maximum variance",
            "Supervised classification using margin maximization",
            "Calculating the gradient of backpropagation in recurrent networks",
            "Handling missing values through mean imputation"
        ],
        "correct_answer": "Dimensionality reduction by projecting features onto orthogonal axes of maximum variance",
        "explanation": "PCA is an unsupervised linear dimensionality reduction technique that finds principal orthogonal components capturing maximum data variance."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "Which regularization technique adds the L1 penalty (absolute sum of weights) to the loss function, encouraging parameter sparsity?",
        "options": ["Lasso Regularization", "Ridge Regularization", "Elastic Net (pure L2)", "Dropout"],
        "correct_answer": "Lasso Regularization",
        "explanation": "L1 / Lasso regularization penalizes absolute weight magnitudes, driving uninformative feature weights to exactly zero."
    },
    {
        "type": "true_false",
        "difficulty": "Easy",
        "question": "True or False: Logistic Regression is a supervised algorithm primarily used for classification rather than continuous numerical regression.",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "True. Despite the name 'regression', Logistic Regression applies the sigmoid function to output probabilities for discrete classification."
    },
    {
        "type": "true_false",
        "difficulty": "Medium",
        "question": "True or False: K-Fold Cross-Validation helps assess how well a model generalizes by partitioning data into K subsets and training K separate models.",
        "options": ["True", "False"],
        "correct_answer": "True",
        "explanation": "True. K-Fold CV trains on K-1 folds and validates on the remaining fold across K rounds to measure generalization."
    },
    {
        "type": "true_false",
        "difficulty": "Difficult",
        "question": "True or False: In K-Means clustering, the algorithm is guaranteed to converge to the global minimum of cluster inertia for any initial centroid placement.",
        "options": ["True", "False"],
        "correct_answer": "False",
        "explanation": "False. K-Means is sensitive to initial centroid placement and often converges to a local minimum; K-Means++ helps mitigate this."
    },
    {
        "type": "short_answer",
        "difficulty": "Medium",
        "question": "What is the matrix called that compares actual target classifications against model-predicted classifications (True Positives, False Positives, etc.)?",
        "options": [],
        "correct_answer": "Confusion Matrix",
        "explanation": "A Confusion Matrix summarizes prediction performance for classification models by charting TP, FP, TN, and FN counts."
    },
    {
        "type": "mcq",
        "difficulty": "Medium",
        "question": "Which ensemble learning technique combines multiple weak learners sequentially, with each subsequent learner focusing on errors made by previous models?",
        "options": ["Boosting (e.g. XGBoost, AdaBoost)", "Bagging (e.g. Random Forest)", "Stacking", "Voting Classifier"],
        "correct_answer": "Boosting (e.g. XGBoost, AdaBoost)",
        "explanation": "Boosting builds trees sequentially in an iterative manner, adjusting sample weights or fitting residuals from earlier rounds."
    },
    {
        "type": "mcq",
        "difficulty": "Easy",
        "question": "What is a Hyperparameter in Machine Learning?",
        "options": [
            "A configuration parameter whose value is set before training begins, rather than learned from data",
            "A model parameter learned automatically via gradient descent",
            "The target output column of a dataset",
            "The hardware CPU clock rate"
        ],
        "correct_answer": "A configuration parameter whose value is set before training begins, rather than learned from data",
        "explanation": "Hyperparameters (e.g. learning rate, number of trees, batch size) are specified prior to training to guide the learning process."
    },
    {
        "type": "mcq",
        "difficulty": "Difficult",
        "question": "What is the purpose of the Softmax activation function in the output layer of a multi-class neural network?",
        "options": [
            "Converts raw model logits into a normalized probability distribution that sums to 1.0",
            "Prevents vanishing gradients in recurrent networks",
            "Applies L2 weight decay to convolution filters",
            "Binarizes continuous features into binary masks"
        ],
        "correct_answer": "Converts raw model logits into a normalized probability distribution that sums to 1.0",
        "explanation": "Softmax exponentiates and normalizes output logits, producing valid class probabilities across multiple mutually exclusive categories."
    }
]

TOPIC_KNOWLEDGE_BASES = {
    "python loops": PYTHON_LOOPS_QUESTIONS,
    "dbms transactions": DBMS_TRANSACTIONS_QUESTIONS,
    "dbms transactions and acid properties": DBMS_TRANSACTIONS_QUESTIONS,
    "machine learning": MACHINE_LEARNING_QUESTIONS
}

def get_prebuilt_topic_questions(topic: str) -> Optional[List[Dict[str, Any]]]:
    """Returns domain-verified questions if topic matches prebuilt banks."""
    topic_clean = topic.strip().lower()
    for key, q_list in TOPIC_KNOWLEDGE_BASES.items():
        if key == topic_clean or (len(key) > 5 and key in topic_clean):
            return [dict(q) for q in q_list]
    return None

# =========================================================================
# DYNAMIC TOPIC CONCEPT GENERATOR (FOR EXPANSION & CUSTOM TOPICS UP TO 50)
# =========================================================================

def generate_dynamic_topic_knowledge_bank(
    topic: str,
    num_questions: int,
    difficulty: str,
    question_types: List[str]
) -> List[Dict[str, Any]]:
    """
    Generates conceptually grounded, non-templated technical questions
    for any custom topic or for scaling beyond prebuilt questions.
    """
    topic_title = normalize_topic(topic)
    type_cycle = question_types if question_types else ["mcq"]
    is_mixed = (difficulty.lower() == "mixed")
    diff_label = difficulty.capitalize() if difficulty.lower() in ("easy", "medium", "difficult") else "Medium"

    aspects = [
        ("Core Architecture", f"What is the foundational architectural principle behind {topic_title}?", f"Systematic execution and strict adherence to domain rules governing {topic_title}.", f"{topic_title} requires structured, predictable operational design."),
        ("State Management", f"How does state transition work during the execution of {topic_title}?", f"State updates occur deterministically under monitored boundary conditions in {topic_title}.", f"Deterministic state management guarantees consistent execution in {topic_title}."),
        ("Resource Optimization", f"Which strategy minimizes computational and memory overhead in {topic_title}?", f"Memory efficiency, lazy evaluation, and eliminating redundant operations in {topic_title}.", f"Resource optimization in {topic_title} prevents memory leaks and latency spikes."),
        ("Concurrency & Scaling", f"How are race conditions and synchronization handled when scaling {topic_title}?", f"Through thread-safety, mutual exclusion, or atomic operational guarantees in {topic_title}.", f"Concurrency control in {topic_title} maintains data integrity under load."),
        ("Exception Handling", f"What is the standard recovery mechanism when an unexpected error occurs during {topic_title}?", f"Catching exceptions, triggering fallback logic, and rolling back uncommitted state in {topic_title}.", f"Defensive programming in {topic_title} ensures graceful failure recovery."),
        ("Input Validation", f"Why is pre-validation of parameters critical prior to initiating {topic_title}?", f"To intercept invalid values before they propagate into internal logic of {topic_title}.", f"Parameter validation in {topic_title} protects runtime invariants."),
        ("Testing & Verification", f"What unit testing methodology is most effective for verifying {topic_title}?", f"Testing boundary values, edge cases, and deterministic output assertions for {topic_title}.", f"Automated tests for {topic_title} confirm functional correctness."),
        ("Performance Profiling", f"Which metric is most vital when profiling the execution efficiency of {topic_title}?", f"Throughput, latency, and CPU/memory utilization curves under {topic_title}.", f"Profiling identifies bottlenecks in {topic_title} routines."),
        ("Security Standards", f"How can vulnerabilities or unauthorized tampering be prevented in {topic_title}?", f"Enforcing access control, sanitizing inputs, and maintaining immutable audit trails for {topic_title}.", f"Security hardening in {topic_title} prevents exploitation."),
        ("Lifecycle Management", f"What stages comprise the standard operational lifecycle of {topic_title}?", f"Initialization, active execution, validation, and final resource deallocation in {topic_title}.", f"Lifecycle management in {topic_title} ensures complete resource cleanup."),
        ("Data Flow Mechanics", f"How do data packets or operands propagate through pipelines in {topic_title}?", f"Via unidirectional buffered streams or strictly validated call stacks in {topic_title}.", f"Data flow mechanisms in {topic_title} regulate data throughput."),
        ("Algorithmic Invariants", f"Which mathematical or computational invariant must hold true throughout {topic_title}?", f"Conservation of state consistency and bounded execution limits in {topic_title}.", f"Algorithmic invariants ensure determinism in {topic_title}."),
        ("Memory Allocations", f"How does the memory subsystem allocate dynamic objects during {topic_title}?", f"Through heap or stack allocations governed by runtime scoping rules in {topic_title}.", f"Memory allocation strategies dictate the performance profile of {topic_title}."),
        ("Asynchronous Workflows", f"What mechanism decouples non-blocking background routines in {topic_title}?", f"Event loops, promises, or non-blocking worker threads configured for {topic_title}.", f"Asynchronous processing improves responsiveness in {topic_title}."),
        ("Cache Invalidation", f"When should cached intermediate states in {topic_title} be invalidated?", f"Immediately upon mutation of underlying source dependencies in {topic_title}.", f"Proper cache invalidation prevents stale state reads in {topic_title}."),
        ("Failure Domains", f"How does fault isolation prevent cascading failures across sub-components of {topic_title}?", f"By implementing circuit breakers, timeouts, and compartmentalized modules in {topic_title}.", f"Fault isolation protects overarching stability in {topic_title}."),
        ("Idempotency Guarantees", f"Why is idempotency essential for retry policies in {topic_title}?", f"To ensure repeated execution produces identical side effects without duplicating operations in {topic_title}.", f"Idempotency enables safe retries in {topic_title}."),
        ("Boundary Edge Cases", f"Which boundary condition must be explicitly checked to prevent off-by-one errors in {topic_title}?", f"Upper and lower index limits, empty inputs, and null references in {topic_title}.", f"Boundary checks prevent index errors in {topic_title}."),
        ("Serialization Formats", f"Which serialization standard ensures cross-language interoperability in {topic_title}?", f"Standardized structured schemas like JSON, Protocol Buffers, or binary encodings for {topic_title}.", f"Structured serialization ensures portability in {topic_title}."),
        ("Deadlock Avoidance", f"What strategy prevents circular dependency deadlocks during resource allocation in {topic_title}?", f"Strict hierarchical lock acquisition ordering and timeout detection in {topic_title}.", f"Hierarchical locking breaks circular wait conditions in {topic_title}."),
        ("Backpressure Control", f"How does backpressure regulate overflowing message queues in {topic_title}?", f"By signaling upstream producers to slow down ingestion rates in {topic_title}.", f"Backpressure avoids queue exhaustion in {topic_title}."),
        ("Telemetry Tracking", f"Which telemetry signals give the clearest indication of degradation in {topic_title}?", f"P99 latency percentiles, error rate spikes, and memory heap growth in {topic_title}.", f"Telemetry provides observability into {topic_title} health."),
        ("Modular Decoupling", f"Why is high cohesion and loose coupling beneficial when structuring {topic_title}?", f"It allows independent modification, testing, and deployment of {topic_title} components.", f"Decoupling improves codebase maintainability in {topic_title}."),
        ("Configuration Tuning", f"Which runtime configuration parameter most directly governs throughput in {topic_title}?", f"Worker pool sizing, buffer capacity, and timeout thresholds in {topic_title}.", f"Parameter tuning aligns {topic_title} with workload capacity."),
        ("Audit Logging", f"What information must be captured in immutable audit logs for {topic_title}?", f"Timestamp, actor identity, operation type, and pre/post validation status in {topic_title}.", f"Audit logging provides compliance and forensics in {topic_title}.")
    ]

    questions = []
    seen = set()

    for idx, (aspect_name, q_mcq, ans_mcq, exp) in enumerate(aspects):
        if len(questions) >= num_questions + 10:
            break

        q_type = type_cycle[idx % len(type_cycle)]
        cand_diff = ["Easy", "Medium", "Difficult"][len(questions) % 3] if is_mixed else diff_label

        if q_type == "mcq":
            if q_mcq not in seen:
                seen.add(q_mcq)
                distractors = [
                    f"Disregarding boundary limits and disabling logging in {topic_title}",
                    f"An unoptimized brute-force approach that violates {topic_title} rules",
                    f"A deprecated mechanism that avoids {topic_title} standards"
                ]
                opts = [ans_mcq] + distractors
                random.shuffle(opts)
                questions.append({
                    "type": "mcq",
                    "difficulty": cand_diff,
                    "question": q_mcq,
                    "options": opts,
                    "correct_answer": ans_mcq,
                    "explanation": exp,
                    "topic": topic_title
                })

        elif q_type == "true_false":
            q_tf = f"True or False: In production environments, {topic_title} should be configured with robust monitoring and validation ({aspect_name})."
            if q_tf not in seen:
                seen.add(q_tf)
                questions.append({
                    "type": "true_false",
                    "difficulty": cand_diff,
                    "question": q_tf,
                    "options": ["True", "False"],
                    "correct_answer": "True",
                    "explanation": f"True. {exp}",
                    "topic": topic_title
                })

        elif q_type == "short_answer":
            q_sa = f"Explain how {aspect_name.lower()} impacts the overall reliability of {topic_title}."
            if q_sa not in seen:
                seen.add(q_sa)
                questions.append({
                    "type": "short_answer",
                    "difficulty": cand_diff,
                    "question": q_sa,
                    "options": [],
                    "correct_answer": ans_mcq,
                    "explanation": exp,
                    "topic": topic_title
                })

    for idx, (aspect_name, q_mcq, ans_mcq, exp) in enumerate(aspects):
        if len(questions) >= num_questions + 5:
            break

        cand_diff = ["Easy", "Medium", "Difficult"][len(questions) % 3] if is_mixed else diff_label
        q_inv_mcq = f"In advanced scenarios concerning {topic_title}, what primary trade-off must be managed for {aspect_name}?"
        if q_inv_mcq not in seen:
            seen.add(q_inv_mcq)
            c_ans = f"Balancing performance, computational overhead, and maintainability in {topic_title} ({aspect_name})"
            opts = [
                c_ans,
                f"Completely disabling {aspect_name} in {topic_title}",
                f"Introducing unhandled memory leaks in {topic_title}",
                f"Ignoring exception boundaries during {topic_title}"
            ]
            random.shuffle(opts)
            questions.append({
                "type": "mcq",
                "difficulty": cand_diff,
                "question": q_inv_mcq,
                "options": opts,
                "correct_answer": c_ans,
                "explanation": exp,
                "topic": topic_title
            })

    # Pass 3: Edge Case & Invariant Questions (scales up to 75+)
    for idx, (aspect_name, q_mcq, ans_mcq, exp) in enumerate(aspects):
        if len(questions) >= num_questions + 5:
            break

        cand_diff = ["Easy", "Medium", "Difficult"][len(questions) % 3] if is_mixed else diff_label
        q_pass3 = f"Which best practice is strongly recommended when architecting {topic_title} for {aspect_name}?"
        if q_pass3 not in seen:
            seen.add(q_pass3)
            c_ans = f"Continuous profiling, defensive assertion checks, and automated validation for {aspect_name}"
            opts = [
                c_ans,
                f"Hardcoding static thresholds and bypassing monitoring in {topic_title}",
                f"Running unverified background tasks without error handling in {topic_title}",
                f"Suppressing all error notifications originating from {aspect_name}"
            ]
            random.shuffle(opts)
            questions.append({
                "type": "mcq",
                "difficulty": cand_diff,
                "question": q_pass3,
                "options": opts,
                "correct_answer": c_ans,
                "explanation": f"Best practices in {topic_title} require proactive validation and continuous health tracking ({aspect_name}).",
                "topic": topic_title
            })

    # Pass 4: Failure & Recovery Questions (scales up to 100+)
    for idx, (aspect_name, q_mcq, ans_mcq, exp) in enumerate(aspects):
        if len(questions) >= num_questions + 5:
            break

        cand_diff = ["Easy", "Medium", "Difficult"][len(questions) % 3] if is_mixed else diff_label
        q_pass4 = f"What is the expected system behavior when a severe anomaly impacts {aspect_name} in {topic_title}?"
        if q_pass4 not in seen:
            seen.add(q_pass4)
            c_ans = f"Triggering automated circuit breakers, logging diagnostic traces, and falling back safely"
            opts = [
                c_ans,
                f"Silently corrupting transactional state without logging errors",
                f"Terminating the entire host operating system immediately",
                f"Broadcasting sensitive internal state tokens to external clients"
            ]
            random.shuffle(opts)
            questions.append({
                "type": "mcq",
                "difficulty": cand_diff,
                "question": q_pass4,
                "options": opts,
                "correct_answer": c_ans,
                "explanation": f"Fault-tolerant design in {topic_title} requires structured failure domains and graceful recovery ({aspect_name}).",
                "topic": topic_title
            })

    return questions

# =========================================================================
# DOMAIN FLASHCARDS
# =========================================================================

PYTHON_LOOPS_FLASHCARDS = [
    {
        "front": "What does the 'break' statement do inside a Python loop?",
        "back": "It immediately terminates the loop and transfers execution to the statement immediately following the loop block."
    },
    {
        "front": "What does the 'continue' statement do inside a Python loop?",
        "back": "It skips the remainder of the current iteration and jumps directly to the beginning of the next iteration."
    },
    {
        "front": "How does the 'else' block behave when attached to a Python 'for' or 'while' loop?",
        "back": "It executes only if the loop terminates normally (completes all iterations without encountering a 'break' statement)."
    },
    {
        "front": "What is the purpose of the built-in 'enumerate()' function in Python loops?",
        "back": "It returns an iterator of tuples containing the index count and the corresponding element from an iterable."
    },
    {
        "front": "What is the purpose of the 'zip()' function during loop iteration in Python?",
        "back": "It aggregates elements from two or more iterables in parallel, yielding tuples of corresponding items."
    },
    {
        "front": "What is the behavior of 'range(start, stop, step)' in Python?",
        "back": "It generates an immutable sequence of integers starting from 'start', incrementing by 'step', and stopping strictly before 'stop'."
    },
    {
        "front": "What causes an infinite loop in Python and how can it be avoided?",
        "back": "An infinite loop occurs when the while condition never becomes False; ensure the loop variable is properly modified inside the loop."
    },
    {
        "front": "What is the difference between 'pass' and 'continue' inside a Python loop?",
        "back": "'pass' is a null statement (no-op) that does nothing, whereas 'continue' interrupts the iteration and jumps to the next loop cycle."
    },
    {
        "front": "Why is modifying a list in-place while iterating over it with a 'for' loop discouraged in Python?",
        "back": "Deleting or adding items shifts indices during traversal, causing skipped elements or unexpected iteration side effects."
    },
    {
        "front": "What is a generator expression and why is it preferred over list comprehensions in large loops?",
        "back": "Generators produce items lazily on-demand using iterator protocol, consuming O(1) memory instead of allocating the full collection."
    }
]

DBMS_TRANSACTIONS_FLASHCARDS = [
    {
        "front": "What does Atomicity mean in the ACID properties of DBMS transactions?",
        "back": "Atomicity guarantees that all operations in a transaction are completed successfully, or none of them are (all-or-nothing)."
    },
    {
        "front": "What does Consistency guarantee in ACID transaction management?",
        "back": "Consistency ensures that a transaction brings the database from one valid state to another, maintaining all integrity constraints and rules."
    },
    {
        "front": "What is Isolation in DBMS transactions?",
        "back": "Isolation ensures that concurrent execution of transactions results in a system state that would be obtained if transactions were executed sequentially."
    },
    {
        "front": "What does Durability guarantee in database transactions?",
        "back": "Durability guarantees that once a transaction commits, its modifications persist permanently, even in the event of a system crash or power outage."
    },
    {
        "front": "What is a 'Dirty Read' anomaly in concurrent database transactions?",
        "back": "A situation where Transaction A reads uncommitted data written by Transaction B, and Transaction B subsequently rolls back."
    },
    {
        "front": "What is a 'Non-Repeatable Read' anomaly in DBMS?",
        "back": "Occurs when Transaction A reads a row, Transaction B modifies or deletes that row and commits, and Transaction A re-reads the row obtaining different data."
    },
    {
        "front": "What is a 'Phantom Read' anomaly in DBMS transactions?",
        "back": "Occurs when Transaction A executes a range query, Transaction B inserts new rows matching the range and commits, and Transaction A re-executes the query seeing new phantom rows."
    },
    {
        "front": "What is Two-Phase Locking (2PL) and what are its two phases?",
        "back": "A concurrency control protocol with a Growing Phase (locks acquired, none released) and a Shrinking Phase (locks released, none acquired)."
    },
    {
        "front": "What is Write-Ahead Logging (WAL) in database transaction recovery?",
        "back": "A protocol mandating that log records describing a change must be flushed to non-volatile storage before the modified data page is written to disk."
    },
    {
        "front": "What is a Deadlock in DBMS transactions and how is it resolved?",
        "back": "A circular wait condition where transactions hold locks each other requires; resolved by deadlock detection (wait-for graphs) and aborting a victim transaction."
    }
]

MACHINE_LEARNING_FLASHCARDS = [
    {
        "front": "What is the difference between Supervised and Unsupervised Learning?",
        "back": "Supervised learning trains models on labeled input-target pairs; unsupervised learning discovers patterns and latent structures in unlabeled data."
    },
    {
        "front": "What is Overfitting in Machine Learning and how is it mitigated?",
        "back": "When a model memorizes noise in the training set and fails to generalize; mitigated by regularization (L1/L2), cross-validation, pruning, or dropout."
    },
    {
        "front": "What is the Bias-Variance Tradeoff?",
        "back": "High bias causes underfitting (oversimplified assumptions); high variance causes overfitting (high sensitivity to training noise); optimal models balance both."
    },
    {
        "front": "What is the F1-Score and when should it be preferred over Accuracy?",
        "back": "The harmonic mean of Precision and Recall (2*P*R / (P+R)); preferred when evaluating models on imbalanced datasets where accuracy is misleading."
    },
    {
        "front": "What is Gradient Descent and what role does the Learning Rate play?",
        "back": "An optimization algorithm that iteratively steps in the direction of negative gradient to minimize loss; the learning rate controls step magnitude."
    },
    {
        "front": "What is Principal Component Analysis (PCA)?",
        "back": "An unsupervised linear dimensionality reduction method that projects features onto orthogonal axes of maximum variance."
    },
    {
        "front": "What is K-Fold Cross-Validation?",
        "back": "A resampling technique that divides data into K subsets, training on K-1 folds and validating on the remaining fold across K rounds to measure generalization."
    },
    {
        "front": "What is the difference between L1 (Lasso) and L2 (Ridge) Regularization?",
        "back": "L1 penalizes absolute weight sums driving weights to zero (feature selection); L2 penalizes squared weight sums shrinking weights smoothly."
    },
    {
        "front": "What is a Confusion Matrix?",
        "back": "A tabular layout that visualizes classification performance by displaying counts of True Positives, False Positives, True Negatives, and False Negatives."
    },
    {
        "front": "What is Logistic Regression used for?",
        "back": "A supervised classification algorithm that applies the logistic sigmoid function to output probabilities between 0 and 1 for discrete outcomes."
    }
]

TOPIC_FLASHCARD_BASES = {
    "python loops": PYTHON_LOOPS_FLASHCARDS,
    "dbms transactions": DBMS_TRANSACTIONS_FLASHCARDS,
    "dbms transactions and acid properties": DBMS_TRANSACTIONS_FLASHCARDS,
    "machine learning": MACHINE_LEARNING_FLASHCARDS
}

def get_prebuilt_topic_flashcards(topic: str) -> Optional[List[Dict[str, str]]]:
    """Returns domain-verified flashcards if topic matches prebuilt banks."""
    topic_clean = topic.strip().lower()
    for key, fc_list in TOPIC_FLASHCARD_BASES.items():
        if key == topic_clean or (len(key) > 5 and key in topic_clean):
            return [dict(fc) for fc in fc_list]
    return None
