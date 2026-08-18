/**
 * QuizGen AI - 3D Flashcards Logic
 */

let activeDeck = null;
let currentCardIndex = 0;

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();

  // Check URL parameters for prefilled topic
  const params = new URLSearchParams(window.location.search);
  const prefillTopic = params.get('topic');
  if (prefillTopic) {
    const topicInput = document.getElementById('deckTopicInput');
    if (topicInput) {
      topicInput.value = prefillTopic;
    }
    if (params.get('open') === '1' || params.get('new') === '1') {
      openCreateDeckModal();
    }
  }

  await loadDecks();
  setupFlashcardEvents();
});

async function loadDecks() {
  const container = document.getElementById('decksContainer');

  try {
    const data = await fetchAPI('/api/flashcards');
    const decks = data.decks || [];

    if (decks.length === 0) {
      container.innerHTML = `
        <div class="card" style="text-align: center; padding: 3.5rem 1.5rem;">
          <div style="font-size: 3rem; margin-bottom: 0.6rem;">🗂️</div>
          <h2 style="font-size: 1.4rem; margin-bottom: 0.4rem;">No flashcards available yet.</h2>
          <p style="color: var(--text-muted); font-size: 0.95rem; max-width: 480px; margin: 0 auto 1.5rem;">
            Generate flashcard decks from your study materials or requested topics to reinforce memory with active recall.
          </p>
          <button onclick="openCreateDeckModal()" class="btn btn-primary">Generate First Deck</button>
        </div>
      `;
      return;
    }

    let html = '<div class="grid-3">';

    decks.forEach(d => {
      const dateStr = d.created_at ? new Date(d.created_at).toLocaleDateString() : '';
      const masteredPercent = d.card_count > 0 ? Math.round((d.mastered_count / d.card_count) * 100) : 0;

      html += `
        <div class="card card-hover" style="display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.8rem;">
              <span style="font-size: 2rem;">🗂️</span>
              <span style="font-size: 0.8rem; font-weight: 700; color: var(--primary); background: var(--primary-light); padding: 0.2rem 0.6rem; border-radius: var(--radius-full);">
                ${d.card_count} Cards
              </span>
            </div>

            <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.4rem; color: var(--text-main);">
              ${escapeHTML(d.title)}
            </h3>

            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
              🏷️ ${escapeHTML(d.topic)} • 📅 ${dateStr}
            </div>

            <!-- Mastery Progress -->
            <div style="margin-bottom: 1.2rem;">
              <div style="display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: 600; color: var(--text-muted); margin-bottom: 0.3rem;">
                <span>Mastery</span>
                <span>${masteredPercent}% (${d.mastered_count}/${d.card_count})</span>
              </div>
              <div style="height: 6px; background: var(--bg-alt); border-radius: var(--radius-full); overflow: hidden;">
                <div style="width: ${masteredPercent}%; height: 100%; background: var(--success);"></div>
              </div>
            </div>
          </div>

          <div style="display: flex; gap: 0.5rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
            <button onclick="playDeck('${d.id}')" class="btn btn-primary btn-sm" style="flex: 1;">
              ⚡ Study Deck
            </button>
            <button onclick="deleteDeck('${d.id}')" class="btn btn-secondary btn-sm" style="color: var(--danger);" title="Delete">
              🗑️
            </button>
          </div>
        </div>
      `;
    });

    html += '</div>';
    container.innerHTML = html;

  } catch (error) {
    container.innerHTML = `<div class="card" style="color: var(--danger); text-align: center; padding: 2rem;">${escapeHTML(error.message || 'Unable to load flashcards. Please try again.')}</div>`;
  }
}

function openCreateDeckModal() {
  const modal = document.getElementById('newDeckModal');
  if (modal) modal.classList.add('active');
}

function setupFlashcardEvents() {
  const modal = document.getElementById('newDeckModal');
  const openBtn = document.getElementById('openNewDeckModalBtn');
  if (openBtn) openBtn.onclick = openCreateDeckModal;

  const closeBtn = document.getElementById('closeDeckModalBtn');
  if (closeBtn) closeBtn.onclick = () => modal.classList.remove('active');

  const cardElement = document.getElementById('flashcardElement');
  if (cardElement) {
    cardElement.onclick = () => {
      cardElement.classList.toggle('flipped');
    };
  }

  // Keyboard Spacebar flip
  document.addEventListener('keydown', (e) => {
    const playerView = document.getElementById('flashcardPlayerView');
    if (e.code === 'Space' && playerView && playerView.style.display !== 'none') {
      if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        if (cardElement) cardElement.classList.toggle('flipped');
      }
    }
  });

  const backBtn = document.getElementById('backToDecksBtn');
  if (backBtn) {
    backBtn.onclick = () => {
      document.getElementById('flashcardPlayerView').style.display = 'none';
      document.getElementById('decksListView').style.display = 'block';
      loadDecks();
    };
  }

  const prevBtn = document.getElementById('prevCardBtn');
  if (prevBtn) {
    prevBtn.onclick = () => {
      if (activeDeck && currentCardIndex > 0) {
        currentCardIndex--;
        renderActiveCard();
      }
    };
  }

  const nextBtn = document.getElementById('nextCardBtn');
  if (nextBtn) {
    nextBtn.onclick = () => {
      if (activeDeck && activeDeck.cards && currentCardIndex < activeDeck.cards.length - 1) {
        currentCardIndex++;
        renderActiveCard();
      }
    };
  }

  const rateEasy = document.getElementById('rateEasyBtn');
  if (rateEasy) {
    rateEasy.onclick = async () => {
      await updateCardRating(true, 'easy');
    };
  }

  const rateHard = document.getElementById('rateHardBtn');
  if (rateHard) {
    rateHard.onclick = async () => {
      await updateCardRating(false, 'hard');
    };
  }

  // Form Submit
  const createForm = document.getElementById('createDeckForm');
  if (createForm) {
    createForm.onsubmit = async (e) => {
      e.preventDefault();
      const topic = document.getElementById('deckTopicInput').value.trim();
      const text = document.getElementById('deckTextInput') ? document.getElementById('deckTextInput').value.trim() : '';
      const numCards = parseInt(document.getElementById('deckNumCards').value, 10);

      if (!topic && !text) {
        showToast('Please enter a topic or paste study text.', 'error');
        return;
      }

      const btn = document.getElementById('generateDeckSubmitBtn');
      btn.disabled = true;
      btn.innerText = 'Extracting flashcards...';

      try {
        const data = await fetchAPI('/api/flashcards/generate', {
          method: 'POST',
          body: JSON.stringify({
            topic,
            text,
            num_cards: numCards
          })
        });

        modal.classList.remove('active');
        showToast('Flashcard deck generated!', 'success');
        btn.disabled = false;
        btn.innerText = '⚡ Generate Flashcards';

        const deckId = (data.deck && data.deck.id) ? data.deck.id : (data.deck ? data.deck._id : null);
        if (deckId) {
          playDeck(deckId);
        } else {
          loadDecks();
        }

      } catch (error) {
        btn.disabled = false;
        btn.innerText = '⚡ Generate Flashcards';
        showToast(error.message || 'Unable to generate flashcards. Please try again.', 'error');
      }
    };
  }
}

async function playDeck(deckId) {
  try {
    const data = await fetchAPI(`/api/flashcards/${deckId}`);
    activeDeck = data.deck;
    currentCardIndex = 0;

    document.getElementById('deckTitleBadge').innerText = activeDeck.title || activeDeck.topic;
    document.getElementById('decksListView').style.display = 'none';
    document.getElementById('flashcardPlayerView').style.display = 'block';

    renderActiveCard();
  } catch (error) {
    showToast(error.message || 'Failed to load deck.', 'error');
  }
}

function renderActiveCard() {
  if (!activeDeck || !activeDeck.cards || activeDeck.cards.length === 0) return;

  const total = activeDeck.cards.length;
  const card = activeDeck.cards[currentCardIndex];

  // Unflip card
  const cardElement = document.getElementById('flashcardElement');
  if (cardElement) cardElement.classList.remove('flipped');

  document.getElementById('cardCounterText').innerText = `Card ${currentCardIndex + 1} of ${total}`;
  document.getElementById('cardFrontText').innerText = card.front;
  document.getElementById('cardBackText').innerText = card.back;

  const citationEl = document.getElementById('cardCitationText');
  if (citationEl) {
    if (card.source_page) {
      citationEl.innerText = `📖 Source: Page ${card.source_page}`;
    } else {
      citationEl.innerText = `🏷️ Topic: ${card.topic || activeDeck.topic || 'General'}`;
    }
  }

  document.getElementById('prevCardBtn').disabled = currentCardIndex === 0;
  document.getElementById('nextCardBtn').disabled = currentCardIndex === total - 1;
}

async function updateCardRating(mastered, rating) {
  if (!activeDeck || !activeDeck.cards) return;
  const card = activeDeck.cards[currentCardIndex];

  try {
    const cardId = card.id || card._id;
    await fetchAPI(`/api/flashcards/${activeDeck.id}/cards/${cardId}`, {
      method: 'PUT',
      body: JSON.stringify({
        mastered: mastered,
        difficulty_rating: rating
      })
    });

    card.mastered = mastered;
    card.difficulty_rating = rating;

    showToast(mastered ? 'Card marked as Mastered! 🌟' : 'Marked as Difficult for review 🤔', 'info', 2000);

    // Advance to next card if not on last
    if (currentCardIndex < activeDeck.cards.length - 1) {
      currentCardIndex++;
      renderActiveCard();
    }
  } catch (err) {
    showToast(err.message || 'Could not update card status.', 'error');
  }
}

async function deleteDeck(deckId) {
  if (!confirm('Are you sure you want to delete this flashcard deck?')) return;

  try {
    await fetchAPI(`/api/flashcards/${deckId}`, { method: 'DELETE' });
    showToast('Deck deleted.', 'success');
    await loadDecks();
  } catch (err) {
    showToast(err.message || 'Failed to delete deck.', 'error');
  }
}
